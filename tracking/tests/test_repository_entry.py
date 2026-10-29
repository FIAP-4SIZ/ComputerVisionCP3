"""Entrada independente do diretório e referências de documentação atual."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import importlib.util

TRACKING=Path(__file__).resolve().parents[1]
ROOT=TRACKING.parent
spec=importlib.util.spec_from_file_location('tracking_run',TRACKING/'run.py')
launcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class RepositoryEntryTests(unittest.TestCase):
    def test_launcher_resolves_runtime_and_restores_context_after_error(self):
        original_path=sys.path.copy()
        with tempfile.TemporaryDirectory() as directory:
            previous=Path.cwd()
            try:
                os.chdir(directory)
                def fail(path,run_name):
                    self.assertEqual(Path.cwd(),TRACKING)
                    self.assertEqual(Path(path),TRACKING/'bin/mediapipepose.py')
                    self.assertEqual(sys.path[0],str(TRACKING/'bin'))
                    self.assertEqual(run_name,'__main__')
                    raise RuntimeError('runtime failed')
                with patch.object(launcher.runpy,'run_path',side_effect=fail):
                    with self.assertRaisesRegex(RuntimeError,'runtime failed'):
                        launcher.main()
                self.assertEqual(Path.cwd(),Path(directory))
                self.assertEqual(sys.path,original_path)
            finally:
                os.chdir(previous)

    def test_unsupported_python_explains_prerequisite(self):
        with patch.object(launcher.sys,'version_info',(3,14)):
            with self.assertRaisesRegex(SystemExit,'Python 3.12'):
                launcher.main()

    def test_runtime_from_unrelated_directory_with_real_models(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,str(TRACKING/'run.py'),'--check-runtime'],
                                  cwd=directory,text=True,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Pose, Hands e modelos',result.stdout)

    def test_current_markdown_local_links_exist(self):
        documents=[ROOT/'README.md',TRACKING/'README.md',ROOT/'DEVELOPMENT.md']
        documents += [p for p in (TRACKING/'docs').rglob('*.md') if 'reference' not in p.parts]
        for document in documents:
            for target in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding="utf-8")):
                if '://' in target or target.startswith(('#','mailto:','/')):
                    continue
                path=target.split('#')[0]
                with self.subTest(document=str(document),target=target):
                    self.assertTrue((document.parent/path).exists())

    def test_requirements_forward_to_single_runtime_definition(self):
        self.assertIn('-r requirements-study.txt',(TRACKING/'requirements.txt').read_text(encoding="utf-8"))
        self.assertIn('-r ../requirements-study.txt',(TRACKING/'bin/requirements.txt').read_text(encoding="utf-8"))
        self.assertIn('-r requirements-study.txt',(TRACKING/'requirements-build.txt').read_text(encoding="utf-8"))

    def test_documentation_checks_with_windows_ansi_default(self):
        # Reproduz a causa da falha na CI Windows sem exigir esse sistema aqui.
        with patch('io.text_encoding', side_effect=lambda encoding=None, stacklevel=2: encoding or 'cp1252'):
            self.test_current_markdown_local_links_exist()

    def test_validation_history_is_distinct_from_review_index(self):
        reports=TRACKING/'docs/reports'
        validation=(reports/'VALIDATION_REPORT.md').read_text(encoding='utf-8')
        review=(reports/'REVIEW_STATUS.md').read_text(encoding='utf-8')
        self.assertNotEqual(validation,review)
        for heading in ('# Relatório de validação e integração','## Feature de vídeo','## Peitoral e dedos'):
            self.assertIn(heading,validation)
