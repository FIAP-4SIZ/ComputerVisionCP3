import tkinter as tk
import sys
import pickle
from scrollable_panel import ScrollablePanel
from tkinter import filedialog

from sys import platform

def set_advanced(window,param):
    param["switch_advanced"] = True
    window.quit()

def getparams():
    
    try:
        param = pickle.load(open("params.p","rb"))
    except:
        param = {}
        
    if "camid" not in param:
        param["camid"] = 'http://192.168.1.103:8080/video'
    if "imgsize" not in param:
        param["imgsize"] = 640
    if "neckoffset" not in param:
        param["neckoffset"] = [0.0, -0.2, 0.1]
    if "prevskel" not in param:
        param["prevskel"] = False
    if "waithmd" not in param:
        param["waithmd"] = False
    if "rotateclock" not in param:
        param["rotateclock"] = False
    if "rotatecclock" not in param: 
        param["rotatecclock"] = False
    if "rotate" not in param:
        param["rotate"] = None
    if "camlatency" not in param:
        param["camlatency"] = 0.05
    if "smooth" not in param:
        param["smooth"] = 0.5
    if "feetrot" not in param:
        param["feetrot"] = False
    if "calib_scale" not in param:
        param["calib_scale"] = True
    if "calib_tilt" not in param:
        param["calib_tilt"] = True
    if "calib_rot" not in param:
        param["calib_rot"] = True
    param.setdefault("track_fingers", False)
    if "use_hands" not in param:
        param["use_hands"] = False
    if "ignore_hip" not in param:
        param["ignore_hip"] = False
    if "camera_settings" not in param:
        param["camera_settings"] = False
    if "camera_width" not in param:
        param["camera_width"] = 640
    if "camera_height" not in param:
        param["camera_height"] = 480
    if "model_complexity" not in param:
        param["model_complexity"] = 1
    if "smooth_landmarks" not in param:
        param["smooth_landmarks"] = True
    if "min_tracking_confidence" not in param:
        param["min_tracking_confidence"] = 0.5
    if "static_image" not in param:
        param["static_image"] = False    
    if "backend" not in param:
        param["backend"] = 1
    if "backend_ip" not in param:
        param["backend_ip"] = "127.0.0.1"
    if "backend_port" not in param:
        param["backend_port"] = 9000
    if "advanced" not in param:
        param["advanced"] = False
    if "webui" not in param:
        param["webui"] = False
    param.setdefault('input_mode', 'camera')
    param.setdefault('video_path', '')
       
    window = tk.Tk()
    window.title('Configuração do rastreamento corporal')
    content = ScrollablePanel(window).content

    def on_close():
        window.destroy()
        sys.exit("INFO: Exiting... You can close the window after 10 seconds.")

    window.protocol("WM_DELETE_WINDOW", on_close)

    input_mode = tk.StringVar(value=param['input_mode'])
    tk.Label(content, text='Entrada para análise de movimento:').pack()
    tk.Radiobutton(content, text='Câmera ao vivo', variable=input_mode, value='camera').pack()
    tk.Radiobutton(content, text='Arquivo de vídeo', variable=input_mode, value='video').pack()
    video_path = tk.StringVar(value=param['video_path'])
    tk.Entry(content, textvariable=video_path, width=50).pack()

    def select_video():
        path = filedialog.askopenfilename(title='Selecionar vídeo', filetypes=[
            ('Vídeos', '*.mp4 *.avi *.mov *.mkv *.webm *.m4v *.mpg *.mpeg'), ('Todos', '*.*')])
        if path:
            video_path.set(path)
            input_mode.set('video')
            varbackend.set(0)
            show_hide_backend_options()

    tk.Button(content, text='Selecionar vídeo...', command=select_video).pack()

    if not param["advanced"]:
        tk.Label(content, text='Para IP Webcam no Android, use http://<ip>:8080/video.\nPara uma webcam USB, tente 0, 1 ou 2 até abrir a câmera.', width = 50).pack()

    tk.Label(content, text='IP ou número da câmera:', width = 50).pack()
    camid = tk.Entry(content, width = 50)
    camid.pack()
    camid.insert(0,param["camid"])
    
    if not param["advanced"]:
        tk.Label(content, text='Resoluções maiores podem reduzir o desempenho.\nMantenha o padrão, salvo se houver problemas na captura.', width = 50).pack()

    tk.Label(content, text='Largura da câmera:', width = 50).pack()
    camwidth = tk.Entry(content, width = 20)
    camwidth.pack()
    camwidth.insert(0,param["camera_width"])
    
    tk.Label(content, text='Altura da câmera:', width = 50).pack()
    camheight = tk.Entry(content, width = 20)
    camheight.pack()
    camheight.insert(0,param["camera_height"])
    
    if platform == "win32":
        if not param["advanced"]:
            tk.Label(content, text='Abrir as configurações pode alterar o comportamento da câmera.\nSe houver problemas, teste esta opção ligada e desligada\ne confira o número da câmera.', width = 55).pack()
    
    varcamsettings = tk.IntVar(value = param["camera_settings"])
    cam_settings_check = tk.Checkbutton(content, text = 'Abrir configurações da câmera', variable = varcamsettings)
    if platform == "win32":
        cam_settings_check.pack()

    if param["advanced"]:
        tk.Label(content, text='Tamanho máximo da imagem:', width = 50).pack()
        maximgsize = tk.Entry(content, width = 20)
        maximgsize.pack()
        maximgsize.insert(0,param["imgsize"])

    tk.Label(content, text="-"*50, width = 50).pack()

    varfingers = tk.IntVar(value=param["track_fingers"])
    tk.Checkbutton(content, text="Rastrear dedos (OSC requer avatar configurado)", variable=varfingers).pack()

    varfeet = tk.IntVar(value = param["feetrot"])
    rot_feet_check = tk.Checkbutton(content, text = 'Ativar rotação experimental dos pés', variable = varfeet)
    rot_feet_check.pack()
    
    if not param["advanced"]:
        tk.Label(content, text='Desative o quadril somente se outro programa,\ncomo owoTrack, já fornecer esse rastreador.', width = 55).pack()
    
    varhip = tk.IntVar(value = param["ignore_hip"])
    hip_check = tk.Checkbutton(content, text = 'Desativar rastreador do quadril', variable = varhip)
    hip_check.pack()
    
    tk.Label(content, text="-"*50, width = 50).pack()
    
    if param["advanced"]:
        
        varhand = tk.IntVar(value = param["use_hands"])
        hand_check = tk.Checkbutton(content, text = 'Experimental: criar rastreadores dos punhos', variable = varhand)
        hand_check.pack()
        
        varskel = tk.IntVar(value = param["prevskel"])
        skeleton_check = tk.Checkbutton(content, text = 'Experimental: visualizar esqueleto em VR', variable = varskel)
        skeleton_check.pack()

        tk.Label(content, text="-"*50, width = 50).pack()

        tk.Label(content, text='[AVANÇADO] Parâmetros do MediaPipe:', width = 50).pack()

        tk.Label(content, text='Complexidade do modelo:', width = 50).pack()
        modelc = tk.Entry(content, width = 20)
        modelc.pack()
        modelc.insert(0,param["model_complexity"])
        
        varmsmooth = tk.IntVar(value = param["smooth_landmarks"])
        msmooth_check = tk.Checkbutton(content, text = 'Suavizar pontos corporais', variable = varmsmooth)
        msmooth_check.pack()
        
        tk.Label(content, text='Confiança mínima do rastreamento:', width = 50).pack()
        trackc = tk.Entry(content, width = 20)
        trackc.pack()
        trackc.insert(0,param["min_tracking_confidence"])
        
        varstatic = tk.IntVar(value = param["static_image"])
        static_check = tk.Checkbutton(content, text = 'Modo de imagem estática', variable = varstatic)
        static_check.pack()

    backend_frame = tk.Frame(content)
    backend_selection_frame = tk.Frame(backend_frame)
    backend_options_frame = tk.Frame(backend_frame)

    varbackend = tk.IntVar(value = param["backend"])

    def show_hide_backend_options():
        if varbackend.get() == 2:
            backend_options_frame.pack(side = tk.BOTTOM)
        else:
            backend_options_frame.pack_forget()

    tk.Label(backend_selection_frame, text='Destino: ').pack(side = tk.LEFT)
    tk.Radiobutton(backend_selection_frame, text='Somente análise', variable=varbackend, value=0, command=show_hide_backend_options).pack(side=tk.LEFT)
    tk.Radiobutton(backend_selection_frame, text="SteamVR", variable = varbackend, value = 1, command = show_hide_backend_options).pack(side = tk.LEFT)
    tk.Radiobutton(backend_selection_frame, text='VRChat OSC',  variable = varbackend, value = 2, command = show_hide_backend_options).pack(side = tk.LEFT)
    backend_selection_frame.pack(side = tk.TOP)

    tk.Label(backend_options_frame, text='IP/porta:').pack(side = tk.LEFT)
    backend_ip = tk.Entry(backend_options_frame, width = 15)
    backend_ip.insert(0, param["backend_ip"])
    backend_ip.pack(side = tk.LEFT)
    backend_port = tk.Entry(backend_options_frame, width = 5)
    backend_port.insert(0, param["backend_port"])
    backend_port.pack(side = tk.LEFT)

    show_hide_backend_options()
    backend_frame.pack()

    tk.Label(content, text="-"*50, width = 50).pack()

    varwebui = tk.IntVar(value = param["webui"])
    webui_check = tk.Checkbutton(content, text = 'Ativar interface web para controle por outro dispositivo', variable = varwebui)
    webui_check.pack()
    
    param["switch_advanced"] = False
    if param["advanced"]:
        tk.Label(content, text="-"*50, width = 50).pack()
        tk.Button(content, text='Desativar modo avançado', command=lambda *args: set_advanced(window,param)).pack()
    else:
        tk.Button(content, text='Ativar modo avançado', command=lambda *args: set_advanced(window,param)).pack()

    tk.Button(content, text='Salvar e continuar', command=window.quit).pack()

    window.mainloop()

#----------------------------------------------------------"

    cameraid = camid.get()
    #hmd_to_neck_offset = [float(val) for val in hmdoffsettext.get().split(" ")]
    
    dont_wait_hmd = False #bool(varhmdwait.get()) 
    
    #camera_latency = float(camlatencytext.get())
    #smoothing = float(smoothingtext.get())
    feet_rotation = bool(varfeet.get())
    
    ignore_hip = bool(varhip.get())
    camera_settings = bool(varcamsettings.get())
    camera_height = camheight.get()
    camera_width = camwidth.get()
    
    backend = int(varbackend.get())
    backend_ip_set = backend_ip.get()
    backend_port_set = int(backend_port.get())
    
    webui = bool(varwebui.get())
    
    if param["advanced"]:
        maximgsize = int(maximgsize.get())
        
        preview_skeleton = bool(varskel.get())
        use_hands = bool(varhand.get())
        
        mp_smoothing = bool(varmsmooth.get())
        model_complexity = int(modelc.get())
        min_tracking_confidence = float(trackc.get())
        static_image = bool(varstatic.get())
        
    else:
        maximgsize = 640
        
        preview_skeleton = False
        use_hands = False
        
        mp_smoothing = True
        model_complexity = 1
        min_tracking_confidence = 0.5
        static_image = False

    switch_advanced = param["switch_advanced"]

    advanced = param["advanced"]

    selected_mode = input_mode.get()
    selected_video = video_path.get()
    param = {}
    param['input_mode'] = selected_mode
    param['video_path'] = selected_video
    param["camid"] = cameraid
    param["imgsize"] = maximgsize
    #param["neckoffset"] = hmd_to_neck_offset
    param["prevskel"] = preview_skeleton
    param["waithmd"] = dont_wait_hmd

    #param["smooth"] = smoothing
    #param["camlatency"] = camera_latency
    param["feetrot"] = feet_rotation
    param["use_hands"] = use_hands
    param["track_fingers"] = bool(varfingers.get())
    param["ignore_hip"] = ignore_hip
    
    param["camera_settings"] = camera_settings
    param["camera_height"] = camera_height
    param["camera_width"] = camera_width
    
    param["model_complexity"] = model_complexity
    param["smooth_landmarks"] = mp_smoothing
    param["static_image"] = static_image
    param["min_tracking_confidence"] = min_tracking_confidence
    param["backend"] = backend
    param["backend_ip"] = backend_ip_set
    param["backend_port"] = backend_port_set
    param["webui"] = webui
    
    if switch_advanced:
        param["advanced"] = not advanced
    else:
        param["advanced"] = advanced
    
    pickle.dump(param,open("params.p","wb"))
    
    window.destroy()
    
    if switch_advanced:
        return None
    else:
        return param

if __name__ == "__main__":
    print(getparams())
