import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('check_steamvr',Path(__file__).resolve().parents[1]/'tools/check_steamvr.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)


class SteamVRReadinessTests(unittest.TestCase):
    def test_absent_configuration_explains_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'não encontrado'):tool.inspect(Path(directory)/'missing')

    def test_invalid_json_and_structures(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'paths'
            for value in ('invalid','[]','{"runtime":"path"}','{"runtime":[42]}','{"external_drivers":[""]}'):
                path.write_text(value,encoding='utf-8')
                with self.assertRaises(ValueError):tool.inspect(path)

    def test_files_detected_without_claiming_runtime_or_changing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runtime=root/'SteamVR';driver=root/'custom'
            for file in ('bin/win64/vrserver.exe','bin/win64/vrpathreg.exe','drivers/null/bin/win64/driver_null.dll'):
                target=runtime/file;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
            driver.mkdir();(driver/'driver.vrdrivermanifest').write_text('{}')
            path=root/'openvrpaths.vrpath'
            path.write_text(json.dumps({'runtime':[str(runtime)],'external_drivers':[str(driver)]}),encoding='utf-8-sig')
            before=path.read_bytes();result=tool.inspect(path)
            self.assertTrue(result['runtimes'][0]['null_driver'])
            self.assertTrue(result['external_drivers'][0]['manifest'])
            self.assertFalse(result['hmd_pose_tested']);self.assertFalse(result['skeletal_input_tested'])
            self.assertEqual(path.read_bytes(),before)

    def test_missing_binaries_and_empty_paths_remain_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'paths';path.write_text(json.dumps({'runtime':[str(Path(directory)/'missing')]}))
            result=tool.inspect(path)
            self.assertFalse(result['runtimes'][0]['directory_exists'])
            self.assertFalse(result['runtimes'][0]['null_driver'])
            path.write_text('{}');self.assertEqual(tool.inspect(path)['runtimes'],[])
