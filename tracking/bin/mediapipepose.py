print("Importing libraries...")

import os
import sys

sys.path.append(os.getcwd())    #embedable python doesnt find local modules without this line

import time
import threading
import cv2
import numpy as np

from helpers import  CameraStream, shutdown, mediapipeTo3dpose, get_rot_mediapipe, get_rot_hands, draw_pose, keypoints_to_original, normalize_screen_coordinates, get_rot
from scipy.spatial.transform import Rotation as R
from backends import DummyBackend, SteamVRBackend, VRChatOSCBackend
import webui

import inference_gui
import parameters

import tkinter as tk
from tkinter import messagebox

import mediapipe as mp
from frame_metrics import FrameMetrics
from video_source import VideoFileSource, VideoInputError


def main():
    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose

    use_steamvr = True

    print("INFO: Reading parameters...")

    params = parameters.Parameters()

    if params.webui:
        webui_thread = threading.Thread(target=webui.start_webui, args=(params,), daemon=True)
        webui_thread.start()
    else:
        print("INFO: WebUI disabled in parameters")

    backends = { 0: DummyBackend, 1: SteamVRBackend, 2: VRChatOSCBackend }
    backend = backends[params.backend]()
    camera_thread = None
    pose = None
    try:
        backend.connect(params)
        if params.exit_ready:
            return
        is_video = getattr(params, 'input_mode', 'camera') == 'video'
        camera_thread = VideoFileSource(params.video_path) if is_video else CameraStream(params)
        #making gui
        gui_thread = threading.Thread(target=inference_gui.make_inference_gui, args=(params,), daemon=True)
        gui_thread.start()

        print("INFO: Starting pose detector...")

        #create our detector. These are default parameters as used in the tutorial.
        pose = mp_pose.Pose(model_complexity=params.model,
                            min_detection_confidence=0.5,
                            min_tracking_confidence=params.min_tracking_confidence,
                            smooth_landmarks=params.smooth_landmarks,
                            static_image_mode=params.static_image)

        cv2.namedWindow("out")

        #Main program loop:

        rotation = 0
        i = 0

        prev_smoothing = params.smoothing
        prev_add_smoothing = params.additional_smoothing
        metrics = FrameMetrics()
        cycle_start = time.perf_counter()
        preview = None
        if is_video:
            camera_thread.start()

        while True:
            # Capture frame-by-frame
            if params.exit_ready:
                shutdown(params)

            if prev_smoothing != params.smoothing or prev_add_smoothing != params.additional_smoothing:
                print(f"INFO: Changed smoothing value from {prev_smoothing} to {params.smoothing}")
                print(f"INFO: Changed additional smoothing from {prev_add_smoothing} to {params.additional_smoothing}")

                prev_smoothing = params.smoothing
                prev_add_smoothing = params.additional_smoothing

                backend.onparamchanged(params)

            #wait untill camera thread captures another image
            if is_video:
                if params.cancel_input:
                    camera_thread.cancel()
                    params.cancel_input = False
                if params.restart_input:
                    params.restart_input = False
                    try:
                        camera_thread.restart()
                        pose.reset()
                        backend.reset()
                        if hasattr(params, 'pose3d_og'):
                            del params.pose3d_og
                        metrics = FrameMetrics()
                    except Exception as exc:
                        camera_thread.fail(str(exc))
                if params.paused:
                    camera_thread.pause()
                elif camera_thread.state in ('ready', 'paused'):
                    camera_thread.start()
            try:
                frame = camera_thread.read_latest()
            except VideoInputError as exc:
                print('ERROR: ' + str(exc))
                frame = None
            if is_video:
                params.input_status = camera_thread.status
            if frame is None:
                if is_video and preview is not None:
                    view = preview.copy()
                    cv2.putText(view, camera_thread.status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                    cv2.imshow('out', view)
                    if cv2.waitKey(1) == 27:
                        shutdown(params)
                if is_video and camera_thread.state != 'running':
                    cycle_start = time.perf_counter()
                time.sleep(0.001)
                continue

            img, capture_seconds, captured_at = frame
            params.frame_timestamp_ms = camera_thread.timestamp_ms if is_video else captured_at * 1000
            params.frame_index = camera_thread.index if is_video else None
            frame_age = time.perf_counter() - captured_at

            #if set, rotate the image
            if params.rotate_image is not None:
                img = cv2.rotate(img, params.rotate_image)

            if params.mirror:
                img = cv2.flip(img,1)

            #if set, ensure image does not exceed the given size.
            if max(img.shape) > params.maximgsize:
                ratio = max(img.shape)/params.maximgsize
                img = cv2.resize(img, (int(img.shape[1]/ratio),int(img.shape[0]/ratio)))

            if params.paused:
                cv2.imshow("out", img)
                cv2.waitKey(1)
                # Não mistura o tempo em pausa com as medições do rastreamento.
                cycle_start = time.perf_counter()
                continue

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            #print(image.shape)

            t0 = time.perf_counter()
            # To improve performance, optionally mark the image as not writeable to
            # pass by reference.    copied from the tutorial
            img.flags.writeable = False
            try:
                results = pose.process(img)
            except Exception as exc:
                if not is_video:
                    raise
                camera_thread.fail('Falha na análise da pose: ' + str(exc))
                params.input_status = camera_thread.status
                preview = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                continue
            pose_seconds = time.perf_counter() - t0
            img.flags.writeable = True
            tracker_seconds = 0.0

            if results.pose_world_landmarks:        #if any pose was detected
                tracker_start = time.perf_counter()

                pose3d = mediapipeTo3dpose(results.pose_world_landmarks.landmark)   #convert keypoints to a format we use

                #do we need this with osc as well?

                pose3d[:,0] = -pose3d[:,0]      #flip the points a bit since steamvrs coordinate system is a bit diffrent
                pose3d[:,1] = -pose3d[:,1]

                pose3d_og = pose3d.copy()
                params.pose3d_og = pose3d_og

                for j in range(pose3d.shape[0]):        #apply the rotations from the sliders
                    pose3d[j] = params.global_rot_z.apply(pose3d[j])
                    pose3d[j] = params.global_rot_x.apply(pose3d[j])
                    pose3d[j] = params.global_rot_y.apply(pose3d[j])

                if not params.feet_rotation:
                    rots = get_rot(pose3d)          #get rotation data of feet and hips from the position-only skeleton data
                else:
                    rots = get_rot_mediapipe(pose3d)

                if params.use_hands:
                    hand_rots = get_rot_hands(pose3d)
                else:
                    hand_rots = None


                #pose3d[0] = [1,0,1]
                #rots = (rots[0], R.from_euler('ZXY',[i/17,i/11,i/10]).as_quat(),rots[2])   #for testing rotation conversions
                #i+=1

                updated = backend.updatepose(params, pose3d, rots, hand_rots)
                tracker_seconds = time.perf_counter() - tracker_start
                if not updated:
                    cycle_start = time.perf_counter()
                    continue


            img = cv2.cvtColor(img,cv2.COLOR_RGB2BGR)       #convert back to bgr and draw the pose
            mp_drawing.draw_landmarks(
                img, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            # Exibe a janela anterior: o ciclo atual só termina após imshow/waitKey.
            summary = metrics.summary()
            # Duas linhas cabem na resolução padrão; desenha somente na cópia de exibição.
            first_line, second_line = summary.split(' | idade:', 1) if ' | idade:' in summary else (summary, '')
            for row, text in enumerate((first_line, 'idade:' + second_line if second_line else '')):
                cv2.putText(img, text, (10, 22 + row * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
            if not results.pose_world_landmarks:
                cv2.putText(img, 'SEM POSE - trackers sem nova medicao', (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
            if is_video:
                cv2.putText(img, camera_thread.status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                preview = img.copy()

            cv2.imshow("out", img)           #show image, exit program if we press esc
            key = cv2.waitKey(1)
            cycle_end = time.perf_counter()
            metrics.add(capture=capture_seconds, age=frame_age, pose=pose_seconds,
                        trackers=tracker_seconds, cycle=cycle_end - cycle_start)
            if params.log_frametime:
                print('INFO: ' + metrics.summary())
            # Inclui o custo do log no próximo ciclo.
            cycle_start = cycle_end
            if key == 27:
                shutdown(params)

    except VideoInputError as exc:
        params.input_status = str(exc)
        print('ERROR: ' + str(exc))
        messagebox.showerror('Erro ao abrir vídeo', str(exc))
    finally:
        if camera_thread is not None and hasattr(camera_thread, 'close'):
            camera_thread.close()
        if pose is not None:
            pose.close()
        backend.disconnect()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    if '--check-runtime' in sys.argv:
        # Smoke test do executável empacotado, sem iniciar Tk ou exigir uma webcam.
        with mp.solutions.pose.Pose(model_complexity=1) as detector:
            result = detector.process(np.zeros((120, 160, 3), dtype=np.uint8))
            assert result.pose_world_landmarks is None
        print('Runtime OK: OpenCV, MediaPipe Pose e modelos disponíveis')
    else:
        main()

