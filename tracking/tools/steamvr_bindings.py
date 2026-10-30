"""Gera bindings a partir do manifest REAL do VRChat; não inventa ações."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path


def make_bindings(manifest):
    if not isinstance(manifest,dict) or not isinstance(manifest.get('actions'),list):
        raise ValueError('Arquivo não é um manifest SteamVR de ações')
    actions=manifest['actions']
    for action in actions:
        if not isinstance(action,dict) or not isinstance(action.get('name'),str) or not action['name'].startswith('/actions/') or '/in/' not in action['name'] or not isinstance(action.get('type'),str):
            # Outputs (por exemplo, haptics) não são usados neste adaptador.
            if isinstance(action,dict) and '/out/' in str(action.get('name')):continue
            raise ValueError('Ação de entrada inválida no manifest')
    inputs=[a for a in actions if '/in/' in a['name']]

    def select(kind,names,required=True):
        for name in names:
            candidates=[a for a in inputs if a['type'].lower()==kind and a['name'].rsplit('/',1)[-1].lower()==name.lower()]
            if len(candidates)==1:return candidates[0]['name']
        if required:raise ValueError('Não foi encontrada ação única '+kind+': '+', '.join(names))
        return None

    output={'controller_type':'fiap_mediapipe_hand','name':'MediaPipe hands - VRChat',
            'description':'Pose/Skeleton reais; gatilho explícito só para confirmação solicitada.',
            'bindings':{}}
    report={'skeleton':{},'pose':{},'interact':{}}
    def group(action):
        name='/'.join(action.split('/')[:3])
        return output['bindings'].setdefault(name,{'poses':[],'skeleton':[],'sources':[]})
    for side in ('left','right'):
        capital=side.title()
        skeleton=select('skeleton',['Skeleton'+capital+'Hand'])
        pose=select('pose',['Pose'+capital+'Hand',capital+'HandPose','Pose'+capital,capital+'Pose','Pose'])
        report['skeleton'][side]=skeleton;report['pose'][side]=pose
        group(skeleton)['skeleton'].append({'output':skeleton,'path':f'/user/hand/{side}/input/skeleton/{side}'})
        group(pose)['poses'].append({'output':pose,'path':f'/user/hand/{side}/pose/raw'})
        interact=select('boolean',['Use'+capital,'Interact'+capital,capital+'Use',capital+'Interact','Use','Interact'],False)
        if interact:
            report['interact'][side]=interact
            group(interact)['sources'].append({'path':f'/user/hand/{side}/input/trigger','mode':'trigger','inputs':{'click':{'output':interact}}})
    report['manual_interact_binding_needed']=len(report['interact'])!=2
    return output,report


def install_bindings(driver,manifest):
    from steamvr_setup import atomic_write
    driver=Path(driver)
    profile_path=driver/'resources/input/mediapipe_hand_profile.json'
    original=profile_path.read_bytes()
    profile=json.loads(original.decode('utf-8-sig'))
    if not isinstance(profile,dict) or profile.get('controller_type')!='fiap_mediapipe_hand':raise ValueError('Pacote de driver incompatível')
    bindings,report=make_bindings(manifest)
    profile=copy.deepcopy(profile)
    previous=profile.get('default_bindings',[])
    if not isinstance(previous,list) or any(not isinstance(b,dict) for b in previous):raise ValueError('default_bindings inválido')
    profile['default_bindings']=[b for b in previous if b.get('app_key')!='steam.app.438100']
    profile['default_bindings'].append({'app_key':'steam.app.438100','binding_url':'vrchat_bindings.json'})
    binding_path=profile_path.with_name('vrchat_bindings.json')
    previous_binding=binding_path.read_bytes() if binding_path.exists() else None
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=profile_path.with_name(profile_path.name+'.'+stamp+'.bak')
    backup.write_bytes(original)
    if previous_binding is not None:binding_path.with_name(binding_path.name+'.'+stamp+'.bak').write_bytes(previous_binding)
    try:
        atomic_write(binding_path,(json.dumps(bindings,indent=2)+'\n').encode('utf-8'))
        atomic_write(profile_path,(json.dumps(profile,indent=2)+'\n').encode('utf-8'))
    except OSError:
        atomic_write(profile_path,original)
        if previous_binding is None:
            if binding_path.exists():binding_path.unlink()
        else:atomic_write(binding_path,previous_binding)
        raise
    return dict(report,profile_backup=str(backup),binding_path=str(binding_path))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actions',required=True,type=Path)
    parser.add_argument('--driver',type=Path)
    parser.add_argument('--write',action='store_true',help='Gravar somente no pacote do nosso driver, com backups; nunca altera arquivos do VRChat.')
    args=parser.parse_args(argv)
    try:
        manifest=json.loads(args.actions.read_text(encoding='utf-8-sig'))
        binding,report=make_bindings(manifest)
        if args.write:
            if args.driver is None:parser.error('--write exige --driver')
            from steamvr_setup import active_vr_processes
            if active_vr_processes():parser.error('Feche VRChat e SteamVR antes de gravar os bindings')
            report=install_bindings(args.driver,manifest)
        print(json.dumps({'report':report,'binding':binding},indent=2,ensure_ascii=True))
    except (ValueError,OSError) as exc:parser.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
