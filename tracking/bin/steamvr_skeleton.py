"""21 keypoints estimados → hierarquia OpenVR, em metros e espaço do pai."""
import numpy as np
from scipy.spatial.transform import Rotation
from body_observation import observe_body
from pose_validation import InvalidPose, valid_alignment

PARENTS=(-1,0,1,2,3,4,1,6,7,8,9,1,11,12,13,14,1,16,17,18,19,1,21,22,23,24,0,0,0,0,0)
CHAINS=((2,3,4,5),(6,7,8,9,10),(11,12,13,14,15),(16,17,18,19,20),(21,22,23,24,25))


def unit(vector):
    length=np.linalg.norm(vector)
    if not np.isfinite(length) or length<1e-7:
        raise InvalidPose('Geometria da mão degenerada')
    return vector/length


def skeleton_transforms(points,side):
    """Retorna orientação do punho e 31 transforms relativos aos pais.

    Root/punho têm a mesma origem. Quatro metacarpos intermediários são
    interpolações entre punho e MCP, não landmarks medidos. Auxiliares copiam
    pontas existentes. Eixo longitudinal dos dedos: +X esquerda, -X direita,
    conforme a convenção esquelética OpenVR.
    """
    points=np.asarray(points,dtype=float)
    if side not in ('Left','Right') or points.shape!=(21,3) or not np.isfinite(points).all() or np.max(np.abs(points))>1e3:
        raise InvalidPose('Dados espaciais da mão inválidos')
    z=-unit(points[9]-points[0])
    x=-unit(np.cross(points[5]-points[0],points[17]-points[0]))
    x=unit(x-np.dot(x,z)*z)
    y=unit(np.cross(z,x))
    wrist=np.column_stack((x,y,z))
    positions=np.zeros((31,3));positions[:2]=points[0]
    positions[2:6]=points[1:5]
    for start,base in ((6,5),(11,9),(16,13),(21,17)):
        positions[start]=(points[0]+points[base])/2
        positions[start+1:start+5]=points[base:base+4]
    for index,tip in enumerate((4,8,12,16,20),26):positions[index]=points[tip]
    global_rotations=np.repeat(wrist[None],31,axis=0)
    sign=1 if side=='Left' else -1
    for chain in CHAINS:
        for current,following in zip(chain,chain[1:]):
            bone_x=unit(positions[following]-positions[current])*sign
            bone_y=y-np.dot(y,bone_x)*bone_x
            if np.linalg.norm(bone_y)<1e-6:
                # Polegar pode alinhar-se à largura da palma. Referência
                # alternativa vem da normal OBSERVADA, não de posição fixa.
                bone_y=x-np.dot(x,bone_x)*bone_x
            bone_y=unit(bone_y)
            global_rotations[current]=np.column_stack((bone_x,bone_y,np.cross(bone_x,bone_y)))
        global_rotations[chain[-1]]=global_rotations[chain[-2]]
    for index,tip in enumerate((5,10,15,20,25),26):global_rotations[index]=global_rotations[tip]
    bones=np.zeros((31,7));bones[:,3]=1
    for index,parent in enumerate(PARENTS[1:],1):
        parent_rotation=global_rotations[parent]
        bones[index,:3]=parent_rotation.T@(positions[index]-positions[parent])
        q=Rotation.from_matrix(parent_rotation.T@global_rotations[index]).as_quat()
        bones[index,3:]=q[[3,0,1,2]]
    return wrist,bones


def transform_camera(points,params):
    points=np.asarray(points,dtype=float).copy()
    points[:,:2]*=-1
    for rotation in (params.global_rot_z,params.global_rot_x,params.global_rot_y):points=rotation.apply(points)
    return points


def prepare_hand(frame,world,image,shape,params):
    """Punho global requer Pose e correspondência com a mão detectada."""
    if not valid_alignment(params) or world is None or not hasattr(world,'__len__') or len(world)!=33:
        raise InvalidPose('Sem pose/alinhamento para posicionar o punho')
    if frame.side not in ('Left','Right'):
        raise InvalidPose('Lado de mão inválido')
    score=float(frame.score)
    minimum=getattr(getattr(params,'hand_quality',None),'min_handedness',.75)
    if isinstance(frame.score,bool) or not np.isfinite(score) or not minimum<=score<=1:
        raise InvalidPose('Confiança de mão insuficiente')
    wrist_index=15 if frame.side=='Left' else 16
    required=(11,12,wrist_index)
    threshold=getattr(params,'min_visibility',.5)
    visible=observe_body(image,threshold).visible
    if not set(required)<=visible:
        raise InvalidPose('Ombros ou punho fora do quadro/sem visibilidade')
    try:
        points=np.array([[world[i].x,world[i].y,world[i].z] for i in required],dtype=float)
        if any(not threshold<=float(world[i].visibility)<=1 for i in required):
            raise InvalidPose('Punho ou ombros sem visibilidade espacial')
        if not np.isfinite(points).all() or np.max(np.abs(points))>1e3:
            raise InvalidPose('Pose espacial inválida')
        pixels=np.asarray(frame.points,dtype=float)[:,:2]*[shape[1],shape[0]]
        if pixels.shape!=(21,2) or not np.isfinite(pixels).all():
            raise InvalidPose('Pontos de mão inválidos')
        palm=np.linalg.norm(pixels[5]-pixels[17])
        pose_pixel=np.array([image[wrist_index].x*shape[1],image[wrist_index].y*shape[0]])
        if palm<1e-6 or np.linalg.norm(pixels[0]-pose_pixel)>2*palm:
            raise InvalidPose('Mão e punho da pose não correspondem')
        hand=np.asarray(frame.world_points,dtype=float)
        if hand.shape!=(21,3):raise InvalidPose('Sem 21 pontos espaciais da mão')
        hand=transform_camera(hand,params)*params.posescale
        orientation,bones=skeleton_transforms(hand,frame.side)
        body=transform_camera(points,params)*params.posescale
        position=body[2]-(body[0]+body[1])/2+np.asarray(params.hmd_to_neck_offset)
        q=Rotation.from_matrix(orientation).as_quat()
        return np.r_[position,q[[3,0,1,2]]],bones
    except (TypeError,ValueError,AttributeError,IndexError) as exc:
        raise InvalidPose('Não foi possível associar mão e pose: '+str(exc)) from exc
