from init_gui import getparams
from scipy.spatial.transform import Rotation as R
import cv2
import json
import math
from dataclasses import asdict
from hand_quality import HandQualitySettings
from lighting import DEFAULT_LIGHTING, LightingSettings

class Parameters():
    def __init__(self) -> None:
        param = None
        while param == None:
            param = getparams()
        
        self.advanced = param["advanced"]
        self.input_mode = param.get('input_mode', 'camera')
        self.video_path = param.get('video_path', '')
        self.restart_input = False
        self.cancel_input = False
        self.input_status = ''
        self.min_visibility = .5
        self.pose_status = ''
        self.tracker_status = ''
        self.tracker_timeout = 0.0
        self.hand_quality = HandQualitySettings()
        self.lighting = DEFAULT_LIGHTING
        self.lighting_status = 'Original; ajustes desligados'
        
        self.model = param["model_complexity"]
        self.smooth_landmarks = param["smooth_landmarks"]
        self.min_tracking_confidence = param["min_tracking_confidence"]
        self.static_image = param["static_image"]

        #PARAMETERS:
        self.maximgsize = param["imgsize"]               #to prevent working with huge images, images that have one axis larger than this value will be downscaled.
        self.cameraid = param["camid"]                    #to use with an usb or virtual webcam. If 0 doesnt work/opens wrong camera, try numbers 1-5 or so
        #cameraid = "http://192.168.1.102:8080/video"   #to use ip webcam, uncomment this line and change to your ip
        self.hmd_to_neck_offset = [0,-0.2,0.1]    #offset of your hmd to the base of your neck, to ensure the tracking is stable even if you look around. Default is 20cm down, 10cm back.
        self.preview_skeleton = param["prevskel"]             #if True, whole skeleton will appear in vr 2 meters in front of you. Good to visualize if everything is working
        self.dont_wait_hmd = param["waithmd"]                  #dont wait for movement from hmd, start inference immediately.
        self.rotate_image = 0 # cv2.ROTATE_90_CLOCKWISE # cv2.ROTATE_90_COUTERCLOCKWISE # cv2.ROTATE_180 # None # if you want, rotate the camera
        self.camera_latency = 0.0
        self.smoothing_1 = 0.0
        self.additional_smoothing_1 = 0.7
        self.smoothing_2 = 0.5
        self.additional_smoothing_2 = 0.9
        self.feet_rotation = param["feetrot"]
        self.use_hands = param["use_hands"]
        self.track_fingers = param.get("track_fingers", False)
        self.osc_full_body = param.get('osc_full_body', False)
        self.osc_hand_profile = param.get('osc_hand_profile', '')
        self.ignore_hip = param["ignore_hip"]
        
        self.camera_settings = param["camera_settings"]
        self.camera_width = param["camera_width"]
        self.camera_height = param["camera_height"]

        self.backend = param["backend"]
        self.backend_ip = param["backend_ip"]
        self.backend_port = param["backend_port"]
        
        self.webui = param["webui"]

        self.calib_rot = True
        self.calib_tilt = True
        self.calib_scale = True

        self.recalibrate = False
        
        #rotations in degrees!
        self.euler_rot_y = 180
        self.euler_rot_x = 90
        self.euler_rot_z = 180

        self.posescale = 1     

        self.exit_ready = False

        self.img_rot_dict = {0: None, 1: cv2.ROTATE_90_CLOCKWISE, 2: cv2.ROTATE_180, 3: cv2.ROTATE_90_COUNTERCLOCKWISE}
        self.img_rot_dict_rev = {None: 0, cv2.ROTATE_90_CLOCKWISE: 1, cv2.ROTATE_180: 2, cv2.ROTATE_90_COUNTERCLOCKWISE: 3}

        self.paused = False
        
        self.flip = False
        
        self.log_frametime = False
        
        self.mirror = False

        self.load_params()
        
        self.global_rot_y = R.from_euler('y',self.euler_rot_y,degrees=True)     #default rotations, for 0 degrees around y and x
        self.global_rot_x = R.from_euler('x',self.euler_rot_x-90,degrees=True) 
        self.global_rot_z = R.from_euler('z',self.euler_rot_z-180,degrees=True) 
        
        self.smoothing = self.smoothing_1
        self.additional_smoothing = self.additional_smoothing_1
        
        #if advanced mode is disabled, always reset smoothing and camera latency to 0
        if not self.advanced:
            self.smoothing = 0.0
            self.smoothing_1 = 0.0
            self.camera_latency = 0.0
        
    

    def change_recalibrate(self):
        self.recalibrate = True

    def set_min_visibility(self, value):
        try:
            value = float(value)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError
        except (ValueError, TypeError):
            self.pose_status = 'Visibilidade deve estar entre 0 e 1'
            return False
        self.min_visibility = value
        return True

    def set_tracker_timeout(self, value):
        try:
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError
        except (ValueError, TypeError):
            return False
        self.tracker_timeout = value
        return True

    def set_hand_quality(self, score, pixels, frames, step):
        try:
            if any(isinstance(value, bool) for value in (score, pixels, frames, step)):
                raise ValueError
            count = float(frames)
            if not count.is_integer():
                raise ValueError
            self.hand_quality = HandQualitySettings(float(score), float(pixels), int(count), float(step))
        except (TypeError, ValueError, OverflowError):
            return False
        return True

    def set_lighting(self, mode='off', contrast=1., brightness=0., compare=False):
        try:
            if isinstance(contrast, bool) or isinstance(brightness, bool):
                raise ValueError
            settings = LightingSettings(mode, float(contrast), float(brightness), compare)
        except (ValueError, TypeError, OverflowError):
            return False
        self.lighting = settings  # Snapshot imutável, trocado de uma vez pela GUI.
        return True


    def rot_change_y(self, value):                                  #callback functions. Whenever the value on sliders are changed, they are called
        print(f"INFO: Changed y rotation value to {value}")
        self.euler_rot_y = value
        self.global_rot_y = R.from_euler('y',value,degrees=True)     #and the rotation is updated with the new value.
        

    def rot_change_x(self, value):
        print(f"INFO: Changed x rotation value to {value}")
        self.euler_rot_x = value
        self.global_rot_x = R.from_euler('x',value-90,degrees=True) 
        

    def rot_change_z(self, value):
        print(f"INFO: Changed z rotation value to {value}")
        self.euler_rot_z = value
        self.global_rot_z = R.from_euler('z',value-180,degrees=True) 
         

    def change_scale(self, value):
        print(f"INFO: Changed scale value to {value}")
        #posescale = value/50 + 0.5
        self.posescale = value


    def change_img_rot(self, val):
        print(f"INFO: Changed image rotation to {val*90} clockwise")
        self.rotate_image = self.img_rot_dict[val]


    def change_smoothing(self, val, paramid = 0):
        print(f"INFO: Changed smoothing value to {val}")
        self.smoothing = val
        
        if paramid == 1:
            self.smoothing_1 = val
        if paramid == 2:
            self.smoothing_2 = val
        

    def change_additional_smoothing(self, val, paramid = 0):
        print(f"INFO: Changed additional smoothing value to {val}")
        self.additional_smoothing = val

        if paramid == 1:
            self.additional_smoothing_1 = val
        if paramid == 2:
            self.additional_smoothing_2 = val


    def change_camera_latency(self, val):
        print(f"INFO: Changed camera latency to {val}")
        self.camera_latency = val


    def change_neck_offset(self,x,y,z):
        print(f"INFO: Hmd to neck offset changed to: [{x},{y},{z}]")
        self.hmd_to_neck_offset = [x,y,z]

    def change_mirror(self, mirror):
        print(f"INFO: Image mirror set to {mirror}")
        self.mirror = mirror


    def ready2exit(self):
        self.exit_ready = True


    def save_params(self):
        param = {}
        param['min_visibility'] = self.min_visibility
        param['tracker_timeout'] = self.tracker_timeout
        param['lighting'] = asdict(self.lighting)
        param['hand_quality'] = asdict(self.hand_quality)
        param["rotate"] = self.img_rot_dict_rev[self.rotate_image] 
        param["smooth1"] = self.smoothing_1
        param["smooth2"] = self.smoothing_2

        param["camlatency"] = self.camera_latency
        param["addsmooth1"] = self.additional_smoothing_1
        param["addsmooth2"] = self.additional_smoothing_2

        #if self.flip:
        param["roty"] = self.euler_rot_y
        param["rotx"] = self.euler_rot_x
        param["rotz"] = self.euler_rot_z
        param["scale"] = self.posescale
        
        param["calibrot"] = self.calib_rot
        param["calibtilt"] = self.calib_tilt
        param["calibscale"] = self.calib_scale
        
        param["flip"] = self.flip
        
        param["hmd_to_neck_offset"] = self.hmd_to_neck_offset
        
        param["mirror"] = self.mirror
        
        #print(param["roty"])
        
        with open("saved_params.json", "w") as f:
            json.dump(param, f)


    def load_params(self):

        try:
            with open("saved_params.json", "r") as f:
                param = json.load(f)
            self.set_min_visibility(param.get('min_visibility', .5))
            self.set_tracker_timeout(param.get('tracker_timeout', 0.))
            quality = param.get('hand_quality', {})
            if isinstance(quality, dict):
                try:
                    self.hand_quality = HandQualitySettings(**quality)
                except (TypeError, ValueError):
                    pass
            lighting = param.get('lighting', {})
            if isinstance(lighting, dict):
                try:
                    self.set_lighting(**lighting)
                except TypeError:
                    pass  # Configuração desconhecida não impede carregar os demais parâmetros.

            #print(param["roty"])

            self.rotate_image = self.img_rot_dict[param["rotate"]]
            self.smoothing_1 = param["smooth1"]
            self.smoothing_2 = param["smooth2"]
            self.camera_latency = param["camlatency"]
            self.additional_smoothing_1 = param["addsmooth1"]
            self.additional_smoothing_2 = param["addsmooth2"]

            self.euler_rot_y = param["roty"]
            self.euler_rot_x = param["rotx"]
            self.euler_rot_z = param["rotz"]
            self.posescale = param["scale"]
            
            self.calib_rot = param["calibrot"]
            self.calib_tilt = param["calibtilt"]
            self.calib_scale = param["calibscale"]
            
            self.mirror = param["mirror"]
            
            if self.advanced:
                self.hmd_to_neck_offset = param["hmd_to_neck_offset"]
            
            self.flip = param["flip"]
        except:
            print("INFO: Save file not found, will be created after you exit the program.")
 

if __name__ == "__main__":
    print("hehe")
