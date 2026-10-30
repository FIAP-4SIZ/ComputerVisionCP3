"""Preparação reversível do SteamVR Windows e bindings reais do cliente."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import steamvr_setup as setup
import steamvr_bindings as bindings
import steamvr_hands_check as check


def installation(directory,settings=True):
    root=Path(directory);runtime=root/'Steam/steamapps/common/SteamVR';config=root/'Steam/config';driver=root/'driver with spaces'
    config.mkdir(parents=True)
    for path in (runtime/'bin/win64/vrpathreg.exe',runtime/'drivers/null/bin/win64/driver_null.dll',driver/'bin/win64/driver_mediapipe_hands.dll'):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'MZ fixture, not executable')
    (driver/'driver.vrdrivermanifest').write_text(json.dumps({'name':'mediapipe_hands'}))
    profile=driver/'resources/input/mediapipe_hand_profile.json';profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({'controller_type':'fiap_mediapipe_hand','input_source':{},'default_bindings':[{'app_key':'other.app','binding_url':'other.json'}]}))
    if settings:(config/'steamvr.vrsettings').write_bytes(b'\xef\xbb\xbf{\r\n "steamvr": {"keep": true}, "unrelated": {"custom": 42}\r\n}\r\n')
    paths=root/'openvrpaths.vrpath'
    paths.write_text(json.dumps({'runtime':[str(runtime)],'config':[str(config)],'external_drivers':[]}))
    return paths,driver,config/'steamvr.vrsettings',runtime


def actions(interact=True,pose_name='Pose'):
    entries=[{'name':'/actions/global/in/'+name,'type':kind} for name,kind in (
        ('SkeletonLeftHand','skeleton'),('SkeletonRightHand','skeleton'),(pose_name,'pose'))]
    if interact:entries.extend({'name':'/actions/main/in/Use'+side,'type':'boolean'} for side in ('Left','Right'))
    return {'actions':entries}


class WindowsSetupTests(unittest.TestCase):
    def test_display_defaults_only_fill_missing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory)
            data=setup.load_json(settings)
            data['driver_null']={'windowX':-1920,'windowY':100,'windowWidth':900,
                                 'windowHeight':600,'renderWidth':2048,'renderHeight':1536}
            data['steamvr']['showMirrorView']=True
            settings.write_text(json.dumps(data));original=settings.read_bytes()
            plan=setup.make_plan(paths,driver)
            for key,value in data['driver_null'].items():
                self.assertEqual(plan['after']['driver_null'][key],value)
            self.assertTrue(plan['after']['steamvr']['showMirrorView'])
            self.assertEqual(settings.read_bytes(),original)

    def test_render_and_mirror_changes_are_explicit_and_reversible(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory)
            data=setup.load_json(settings);data['steamvr']['showMirrorView']=True
            settings.write_text(json.dumps(data));original=settings.read_bytes()
            plan=setup.make_plan(paths,driver,render_size=(1920,1080),hide_mirror=True)
            null=plan['after']['driver_null']
            self.assertEqual((null['renderWidth'],null['renderHeight']),(1920,1080))
            self.assertEqual((null['windowWidth'],null['windowHeight']),(1280,720))
            self.assertFalse(plan['after']['steamvr']['showMirrorView'])
            result=setup.apply_plan(plan,check_processes=lambda:[],run=Mock())
            setup.restore(result['backup'],check_processes=lambda:[],run=Mock())
            self.assertEqual(settings.read_bytes(),original)

    def test_display_size_validation(self):
        self.assertEqual(setup.display_size('1920x1080'),(1920,1080))
        self.assertEqual(setup.display_size('320X4096'),(320,4096))
        for value in ('0x1080','1920x319','4097x1080','-1x720','1.5x720','1920','1920x1080extra'):
            with self.subTest(value=value),self.assertRaises(setup.argparse.ArgumentTypeError):
                setup.display_size(value)

    def test_invalid_display_api_arguments_rejected_before_file_access(self):
        for value in ((True,720),(320,4097),[1920,1080],(320,),('1920',1080)):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'Resolução'):
                setup.make_plan('missing','missing',render_size=value)
        with self.assertRaisesRegex(ValueError,'booleano'):
            setup.make_plan('missing','missing',hide_mirror=1)

    def test_display_cli_preview_apply_and_restore_conflict(self):
        with patch.object(setup,'make_plan',return_value={'register_tool':'/runtime/bin/win64/tool'}) as plan,patch.object(setup,'discover_actions',return_value=None),patch('builtins.print'),patch.object(setup,'apply_plan',return_value={'changes_applied':True}) as apply:
            setup.main(['--driver','package','--render-size','1920x1080','--hide-mirror'])
            self.assertEqual(plan.call_args.kwargs,{'render_size':(1920,1080),'hide_mirror':True})
            apply.assert_not_called()
            setup.main(['--driver','package','--render-size','1920x1080','--hide-mirror','--apply'])
            apply.assert_called_once()
        with patch.object(setup,'restore') as restore,patch('sys.stderr'):
            with self.assertRaises(SystemExit) as error:
                setup.main(['--restore','backup.json','--hide-mirror'])
            self.assertEqual(error.exception.code,2);restore.assert_not_called()

    def test_plan_is_read_only_and_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory);before=settings.read_bytes()
            plan=setup.make_plan(paths,driver)
            self.assertEqual(settings.read_bytes(),before)
            self.assertEqual(plan['after']['steamvr']['keep'],True)
            self.assertEqual(plan['after']['unrelated'],{'custom':42})
            self.assertEqual(plan['after']['steamvr']['forcedDriver'],'null')
            self.assertTrue(plan['after']['steamvr']['activateMultipleDrivers'])
            self.assertFalse(plan['changes_applied'])

    def test_plan_accepts_windows_null_external_drivers(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,_,_=installation(directory)
            data=setup.load_json(paths);data['external_drivers']=None;paths.write_text(json.dumps(data))
            self.assertFalse(setup.make_plan(paths,driver)['already_registered'])

    def test_apply_and_restore_exact_bytes_including_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory);original=settings.read_bytes();run=Mock()
            plan=setup.make_plan(paths,driver)
            result=setup.apply_plan(plan,check_processes=lambda:[],run=run)
            self.assertTrue(result['changes_applied']);self.assertNotEqual(settings.read_bytes(),original)
            self.assertEqual(run.call_args.args[0],[plan['register_tool'],'adddriver',str(driver.resolve())])
            setup.restore(result['backup'],check_processes=lambda:[],run=run)
            self.assertEqual(settings.read_bytes(),original)
            self.assertEqual(run.call_args.args[0],[plan['register_tool'],'removedriver',str(driver.resolve())])

    def test_existing_addon_not_unregistered_and_new_file_removed_on_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory,settings=False)
            data=setup.load_json(paths);data['external_drivers']=[str(driver)];paths.write_text(json.dumps(data))
            run=Mock();result=setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=run)
            setup.restore(result['backup'],check_processes=lambda:[],run=run)
            self.assertFalse(settings.exists());run.assert_not_called()

    def test_changed_settings_refuse_apply_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory)
            plan=setup.make_plan(paths,driver);settings.write_text('{}')
            with self.assertRaisesRegex(ValueError,'mudou'):setup.apply_plan(plan,check_processes=lambda:[],run=Mock())
            result=setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=Mock())
            modified=setup.load_json(settings);modified['steamvr']['forcedDriver']='user-selected-driver';settings.write_text(json.dumps(modified))
            run=Mock()
            with self.assertRaisesRegex(ValueError,'modificada'):setup.restore(result['backup'],check_processes=lambda:[],run=run)
            self.assertEqual(json.loads(settings.read_text())['steamvr']['forcedDriver'],'user-selected-driver');run.assert_not_called()

    def test_restore_preserves_runtime_metadata_and_unrelated_user_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory)
            result=setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=Mock())
            current=setup.load_json(settings);current['steamvr']['last_runtime_update']='keep me';current['unrelated']['custom']=99
            settings.write_text(json.dumps(current))
            setup.restore(result['backup'],check_processes=lambda:[],run=Mock())
            restored=setup.load_json(settings)
            self.assertEqual(restored['steamvr'],{'keep':True,'last_runtime_update':'keep me'})
            self.assertEqual(restored['unrelated'],{'custom':99})
            self.assertNotIn('driver_null',restored)

    def test_running_vr_blocks_all_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory);original=settings.read_bytes();run=Mock()
            with self.assertRaisesRegex(ValueError,'Feche'):setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:['VRChat.exe'],run=run)
            self.assertEqual(settings.read_bytes(),original);run.assert_not_called()

    def test_registration_failure_does_not_change_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory);original=settings.read_bytes()
            run=Mock(side_effect=subprocess.CalledProcessError(1,'vrpathreg'))
            with self.assertRaises(subprocess.CalledProcessError):setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=run)
            self.assertEqual(settings.read_bytes(),original)

    def test_write_failure_unregisters_only_new_addon(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,_=installation(directory);original=settings.read_bytes();run=Mock()
            with patch.object(setup,'atomic_write',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=run)
            self.assertEqual(settings.read_bytes(),original)
            self.assertEqual([call.args[0][1] for call in run.call_args_list],['adddriver','removedriver'])

    def test_corrupt_json_invalid_sections_and_missing_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,settings,runtime=installation(directory)
            for text in ('not json','[]','{"steamvr":false}'):
                settings.write_text(text)
                with self.assertRaises(ValueError):setup.make_plan(paths,driver)
            settings.write_text('{}')
            (runtime/'drivers/null/bin/win64/driver_null.dll').unlink()
            with self.assertRaisesRegex(ValueError,'null'):setup.make_plan(paths,driver)

    def test_corrupt_backup_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,_,_=installation(directory)
            result=setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=Mock())
            backup=Path(result['backup']);journal=setup.load_json(backup)
            journal['before_b64']=base64.b64encode(b'changed').decode();backup.write_text(json.dumps(journal))
            run=Mock()
            with self.assertRaisesRegex(ValueError,'Hash'):setup.restore(backup,check_processes=lambda:[],run=run)
            run.assert_not_called()

    def test_restore_write_failure_reregisters_addon(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,driver,_,_=installation(directory)
            result=setup.apply_plan(setup.make_plan(paths,driver),check_processes=lambda:[],run=Mock())
            run=Mock()
            with patch.object(setup,'atomic_write',side_effect=OSError('read only')):
                with self.assertRaises(OSError):setup.restore(result['backup'],check_processes=lambda:[],run=run)
            self.assertEqual([call.args[0][1] for call in run.call_args_list],['removedriver','adddriver'])

    def test_windows_process_detection_uses_argument_list(self):
        output='"VRChat.exe","123","Console","1","123 K"\n"vrserver.exe","456","Console","1","1 K"\n"steam.exe","987","Console","1","1 K"'
        with patch.object(setup.sys,'platform','win32'),patch.object(setup.subprocess,'run',return_value=NS(stdout=output)) as run:
            self.assertEqual(setup.active_vr_processes(),['VRChat.exe','vrserver.exe'])
        self.assertEqual(run.call_args.args[0],['tasklist','/fo','csv','/nh'])

    def test_discover_real_action_manifest_from_streaming_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            _,_,_,runtime=installation(directory)
            assets=runtime.parent/'VRChat/VRChat_Data/StreamingAssets/SteamVR';assets.mkdir(parents=True)
            manifest=assets/'actions.json';manifest.write_text(json.dumps(actions()))
            self.assertEqual(setup.discover_actions(runtime),manifest)


class VRChatBindingsTests(unittest.TestCase):
    def test_pose_skeleton_and_manual_trigger_use_existing_actions(self):
        binding,report=bindings.make_bindings(actions())
        self.assertEqual(binding['controller_type'],'fiap_mediapipe_hand')
        self.assertFalse(report['manual_interact_binding_needed'])
        self.assertEqual(binding['bindings']['/actions/global']['skeleton'][0],
            {'output':'/actions/global/in/SkeletonLeftHand','path':'/user/hand/left/input/skeleton/left'})
        self.assertEqual(len(binding['bindings']['/actions/main']['sources']),2)

    def test_unknown_actions_not_guessed_and_trigger_mapping_optional(self):
        binding,report=bindings.make_bindings(actions(interact=False))
        self.assertTrue(report['manual_interact_binding_needed'])
        self.assertEqual(binding['bindings']['/actions/global']['sources'],[])
        for invalid in ({},actions(pose_name='UnknownPose'),{'actions':actions()['actions'][:1]}):
            with self.assertRaises(ValueError):bindings.make_bindings(invalid)

    def test_install_keeps_other_profiles_and_creates_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            _,driver,_,_=installation(directory)
            profile=driver/'resources/input/mediapipe_hand_profile.json';original=profile.read_bytes()
            report=bindings.install_bindings(driver,actions())
            self.assertEqual(Path(report['profile_backup']).read_bytes(),original)
            updated=setup.load_json(profile)
            self.assertIn({'app_key':'other.app','binding_url':'other.json'},updated['default_bindings'])
            self.assertEqual(updated['default_bindings'][-1]['app_key'],'steam.app.438100')
            self.assertTrue(Path(report['binding_path']).is_file())

    def test_failed_profile_write_restores_both_files(self):
        with tempfile.TemporaryDirectory() as directory:
            _,driver,_,_=installation(directory)
            profile=driver/'resources/input/mediapipe_hand_profile.json';original=profile.read_bytes()
            binding=profile.with_name('vrchat_bindings.json');binding.write_bytes(b'old binding')
            real=setup.atomic_write
            count=[0]
            def fail_once(path,data):
                count[0]+=1
                if count[0]==2:raise OSError('write failed')
                return real(path,data)
            with patch.object(setup,'atomic_write',side_effect=fail_once):
                with self.assertRaises(OSError):bindings.install_bindings(driver,actions())
            self.assertEqual(profile.read_bytes(),original);self.assertEqual(binding.read_bytes(),b'old binding')


class WindowsCheckTests(unittest.TestCase):
    def test_status_does_not_trigger_buttons(self):
        with patch.object(check,'SteamVRHandsClient') as factory:
            client=factory.return_value;client.status.return_value={'hmd_valid':True,'tracked_mask':0,'protocol':1}
            check.main([])
        client.confirm.assert_not_called();client.close.assert_called_once()

    def test_confirmation_waits_and_checks_fresh_tracking(self):
        with patch.object(check,'SteamVRHandsClient') as factory,patch.object(check.time,'sleep') as sleep:
            client=factory.return_value;client.status.return_value={'hmd_valid':True,'tracked_mask':3,'protocol':1}
            check.main(['--confirm','--delay','3'])
        self.assertEqual(sleep.call_count,3);self.assertEqual(client.status.call_count,2)
        client.confirm.assert_called_once();client.close.assert_called_once()

    def test_tracking_loss_cancels_confirmation_and_closes(self):
        with patch.object(check,'SteamVRHandsClient') as factory,patch.object(check.time,'sleep'):
            client=factory.return_value;client.status.side_effect=[{'hmd_valid':True,'tracked_mask':3}, {'hmd_valid':True,'tracked_mask':0}]
            with self.assertRaises(SystemExit):check.main(['--confirm'])
        client.confirm.assert_not_called();client.close.assert_called_once()
