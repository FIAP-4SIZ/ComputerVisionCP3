"""Encoder Python real → decoder C++ compilado, sem mocks e sem SteamVR."""
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tracking'/'bin'))
from steamvr_protocol import encode_frame

probe=sys.argv[1]
pose=[.25,-.2,-.4,1,0,0,0]
bones=[[0,0,0,1,0,0,0] for _ in range(31)]
for side in (0,1):
    data=encode_frame(side,17,pose,bones)
    result=subprocess.run([probe],input=data,capture_output=True,check=True)
    assert result.stdout.decode().strip()==f'{side} 17 1 0.25'
    result=subprocess.run([probe],input=data[:-1],capture_output=True)
    assert result.returncode==2
    result=subprocess.run([probe],input=encode_frame(side,18,valid=False),capture_output=True,check=True)
    assert result.stdout.decode().strip()==f'{side} 18 0 0'
print('Python encoder -> native C++ decoder passed')
