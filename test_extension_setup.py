"""Bundled extension setup regression checks without changing browser state."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class ExtensionSetupTests(unittest.TestCase):
    def test_extension_is_copied_to_stable_user_folder(self):
        import extension_setup
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'bundle/browser_extension'
            source.mkdir(parents=True)
            (source/'manifest.json').write_text('{"version":"0.2.2"}')
            (source/'bridge.js').write_text('extension')
            with patch.object(extension_setup,'ROOT',source.parent), patch.object(extension_setup,'user_extension_folder',return_value=root/'stable/ChromeExtension'):
                folder=extension_setup.prepare_extension()
                self.assertEqual((folder/'manifest.json').read_text(),'{"version":"0.2.2"}')
                self.assertEqual((folder/'bridge.js').read_text(),'extension')
                (folder/'user-note.txt').write_text('keep')
                extension_setup.prepare_extension()
                self.assertEqual((folder/'user-note.txt').read_text(),'keep')

    def test_missing_bundle_does_not_create_empty_extension(self):
        import extension_setup
        with tempfile.TemporaryDirectory() as directory, patch.object(extension_setup,'ROOT',Path(directory)):
            with self.assertRaises(FileNotFoundError): extension_setup.prepare_extension()

    def test_chrome_launch_reports_missing_browser(self):
        import extension_setup
        with patch.object(extension_setup,'chrome_command',return_value=None):
            self.assertFalse(extension_setup.open_chrome_extensions())
        with patch.object(extension_setup.sys,'platform','win32'), patch.object(extension_setup,'chrome_command',return_value=['chrome','chrome://extensions/']), patch.object(extension_setup.subprocess,'Popen') as launch:
            self.assertTrue(extension_setup.open_chrome_extensions())
            self.assertEqual(launch.call_args.args[0],['chrome','chrome://extensions/'])
        with patch.object(extension_setup.sys,'platform','darwin'),patch.object(extension_setup,'chrome_command',return_value=['/usr/bin/open','-a','Google Chrome','chrome://extensions/']),patch.object(extension_setup.subprocess,'run') as launch:
            self.assertTrue(extension_setup.open_chrome_extensions())
            self.assertEqual(launch.call_args.args[0][0],'/usr/bin/open')
            launch.side_effect=extension_setup.subprocess.CalledProcessError(1,['open'])
            self.assertFalse(extension_setup.open_chrome_extensions())

    def test_mac_registration_uses_host_beside_frozen_gui(self):
        import extension_setup
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            host=root/'HizliIndirBrowserHost'
            host.touch()
            with patch.object(extension_setup.sys,'platform','darwin'), patch.object(extension_setup.sys,'frozen',True,create=True), patch.object(extension_setup.sys,'executable',str(root/'HizliIndir')), patch.object(extension_setup.subprocess,'run') as run:
                extension_setup.register_native_host()
                self.assertEqual(run.call_args.args[0],[str(host),'--register-browser-host'])

    def test_windows_registration_keeps_installer_manifest_for_uninstall(self):
        import extension_setup
        from unittest.mock import MagicMock
        import sys
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'HizliIndirBrowserHost.exe').touch()
            manifest=folder/'com.starlit.deskdownloader.json'
            manifest.write_text('{}')
            registry=MagicMock()
            with patch.dict(sys.modules,{'winreg':registry}),patch.object(extension_setup.sys,'platform','win32'),patch.object(extension_setup.sys,'frozen',True,create=True),patch.object(extension_setup.sys,'executable',str(folder/'HizliIndir.exe')),patch.object(extension_setup,'user_extension_folder',return_value=folder/'stable/ChromeExtension'):
                self.assertTrue(extension_setup.register_native_host())
                self.assertEqual(registry.SetValueEx.call_args.args[-1],str(manifest))

    def test_ui_has_extension_setup_button_and_instructions(self):
        import os,subprocess,sys
        result=subprocess.run([sys.executable,'-c',r"""
from PySide6.QtWidgets import QApplication,QPushButton,QDialog
from PySide6.QtCore import QCoreApplication,QEvent,QSettings,QTimer
from shiboken6 import delete,isValid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from app import VideoWindow
from unix_desktop import BrowserCapture
app=QApplication([])
try:
 with TemporaryDirectory() as directory:
  settings=QSettings(str(Path(directory)/'settings.ini'),QSettings.Format.IniFormat)
  capture=BrowserCapture(Path('unused'),app)
  window=VideoWindow(app,settings,capture)
  try:
   button=next((b for b in window.findChildren(QPushButton) if b.text()=='Extension Kur'),None)
   assert button is not None
   with patch('app.prepare_extension',return_value=Path(directory)),patch('app.register_native_host') as register:
    colors=[]
    def inspect_dialog():
     d=app.activeModalWidget()
     colors.append(d.grab().toImage().pixelColor(0,0).name())
     d.accept()
    QTimer.singleShot(50,inspect_dialog)
    button.click()
    register.assert_called_once()
    from theme import DIALOG_BACKGROUND
    assert colors==[DIALOG_BACKGROUND.lower()],colors
  finally:
   # Destroy Python-backed Qt objects while QApplication still owns its event dispatcher.
   capture.stop()
   window.tray.hide()
   window.hide()
   window.deleteLater()
   capture.deleteLater()
   QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
   app.processEvents()
   QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
   assert not isValid(window)
   assert not isValid(capture)
   settings.sync()
finally:
 delete(app)

"""],env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
