"""Transporte local para o driver próprio. Sem dependência de Python OpenVR."""
import math
from numbers import Real
import socket
import struct
import time

PORT=39570
BONE_COUNT=31
PACKET_SIZE=916


class DriverConnectionError(ValueError):
    pass


def uint32(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError('Inteiro uint32 inválido')
    return value


def transform(values, limit):
    try:
        values=list(values)
        if any(isinstance(v,bool) or not isinstance(v,Real) for v in values):
            raise ValueError('Coordenadas devem ser números')
        values=[float(v) for v in values]
    except (TypeError,OverflowError) as exc:
        raise ValueError('Transformação inválida') from exc
    if len(values)!=7 or any(not math.isfinite(v) for v in values):
        raise ValueError('Transformação deve conter xyz e quaternion wxyz finitos')
    if any(abs(v)>limit for v in values[:3]) or not math.isclose(sum(v*v for v in values[3:]),1,abs_tol=.001):
        raise ValueError('Posição fora dos limites ou quaternion não unitário')
    return values


def encode_frame(side, sequence, pose=None, bones=None, valid=True):
    if type(side) is not int or side not in (0,1) or type(valid) is not bool:
        raise ValueError('Lado/validade inválidos')
    header=struct.pack('<8sIII',b'MPVRH001',side,uint32(sequence),int(valid))
    if not valid:
        return header+bytes(PACKET_SIZE-len(header))
    pose=transform(pose,10)
    try:
        bones=list(bones)
    except TypeError as exc:
        raise ValueError('Esperados ossos OpenVR') from exc
    if len(bones)!=BONE_COUNT:
        raise ValueError('Esperados 31 ossos OpenVR')
    bones=[transform(bone,1) for bone in bones]
    if any(abs(v)>1e-6 for v in bones[0][:3]) or any(abs(v)>1e-6 for v in bones[0][4:]) or abs(abs(bones[0][3])-1)>1e-6:
        raise ValueError('Root deve ser identidade')
    return header+struct.pack('<224f',*(pose+[v for bone in bones for v in bone]))


def control(command, value=0):
    if type(command) is not int or command not in (1,2,3):
        raise ValueError('Comando inválido')
    uint32(value)
    if (command==1 and value>500) or (command in (2,3) and value!=0):
        raise ValueError('Valor de comando inválido')
    return struct.pack('<8sII',b'MPVRC001',command,value)


def decode_status(data):
    if len(data)!=20:
        raise DriverConnectionError('Resposta incompleta do driver SteamVR')
    magic,version,mask,hmd=struct.unpack('<8sIII',data)
    if magic!=b'MPVRA001' or version!=1 or mask>3 or hmd>1:
        raise DriverConnectionError('Versão ou resposta do driver SteamVR incompatível')
    return dict(protocol=version,tracked_mask=mask,hmd_valid=bool(hmd))


def decode_head_pose(data):
    if len(data)!=60:raise DriverConnectionError('Resposta de pose HMD incompleta; atualize o driver')
    magic,valid,*matrix=struct.unpack('<8sI12f',data)
    if magic!=b'MPVRP001' or valid!=1 or not all(math.isfinite(v) for v in matrix):
        raise DriverConnectionError('Pose HMD inválida ou não disponível')
    return [matrix[i:i+4] for i in range(0,12,4)]


class SteamVRHandsClient:
    def __init__(self, port=PORT, timeout=1.):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Porta SteamVR inválida')
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            self.socket.settimeout(timeout)
            self.socket.connect(('127.0.0.1',port))
        except Exception:
            self.socket.close()
            raise
        # Relógio do SO compartilhado entre processos; novo remetente continua
        # depois do anterior. Incremento local evita duplicatas no mesmo ms.
        seed=int(time.monotonic()*1000)&0xffffffff
        self.sequences=[(seed-1)&0xffffffff]*2

    def status(self):
        try:
            self.socket.send(control(2))
            return decode_status(self.socket.recv(1024))
        except OSError as exc:
            raise DriverConnectionError('Driver de mãos não respondeu. Inicie SteamVR com o addon mediapipe_hands.') from exc

    def send(self, side, pose=None, bones=None, valid=True):
        if type(side) is not int or side not in (0,1):
            raise ValueError('Lado inválido')
        now=int(time.monotonic()*1000)&0xffffffff
        previous=self.sequences[side]
        difference=(now-previous)&0xffffffff
        sequence=now if 0<difference<0x80000000 else (previous+1)&0xffffffff
        packet=encode_frame(side,sequence,pose,bones,valid)
        self.socket.send(packet)
        self.sequences[side]=sequence

    def head_pose(self):
        try:
            self.socket.send(control(3))
            return decode_head_pose(self.socket.recv(1024))
        except OSError as exc:raise DriverConnectionError('HMD não respondeu à consulta de pose; atualize/reinicie o driver') from exc

    def invalidate(self):
        for side in (0,1):self.send(side,valid=False)

    def confirm(self, milliseconds=300):
        self.socket.send(control(1,milliseconds))

    def close(self):
        self.socket.close()
