"""Inspeção somente de leitura: instalação SteamVR e presença do driver null."""
import argparse
import json
import os
from pathlib import Path


def inspect(paths_file):
    path=Path(paths_file)
    if not path.is_file():
        raise ValueError('openvrpaths.vrpath não encontrado. Instale e inicie SteamVR ao menos uma vez, ou informe --paths.')
    try:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,json.JSONDecodeError) as error:
        raise ValueError('Não foi possível ler openvrpaths.vrpath: '+str(error)) from error
    if not isinstance(data,dict):raise ValueError('Documento OpenVR deve ser um objeto JSON')
    for key in ('runtime','external_drivers'):
        values=data.get(key,[])
        if not isinstance(values,list) or any(not isinstance(item,str) or not item.strip() for item in values):
            raise ValueError('Lista inválida: '+key)
    runtimes=[]
    for item in data.get('runtime',[]):
        root=Path(item)
        runtimes.append(dict(path=str(root),directory_exists=root.is_dir(),
                             vrserver=(root/'bin/win64/vrserver.exe').is_file(),
                             vrpathreg=(root/'bin/win64/vrpathreg.exe').is_file(),
                             null_driver=(root/'drivers/null/bin/win64/driver_null.dll').is_file()))
    return dict(paths_file=str(path),runtimes=runtimes,
                external_drivers=[dict(path=value,manifest=(Path(value)/'driver.vrdrivermanifest').is_file()) for value in data.get('external_drivers',[])],
                hmd_pose_tested=False,skeletal_input_tested=False,configuration_changed=False,
                note='Presença de arquivos não confirma HMD, dedos ou compatibilidade com VRChat. Nenhum driver foi instalado ou iniciado.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths',default=str(Path(os.environ.get('LOCALAPPDATA',''))/'openvr/openvrpaths.vrpath'))
    args=parser.parse_args(argv)
    try:report=inspect(args.paths)
    except ValueError as error:parser.exit(2,str(error)+'\n')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
