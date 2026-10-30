"""Corpo OSC original + mãos esqueléticas no driver OpenVR próprio."""
from backends import VRChatOSCBackend
from steamvr_protocol import SteamVRHandsClient,DriverConnectionError
from steamvr_skeleton import prepare_hand
from pose_validation import InvalidPose


class SteamVRHandsBackend(VRChatOSCBackend):
    def __init__(self):
        super().__init__()
        self.hands=None
        self._invalidated=True
        self.confirm_at=None
        self.status='SteamVR: aguardando driver'

    def connect(self,params):
        super().connect(params)
        try:
            self.hands=SteamVRHandsClient()
            status=self.hands.status()
            if not status['hmd_valid']:
                raise DriverConnectionError('SteamVR respondeu, mas o HMD não tem pose válida. Configure/inicie o HMD real ou virtual.')
            self._invalidated=False
            self.reset()
            params.read_hmd_pose=self.hands.head_pose
        except Exception as exc:
            if self.hands is not None:self.hands.close()
            self.hands=None
            super().disconnect()
            if isinstance(exc,OSError):raise DriverConnectionError('Não foi possível abrir a conexão com SteamVR: '+str(exc)) from exc
            raise

    def update_hands(self,params,frames,world,image,shape):
        labels=[]
        try:
            for side_index,side in enumerate(('Left','Right')):
                try:
                    if side not in frames:raise InvalidPose('Mão ausente')
                    pose,bones=prepare_hand(frames[side],world,image,shape,params)
                    self.hands.send(side_index,pose,bones)
                    labels.append(('ME' if side_index==0 else 'MD')+':ok')
                except (InvalidPose,ValueError,TypeError,AttributeError) as exc:
                    self.hands.send(side_index,valid=False)
                    labels.append(('ME' if side_index==0 else 'MD')+':'+str(exc))
            self._invalidated=False
            self.status='SteamVR | '+' | '.join(labels)
        except OSError as exc:
            raise DriverConnectionError('Falha ao enviar mãos ao SteamVR: '+str(exc)) from exc

    def request_confirmation(self,now):
        self.confirm_at=now+3.
        self.status='SteamVR: confirmação FBT em 3 s; volte ao VRChat em calibração'

    def tick(self,now):
        if self.confirm_at is not None and now>=self.confirm_at:
            self.confirm_at=None
            try:self.hands.confirm()
            except OSError as exc:raise DriverConnectionError('Não foi possível confirmar calibração SteamVR') from exc

    def reset(self):
        super().reset()
        self.confirm_at=None
        if self.hands is not None and not self._invalidated:
            try:self.hands.invalidate()
            except OSError as exc:raise DriverConnectionError('Não foi possível suspender as mãos SteamVR') from exc
            self._invalidated=True
        self.status='SteamVR: mãos suspensas/sem dados'

    def disconnect(self):
        try:
            if self.hands is not None:
                try:self.reset()
                except DriverConnectionError:
                    pass  # O driver ainda expira a última amostra em 500 ms.
                finally:self.hands.close();self.hands=None
        finally:
            super().disconnect()
