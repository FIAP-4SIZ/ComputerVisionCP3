import time
from abc import ABC, abstractmethod
from helpers import  sendToSteamVR
from scipy.spatial.transform import Rotation as R
from pythonosc import osc_bundle_builder
from pythonosc import osc_message_builder
from pythonosc import udp_client

from helpers import shutdown
from pose_validation import valid_tracker_data, valid_alignment
from independent_trackers import NAMES, JOINTS, enabled_names, tracker_mask
from osc_body import EXTRA_IDS
import numpy as np

class Backend(ABC):

    def expire_trackers(self, names):
        """Expiração local; não inventa um comando de desativação no receptor VR."""
        pass

    def reset(self):
        """Reinicia estado temporal, quando o backend possui histórico local."""
        pass

    @abstractmethod
    def onparamchanged(self, params):
        ...

    @abstractmethod
    def connect(self, params):
        ...

    @abstractmethod
    def updatepose(self, params, pose3d, rots, hand_rots, valid_trackers=None):
        ...

    @abstractmethod
    def disconnect(self):
        ...

class DummyBackend(Backend):

    def __init__(self, **kwargs):
        pass

    def onparamchanged(self, params):
        pass

    def connect(self, params):
        pass

    def updatepose(self, params, pose3d, rots, hand_rots, valid_trackers=None):
        return True

    def disconnect(self):
        pass

class SteamVRBackend(Backend):

    def __init__(self, **kwargs):
        pass

    def onparamchanged(self, params):
        resp = sendToSteamVR(f"settings 50 {params.smoothing} {params.additional_smoothing}")
        if resp is None:
            print("ERROR: Could not connect to SteamVR after 10 tries! Launch SteamVR and try again.")
            shutdown(params)
            
    def connect(self, params):
        print("Connecting to SteamVR")

        #ask the driver, how many devices are connected to ensure we dont add additional trackers
        #in case we restart the program
        numtrackers = sendToSteamVR("numtrackers")
        if numtrackers is None:
            print("ERROR: Could not connect to SteamVR after 10 tries! Launch SteamVR and try again.")
            shutdown(params)

        numtrackers = int(numtrackers[2])

        #games use 3 trackers, but we can also send the entire skeleton if we want to look at how it works
        totaltrackers = 23 if params.preview_skeleton else  3
        if params.use_hands:
            totaltrackers = 5
        if params.ignore_hip:
            totaltrackers -= 1

        roles = ["TrackerRole_Waist", "TrackerRole_RightFoot", "TrackerRole_LeftFoot"]

        if params.ignore_hip and not params.preview_skeleton:
            del roles[0]

        if params.use_hands:
            roles.append("TrackerRole_Handed")
            roles.append("TrackerRole_Handed")

        for i in range(len(roles),totaltrackers):
            roles.append("None")

        for i in range(numtrackers,totaltrackers):
            #sending addtracker to our driver will... add a tracker. to our driver.
            resp = sendToSteamVR(f"addtracker MPTracker{i} {roles[i]}")
            if resp is None:
                print("ERROR: Could not connect to SteamVR after 10 tries! Launch SteamVR and try again.")
                shutdown(params)

        resp = sendToSteamVR(f"settings 50 {params.smoothing} {params.additional_smoothing}")
        if resp is None:
            print("ERROR: Could not connect to SteamVR after 10 tries! Launch SteamVR and try again.")
            shutdown(params)

    def updatepose(self, params, pose3d, rots, hand_rots, valid_trackers=None):
        try:
            mask = tracker_mask(params, valid_trackers)
        except ValueError:
            return False
        if params.preview_skeleton and valid_trackers is not None:
            return False
        if not any(mask.values()):
            return True
        if hand_rots is None and any(mask.get(name, False) for name in NAMES[3:]):
            return False
        if not valid_tracker_data(pose3d, rots, hand_rots) or not valid_alignment(params):
            return False
        pose3d = np.asarray(pose3d, dtype=float)
        array = sendToSteamVR("getdevicepose 0")        #get hmd data to allign our skeleton to

        if array is None or len(array) < 10:
            print("ERROR: Could not connect to SteamVR after 10 tries! Launch SteamVR and try again.")
            shutdown(params)

        try:
            headsetpos = [float(array[3]), float(array[4]), float(array[5])]
            headsetquat = [float(array[7]), float(array[8]), float(array[9]), float(array[6])]
            if not np.isfinite(headsetpos + headsetquat).all():
                return False
            headsetrot = R.from_quat(headsetquat)
        except (ValueError, TypeError):
            return False

        neckoffset = headsetrot.apply(np.asarray(params.hmd_to_neck_offset, dtype=float))   #the neck position seems to be the best point to allign to, as its well defined on
                                                            #the skeleton (unlike the eyes/nose, which jump around) and can be calculated from hmd.

        if params.recalibrate:
            print("INFO: frame to recalibrate")

        else:
            pose3d = pose3d * float(params.posescale)     #rescale skeleton to calibrated height
            #print(pose3d)
            offset = pose3d[7] - (headsetpos+neckoffset)    #calculate the position of the skeleton
            if not np.isfinite(pose3d).all() or not np.isfinite(offset).all():
                return False
            if not params.preview_skeleton:
                # IDs acompanham a ordem dos dispositivos criados no connect().
                for device_id, name in enumerate(enabled_names(params)):
                    if not mask[name]:
                        continue
                    index = NAMES.index(name)
                    quaternion = rots[index] if index < 3 else hand_rots[index - 3]
                    joint = pose3d[JOINTS[name]] - offset
                    sendToSteamVR(f"updatepose {device_id} {joint[0]} {joint[1]} {joint[2]} {quaternion[3]} {quaternion[0]} {quaternion[1]} {quaternion[2]} {params.camera_latency} 0.8")
            else:
                for i in range(23):
                    joint = pose3d[i] - offset      #if previewing skeleton, send the position of each keypoint to steamvr without rotation
                    sendToSteamVR(f"updatepose {i} {joint[0]} {joint[1]} {joint[2] - 2} 1 0 0 0 {params.camera_latency} 0.8")
        return True

    def disconnect(self):
        pass

def osc_build_msg(name, position_or_rotation, args):
    builder = osc_message_builder.OscMessageBuilder(address=f"/tracking/trackers/{name}/{position_or_rotation}")
    builder.add_arg(float(args[0]))
    builder.add_arg(float(args[1]))
    builder.add_arg(float(args[2]))
    return builder.build()

def osc_build_bundle(trackers):
    builder = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)
    builder.add_content(osc_build_msg(trackers[0]['name'], "position", trackers[0]['position']))
    for tracker in trackers[1:]:
        builder.add_content(osc_build_msg(tracker['name'], "position", tracker['position']))
        builder.add_content(osc_build_msg(tracker['name'], "rotation", tracker['rotation']))
    return builder.build()

class VRChatOSCBackend(Backend):

    def __init__(self, **kwargs):
        # Para cada tracker: posição e âncora do pescoço filtradas juntas.
        self.history = {}

    def onparamchanged(self, params):
        pass

    def reset(self):
        self.history.clear()

    def expire_trackers(self, names):
        for name in names:
            self.history.pop(name, None)

    def connect(self, params):
        if hasattr(params, 'backend_ip') and hasattr(params, 'backend_port'):
            self.client = udp_client.UDPClient(params.backend_ip, params.backend_port)
        else:
            self.client = udp_client.UDPClient('127.0.0.1', 9000)

    def updatepose(self, params, pose3d, rots, hand_rots, valid_trackers=None, extra_trackers=None):
        if not valid_tracker_data(pose3d, rots, hand_rots) or not valid_alignment(params):
            return False
        try:
            mask = tracker_mask(params, valid_trackers)
            weight = float(params.additional_smoothing)
        except (ValueError, TypeError):
            return False
        if not np.isfinite(weight) or not 0 <= weight <= 1:
            return False
        if params.recalibrate or params.preview_skeleton:
            return True  # Preview rígido não é parte da API OSC Trackers.
        pose = np.asarray(pose3d, dtype=float)
        scale = float(params.posescale)
        neckoffset = np.asarray(params.hmd_to_neck_offset, dtype=float)
        trackers = [{'name': 'head', 'position': [0, 0, 0]}]
        next_history = {}
        candidates = []
        for index, name in enumerate(NAMES[:3]):
            if not mask.get(name, False):
                continue
            candidates.append((name, str(index + 1), pose[[JOINTS[name], 7]].copy(), rots[index]))
        if extra_trackers is not None:
            if not isinstance(extra_trackers, dict) or set(extra_trackers) - set(EXTRA_IDS):
                return False
            for name in set(EXTRA_IDS) - set(extra_trackers):
                self.history.pop(name, None)
            try:
                for name, (pair, quaternion) in extra_trackers.items():
                    pair, quaternion = np.asarray(pair, dtype=float), np.asarray(quaternion, dtype=float)
                    if (pair.shape != (2, 3) or not np.isfinite(pair).all()
                            or quaternion.shape != (4,) or not np.isfinite(quaternion).all()
                            or not np.isclose(np.linalg.norm(quaternion), 1)):
                        return False
                    candidates.append((name, EXTRA_IDS[name], pair, quaternion))
            except (TypeError, ValueError):
                return False
        for name, tracker_id, pair, quaternion in candidates:
            if name in self.history:
                pair = self.history[name] * weight + pair * (1 - weight)
            scaled = pair * scale
            position = scaled[0] - (scaled[1] - neckoffset)
            if (not np.isfinite(pair).all() or not np.isfinite(position).all()
                    or np.any(np.abs(position) > np.finfo(np.float32).max)):
                return False
            position[2] *= -1
            rotation = R.from_quat(quaternion).as_euler('zxy', degrees=True)
            rotation = [-rotation[1], -rotation[2], rotation[0]]
            trackers.append({'name': tracker_id, 'position': position, 'rotation': rotation})
            next_history[name] = pair
        if len(trackers) > 1:
            self.client.send(osc_build_bundle(trackers))
            self.history.update(next_history)
        return True

    def disconnect(self):
        client = getattr(self, 'client', None)
        if client is not None:
            client.close()
            self.client = None
        self.reset()
