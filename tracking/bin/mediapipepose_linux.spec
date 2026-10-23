# -*- mode: python ; coding: utf-8 -*-
# Resolve módulos e modelos a partir do Python ativo, sem caminhos da antiga CI.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files

source = Path(SPECPATH)
# Python standalone pode carregar Tcl/Tk fora dos diretórios globais do sistema.
runtime_lib = Path(sys.base_prefix) / 'lib'
tk_binaries = [(str(path), '.') for pattern in ('libtcl*.so*', 'libtk*.so*', 'libtcl*.dylib', 'libtk*.dylib')
               for path in runtime_lib.glob(pattern) if path.is_file()]
a = Analysis([str(source / 'mediapipepose.py')],
             pathex=[str(source)], binaries=tk_binaries,
             datas=collect_data_files('mediapipe') + [(str(source / 'templates'), 'templates')],
             hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='mediapipepose',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='mediapipepose')
