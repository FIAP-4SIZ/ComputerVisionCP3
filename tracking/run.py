"""Entrada estável: python tracking/run.py [--check-runtime], de qualquer pasta."""
from pathlib import Path
import os
import runpy
import sys


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('Use Python 3.12: a API MediaPipe fixada neste projeto requer esse ambiente validado.')
    directory = Path(__file__).resolve().parent
    previous_directory = Path.cwd()
    previous_path = sys.path.copy()
    try:
        os.chdir(directory)
        sys.path.insert(0, str(directory / 'bin'))
        runpy.run_path(str(directory / 'bin' / 'mediapipepose.py'), run_name='__main__')
    finally:
        sys.path[:] = previous_path
        os.chdir(previous_directory)


if __name__ == '__main__':
    main()
