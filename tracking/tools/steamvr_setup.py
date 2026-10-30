"""Prepara SteamVR null + mãos. Padrão: somente diagnóstico/plano, sem gravar."""
import argparse
import base64
import copy
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def digest(data):return hashlib.sha256(data).hexdigest()


def load_json(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict):raise ValueError('JSON deve ser um objeto: '+str(path))
    return data


def make_plan(paths_file,driver):
    paths=load_json(paths_file)
    for key in ('runtime','config','external_drivers'):
        values=paths.get(key,[])
        if key=='external_drivers' and values is None:values=[]
        if not isinstance(values,list) or any(not isinstance(p,str) or not p.strip() for p in values):raise ValueError('Lista OpenVR inválida: '+key)
        paths[key]=values
    if not paths.get('runtime') or not paths.get('config'):raise ValueError('Inicie SteamVR uma vez para criar seus caminhos/configuração')
    runtime=Path(paths['runtime'][0]).resolve()
    register=runtime/'bin/win64/vrpathreg.exe'
    if not register.is_file() or not (runtime/'drivers/null/bin/win64/driver_null.dll').is_file():
        raise ValueError('SteamVR Windows ou driver null oficial não encontrado')
    driver=Path(driver).resolve()
    manifest=load_json(driver/'driver.vrdrivermanifest')
    if manifest.get('name')!='mediapipe_hands' or not (driver/'bin/win64/driver_mediapipe_hands.dll').is_file():
        raise ValueError('Selecione o pacote compilado steamvr-hands-Windows, não apenas os fontes do driver')
    profile=load_json(driver/'resources/input/mediapipe_hand_profile.json')
    if profile.get('controller_type')!='fiap_mediapipe_hand':raise ValueError('Perfil de mãos incompatível')
    settings=Path(paths['config'][0]).resolve()/'steamvr.vrsettings'
    raw=settings.read_bytes() if settings.exists() else None
    before=load_json(settings) if raw is not None else {}
    after=copy.deepcopy(before)
    for section in ('steamvr','driver_null','driver_mediapipe_hands'):
        if section in after and not isinstance(after[section],dict):raise ValueError('Seção SteamVR inválida: '+section)
        after.setdefault(section,{})
    after['steamvr'].update(activateMultipleDrivers=True,forcedDriver='null',forcedHmd='',requireHmd=True,enableHomeApp=False)
    after['driver_null'].update(enable=True,id='Null Driver',serialNumber='FIAP-Development-HMD',modelNumber='MediaPipe Development HMD',
        windowX=0,windowY=0,windowWidth=1280,windowHeight=720,renderWidth=1280,renderHeight=720,
        secondsFromVsyncToPhotons=.01111111,displayFrequency=60.)
    after['driver_mediapipe_hands']['enable']=True
    normalize=lambda p:os.path.normcase(str(Path(p).resolve()))
    return dict(settings_path=str(settings),before_hash=digest(raw) if raw is not None else None,
        after=after,driver_path=str(driver),register_tool=str(register),
        already_registered=normalize(driver) in [normalize(p) for p in paths.get('external_drivers',[])],
        hmd_simulated=True,changes_applied=False,
        note='Cabeça virtual estacionária; não é rastreamento medido da cabeça. Inicie VRChat em VR, não desktop.')


def active_vr_processes():
    if sys.platform!='win32':raise ValueError('A aplicação destas configurações exige Windows; o plano pode ser testado separadamente')
    result=subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True,text=True,errors='replace',check=True)
    relevant={'vrserver.exe','vrmonitor.exe','vrcompositor.exe','vrchat.exe'}
    return [row[0] for row in csv.reader(io.StringIO(result.stdout)) if row and row[0].lower() in relevant]


def atomic_write(path,data):
    path=Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as target:
        temporary=Path(target.name)
        target.write(data);target.flush();os.fsync(target.fileno())
    try:os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def apply_plan(plan,check_processes=active_vr_processes,run=subprocess.run):
    running=check_processes()
    if running:raise ValueError('Feche VRChat e SteamVR antes: '+', '.join(running))
    settings=Path(plan['settings_path'])
    raw=settings.read_bytes() if settings.exists() else None
    if (digest(raw) if raw is not None else None)!=plan['before_hash']:
        raise ValueError('Configuração mudou desde o plano; gere outro plano sem sobrescrever alterações')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=settings.with_name('steamvr.fiap-backup-'+stamp+'.json')
    content=(json.dumps(plan['after'],indent=2)+'\n').encode('utf-8')
    journal=dict(version=1,settings_path=str(settings),before_hash=plan['before_hash'],
        before_b64=base64.b64encode(raw).decode('ascii') if raw is not None else None,
        after_hash=digest(content),after=plan['after'],driver_path=plan['driver_path'],register_tool=plan['register_tool'],
        registered_new=not plan['already_registered'])
    backup.write_text(json.dumps(journal,indent=2)+'\n',encoding='utf-8')
    registered=False
    try:
        if not plan['already_registered']:
            run([plan['register_tool'],'adddriver',plan['driver_path']],check=True,capture_output=True,text=True)
            registered=True
        atomic_write(settings,content)
    except Exception:
        if registered:
            run([plan['register_tool'],'removedriver',plan['driver_path']],check=True,capture_output=True,text=True)
        raise
    return dict(backup=str(backup),settings_path=str(settings),changes_applied=True,
                note='Inicie SteamVR, confirme HMD e driver; bindings e VRChat ainda precisam de validação.')


def restore(backup,check_processes=active_vr_processes,run=subprocess.run):
    if check_processes():raise ValueError('Feche VRChat e SteamVR antes de restaurar')
    journal=load_json(backup)
    required={'version','settings_path','before_hash','before_b64','after_hash','after','driver_path','register_tool','registered_new'}
    if type(journal.get('version')) is not int or journal.get('version')!=1 or not required<=set(journal) or type(journal.get('registered_new')) is not bool:
        raise ValueError('Backup incompatível')
    if any(not isinstance(journal[key],str) or not journal[key] for key in ('settings_path','after_hash','driver_path','register_tool')):
        raise ValueError('Caminhos/hashes do backup inválidos')
    try:
        original=base64.b64decode(journal['before_b64'],validate=True) if journal['before_b64'] is not None else None
    except (ValueError,TypeError) as exc:raise ValueError('Backup corrompido') from exc
    if (digest(original) if original is not None else None)!=journal['before_hash']:
        raise ValueError('Hash do backup não corresponde à configuração original')
    path=Path(journal['settings_path'])
    expected=(json.dumps(journal['after'],indent=2)+'\n').encode('utf-8')
    if digest(expected)!=journal['after_hash'] or not isinstance(journal['after'],dict):
        raise ValueError('Conteúdo posterior do backup corrompido')
    if not path.is_file():raise ValueError('Arquivo de configuração removido; restauração não será presumida')
    current_raw=path.read_bytes()
    if digest(current_raw)==journal['after_hash']:
        restored=original
    else:
        # SteamVR pode acrescentar metadados após iniciar. Desfazemos só os
        # campos alterados por nós, preservando mudanças em outros campos.
        before=json.loads(original.decode('utf-8-sig')) if original is not None else {}
        current=load_json(path)
        missing=object()
        changes=[]
        for section,values in journal['after'].items():
            if not isinstance(values,dict):continue
            old=before.get(section,{})
            if not isinstance(old,dict):continue
            for key,after_value in values.items():
                old_value=old.get(key,missing)
                if old_value==after_value:continue
                now=current.get(section,{})
                if not isinstance(now,dict):raise ValueError('Configuração modificada no campo '+section)
                current_value=now.get(key,missing)
                if current_value!=after_value and current_value!=old_value:
                    raise ValueError('Configuração modificada no campo '+section+'.'+key+'; compare o backup manualmente')
                changes.append((section,key,old_value))
        for section,key,value in changes:
            if value is missing:current.get(section,{}).pop(key,None)
            else:current.setdefault(section,{})[key]=value
        for section in journal['after']:
            if section not in before and current.get(section)=={}:current.pop(section,None)
        restored=(json.dumps(current,indent=2)+'\n').encode('utf-8') if current or original is not None else None
    if journal['registered_new']:
        run([journal['register_tool'],'removedriver',journal['driver_path']],check=True,capture_output=True,text=True)
    try:
        if restored is None:path.unlink()
        else:atomic_write(path,restored)
    except OSError:
        if journal['registered_new']:
            run([journal['register_tool'],'adddriver',journal['driver_path']],check=True,capture_output=True,text=True)
        raise
    return {'restored':True,'settings_path':str(path)}


def discover_actions(runtime):
    """Leitura somente de StreamingAssets, sem alterar o cliente/jogo."""
    runtime=Path(runtime)
    roots=[runtime.parent/'VRChat']
    steam=runtime.parents[2] if len(runtime.parents)>2 else runtime
    libraries=steam/'steamapps/libraryfolders.vdf'
    if libraries.is_file():
        for path in re.findall(r'"path"\s*"([^"\n]+)"',libraries.read_text(encoding='utf-8-sig')):
            roots.append(Path(path.replace('\\\\','\\'))/'steamapps/common/VRChat')
    for root in roots:
        assets=root/'VRChat_Data/StreamingAssets'
        if not assets.is_dir():continue
        for index,path in enumerate(assets.rglob('*.json')):
            if index>500:break
            if path.stat().st_size>2_000_000:continue
            try:
                data=load_json(path)
                if isinstance(data.get('actions'),list) and any('skeletonlefthand' in str(a.get('name','')).lower() for a in data['actions'] if isinstance(a,dict)):
                    return path
            except (ValueError,OSError):continue
    return None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths',type=Path,default=Path(os.environ.get('LOCALAPPDATA',''))/'openvr/openvrpaths.vrpath')
    parser.add_argument('--driver',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--restore',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.restore:
            if args.apply or args.driver:parser.error('--restore não combina com --apply/--driver')
            report=restore(args.restore)
        else:
            if args.driver is None:parser.error('Informe --driver com o pacote compilado')
            plan=make_plan(args.paths,args.driver)
            actions=discover_actions(Path(plan['register_tool']).parents[2])
            report={'plan':plan,'actions_manifest':str(actions) if actions else None,
                    'bindings_note':'Use steamvr_bindings.py --actions CAMINHO --driver PACOTE --write, ou configure Pose/Skeleton no SteamVR Binding UI.'}
            if args.apply:report['result']=apply_plan(plan)
        print(json.dumps(report,indent=2,ensure_ascii=True))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:parser.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
