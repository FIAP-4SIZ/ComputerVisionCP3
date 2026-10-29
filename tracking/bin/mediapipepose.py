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
from hand_quality import HandQualitySettings
from finger_tracking import FingerTracking, draw_hands
from body_observation import observe_body, draw_observation
from frame_metrics import FrameMetrics
from video_source import VideoFileSource, VideoInputError
from pose_validation import InvalidPose
from independent_trackers import prepare_trackers, enabled_names, TrackerLifecycle
from lighting import DEFAULT_LIGHTING, LABELS, apply_lighting, comparison_view, resize_for_pose


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
    fingers = None
    finger_frames = {}
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

        if getattr(params, 'track_fingers', False):
            # Mãos independentes da pose corporal: funcionam sem quadris/pernas.
            fingers = FingerTracking(mp.solutions.hands.Hands(max_num_hands=2),
                                     backend.client if params.backend == 2 else None,
                                     getattr(params, 'hand_quality', HandQualitySettings()))
        cv2.namedWindow("out")

        #Main program loop:

        rotation = 0
        i = 0

        prev_smoothing = params.smoothing
        prev_add_smoothing = params.additional_smoothing
        metrics = FrameMetrics()
        cycle_start = time.perf_counter()
        preview = None
        preview_original = None
        preview_settings = DEFAULT_LIGHTING
        preview_preprocess_ms = 0.
        active_lighting_key = None
        tracker_lifecycle = TrackerLifecycle(enabled_names(params))
        params.tracker_status = tracker_lifecycle.summary()
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
                        if fingers is not None:
                            fingers.reset()
                        backend.reset()
                        tracker_lifecycle.reset()
                        active_lighting_key = None
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
                if fingers is not None and is_video and camera_thread.state != 'running':
                    fingers.suspend()
                if is_video and camera_thread.state in ('completed', 'cancelled', 'error'):
                    if (tracker_lifecycle.timestamp is not None
                            or any(state != 'expired' for state in tracker_lifecycle.states.values())):
                        backend.expire_trackers(tracker_lifecycle.invalidate())
                    params.tracker_status = tracker_lifecycle.summary()
                    if hasattr(params, 'pose3d_og'):
                        del params.pose3d_og
                if is_video and preview is not None:
                    view = preview.copy()
                    cv2.rectangle(view, (0, 97), (view.shape[1], 118), (0, 0, 0), -1)
                    cv2.putText(view, params.tracker_status, (10, 112), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                    cv2.putText(view, camera_thread.status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                    cv2.imshow('out', comparison_view(preview_original, view, preview_settings, preview_preprocess_ms))
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
            original = resize_for_pose(img, params.maximgsize)
            settings = getattr(params, 'lighting', DEFAULT_LIGHTING)
            preprocessing_start = time.perf_counter()
            img = apply_lighting(original, settings)
            preprocess_ms = (time.perf_counter() - preprocessing_start) * 1000
            params.lighting_status = f'{LABELS[settings.mode]} | PDI:{preprocess_ms:.2f}ms'

            if params.paused and not is_video:
                if fingers is not None:
                    fingers.suspend()
                cv2.imshow("out", comparison_view(original, img, settings, preprocess_ms))
                cv2.waitKey(1)
                # Não mistura o tempo em pausa com as medições do rastreamento.
                cycle_start = time.perf_counter()
                continue

            key = settings.inference_key()
            if active_lighting_key is not None and key != active_lighting_key:
                pose.reset()
                if fingers is not None:
                    fingers.reset()
                backend.reset()
                tracker_lifecycle.reset()
                metrics = FrameMetrics()
                if hasattr(params, 'pose3d_og'):
                    del params.pose3d_og
            active_lighting_key = key

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            #print(image.shape)

            t0 = time.perf_counter()
            # To improve performance, optionally mark the image as not writeable to
            # pass by reference.    copied from the tutorial
            img.flags.writeable = False
            try:
                results = pose.process(img)
                if fingers is not None:
                    fingers.settings = getattr(params, 'hand_quality', fingers.settings)
                    finger_frames = fingers.process(img, mirrored=params.mirror)
                    params.finger_frames = finger_frames
                    params.finger_timestamp_ms = params.frame_timestamp_ms
            except Exception as exc:
                if not is_video:
                    raise
                if fingers is not None:
                    fingers.suspend()
                camera_thread.fail('Falha na análise da pose/maos: ' + str(exc))
                params.input_status = camera_thread.status
                preview = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                preview_original = original.copy()
                preview_settings = settings
                preview_preprocess_ms = preprocess_ms
                continue
            pose_seconds = time.perf_counter() - t0
            img.flags.writeable = True
            tracker_seconds = 0.0

            image_landmarks = results.pose_landmarks.landmark if results.pose_landmarks else None
            params.body_observation = observe_body(image_landmarks, getattr(params, 'min_visibility', .5))
            params.body_status = params.body_observation.status
            params.pose_status = 'Sem pose detectavel'
            tracking = None
            valid = dict.fromkeys(tracker_lifecycle.names, False)
            tracker_start = time.perf_counter()
            if results.pose_world_landmarks:
                try:
                    tracking = prepare_trackers(results.pose_world_landmarks.landmark, params, image_landmarks=image_landmarks)
                    valid = tracking.valid
                except InvalidPose as exc:
                    params.pose_status = str(exc)
            expired = tracker_lifecycle.update(valid, params.frame_timestamp_ms / 1000,
                                               getattr(params, 'tracker_timeout', 0.))
            backend.expire_trackers(expired)
            params.tracker_status = tracker_lifecycle.summary()
            calibration = None
            if tracking is not None and any(valid.values()):
                options = {} if getattr(params, 'preview_skeleton', False) else {'valid_trackers': valid}
                updated = backend.updatepose(params, tracking.pose, tracking.rotations, tracking.hands, **options)
                if updated is False:
                    params.pose_status = 'Backend rejeitou pose: sem nova atualizacao'
                else:
                    params.pose_status = 'Pose válida' if all(valid.values()) else 'Rastreamento parcial'
                    calibration = tracking.calibration
            elif tracking is not None and tracking.reasons:
                params.pose_status = next(iter(tracking.reasons.values()))
            if calibration is not None:
                params.pose3d_og = calibration
            elif hasattr(params, 'pose3d_og'):
                del params.pose3d_og
            tracker_seconds = time.perf_counter() - tracker_start

            img = cv2.cvtColor(img,cv2.COLOR_RGB2BGR)       #convert back to bgr and draw the pose
            if fingers is not None:
                draw_hands(img, finger_frames)
                cv2.putText(img, fingers.status, (10, 156), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 0), 1)
            draw_observation(img, image_landmarks, params.body_observation, mp_pose.POSE_CONNECTIONS)
            cv2.putText(img, params.body_status, (10, 134), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 0), 1)
            # Exibe a janela anterior: o ciclo atual só termina após imshow/waitKey.
            summary = metrics.summary()
            # Duas linhas cabem na resolução padrão; desenha somente na cópia de exibição.
            first_line, second_line = summary.split(' | idade:', 1) if ' | idade:' in summary else (summary, '')
            for row, text in enumerate((first_line, 'idade:' + second_line if second_line else '')):
                cv2.putText(img, text, (10, 22 + row * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
            if params.pose_status != 'Pose válida':
                cv2.putText(img, params.pose_status, (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
            else:
                landmarks = results.pose_world_landmarks.landmark
                visibility = f'Vis tornozelos E:{float(landmarks[27].visibility):.2f} D:{float(landmarks[28].visibility):.2f}'
                cv2.putText(img, visibility, (10, 66), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.putText(img, params.tracker_status, (10, 112), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
            if is_video:
                cv2.putText(img, camera_thread.status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
                preview = img.copy()
                preview_original = original.copy()
                preview_settings = settings
                preview_preprocess_ms = preprocess_ms

            cv2.imshow("out", comparison_view(original, img, settings, preprocess_ms))
            key = cv2.waitKey(1)
            cycle_end = time.perf_counter()
            metrics.add(capture=capture_seconds, age=frame_age, pose=pose_seconds,
                        trackers=tracker_seconds, cycle=cycle_end - cycle_start)
            if params.log_frametime:
                print('INFO: ' + metrics.summary() + ' | ' + params.lighting_status)
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
        if fingers is not None:
            try:
                fingers.close()
            except Exception as exc:
                print('WARNING: Falha ao finalizar maos: ' + str(exc))
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
        with mp.solutions.hands.Hands(max_num_hands=2) as detector:
            result = detector.process(np.zeros((120, 160, 3), dtype=np.uint8))
            assert not result.multi_hand_landmarks
        print('Runtime OK: OpenCV, MediaPipe Pose, Hands e modelos disponíveis')
    else:
        main()

