"""Imagem de mão → MediaPipe real → 31 ossos → decoder C++ compilado.

Valida o contrato; a posição global usada no teste é uma origem sintética.
Não é fallback do rastreador nem teste de movimento no VRChat.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from urllib.request import Request,urlopen
import cv2
import mediapipe as mp
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from finger_tracking import FingerTracking
from steamvr_skeleton import skeleton_transforms,transform_camera
from steamvr_protocol import encode_frame

REFERENCE_URL='https://storage.googleapis.com/mediapipe-assets/right_hands.jpg'
REFERENCE_HASH='4b5134daa4cb60465535239535f9f74c2842aba3aa5fd30bf04ef5678f93d87f'


def validate(image_path,probe,left_half=False):
    original=cv2.imread(str(image_path))
    if original is None:raise ValueError('Imagem inválida')
    rgb=cv2.cvtColor(original,cv2.COLOR_BGR2RGB)
    if left_half:rgb=rgb[:,:rgb.shape[1]//2].copy()
    states=[]
    with mp.solutions.hands.Hands(static_image_mode=True,max_num_hands=2) as detector:
        tracker=FingerTracking(detector)
        for _ in range(3):
            frames=tracker.process(rgb)
            states.append(sorted(frames))
    if not frames:raise ValueError('Nenhuma mão confirmada; não foi gerado esqueleto artificial')
    params=SimpleNamespace(global_rot_x=Rotation.identity(),global_rot_y=Rotation.identity(),global_rot_z=Rotation.identity())
    results=[]
    for side,frame in frames.items():
        wrist,bones=skeleton_transforms(transform_camera(frame.world_points,params),side)
        quaternion=Rotation.from_matrix(wrist).as_quat()
        # Somente fixture de transporte: produção usa punho observado pelo Pose.
        pose=np.r_[np.zeros(3),quaternion[[3,0,1,2]]]
        packet=encode_frame(0 if side=='Left' else 1,1,pose,bones)
        native=subprocess.run([str(Path(probe).resolve())],input=packet,capture_output=True,timeout=10)
        if native.returncode:
            raise ValueError('Decoder nativo rejeitou o pacote: '+native.stderr.decode('utf-8',errors='replace'))
        results.append({'side':side,'score':frame.score,'bone_count':len(bones),'packet_bytes':len(packet),
                        'native_reply':native.stdout.decode('ascii').strip()})
    return {'mediapipe':mp.__version__,'image_sha256':hashlib.sha256(Path(image_path).read_bytes()).hexdigest(),
            'left_half':left_half,'states':states,'hands':results,'vrchat_tested':False,
            'note':'Imagem estática repetida; origem global sintética só no teste. Não mede precisão, jitter ou FPS.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--image',type=Path)
    group.add_argument('--download-reference',action='store_true',help='Baixar imagem pública MediaPipe e verificar SHA-256 fixo; recortar metade esquerda em memória.')
    parser.add_argument('--left-half',action='store_true')
    parser.add_argument('--probe',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as directory:
        path=args.image
        if args.download_reference:
            with urlopen(Request(REFERENCE_URL,headers={'User-Agent':'MediaPipe-FIAP-integration-test'}),timeout=30) as response:
                data=response.read(1_000_001)
            if len(data)>1_000_000 or hashlib.sha256(data).hexdigest()!=REFERENCE_HASH:
                raise ValueError('Hash/tamanho da referência divergiu; teste interrompido')
            path=Path(directory)/'right_hands.jpg';path.write_bytes(data)
        result=validate(path,args.probe,args.left_half or args.download_reference)
        if args.download_reference:result['reference_url']=REFERENCE_URL
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('MediaPipe real e decoder nativo aprovados. Resultado: '+str(args.output))


if __name__=='__main__':main()
