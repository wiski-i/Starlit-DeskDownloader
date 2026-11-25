"""Exercise real NSIS install/upgrade/uninstall in an owned test directory.

Aborts if product/host registration or the Start menu shortcut already exists.
Usage: python tests/check_windows_installer.py SETUP [PREVIOUS_SETUP]
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import winreg

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\StarlitDeskDownloader'
HOST = r'Software\Google\Chrome\NativeMessagingHosts\com.starlit.deskdownloader'
SHORTCUT = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Hızlı İndir.lnk'

def registry(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return {winreg.EnumValue(key,i)[0]: winreg.EnumValue(key,i)[1:] for i in range(winreg.QueryInfoKey(key)[1])}
    except FileNotFoundError:
        return None

def run(command, **kwargs):
    result = subprocess.run(command, timeout=180, **kwargs)
    assert result.returncode == 0, (command, result.returncode)

def installed(version, folder):
    values = registry(PRODUCT)
    assert values and values['DisplayVersion'][0] == version, values
    app = Path(values['ApplicationPath'][0])
    assert app.resolve() == (folder / ('app-' + version)).resolve(), app
    manifest = app / 'com.starlit.deskdownloader.json'
    assert Path(registry(HOST)[''][0]).resolve() == manifest.resolve()
    assert SHORTCUT.is_file()
    run([sys.executable, str(ROOT/'tests/check_packaged_host.py'), str(app/'HizliIndirBrowserHost.exe')])
    if version != '0.2.1':
        run([str(app/'HizliIndir.exe'), '--smoke-test'], env={**os.environ,'QT_QPA_PLATFORM':'offscreen'})
    return app

def main():
    assert sys.platform == 'win32'
    assert registry(PRODUCT) is None and registry(HOST) is None and not SHORTCUT.exists(), 'Existing user installation; nothing changed'
    setup = Path(sys.argv[1]).resolve(strict=True)
    old_setup = Path(sys.argv[2]).resolve(strict=True) if len(sys.argv)>2 else None
    settings_before = registry(r'Software\HizliIndir\HizliIndir')
    owned = ROOT / '.deps' / 'installer-lifecycle'
    owned.mkdir(parents=True,exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-',dir=owned)).resolve()
    assert folder.is_relative_to(owned.resolve())
    (folder/'user-sentinel.txt').write_text('keep user file',encoding='utf-8')
    old_app = None
    try:
        if old_setup:
            run([str(old_setup), '/S', '/D='+str(folder)])
            old_app = installed('0.2.1',folder)
            (old_app/'user-sentinel.txt').write_text('keep old user file',encoding='utf-8')
            print('PASS genuine 0.2.1 install, registry, shortcut and installed host')
        run([str(setup), '/S', '/D='+str(folder)])
        app = installed('0.2.2',folder)
        assert (folder/'user-sentinel.txt').read_text() == 'keep user file'
        if old_app:
            assert (old_app/'user-sentinel.txt').read_text() == 'keep old user file'
            assert not (old_app/'HizliIndir.exe').exists()
            print('PASS 0.2.1 -> 0.2.2 upgrade; user files preserved; old program removed')
        else:
            print('PASS 0.2.2 install, registry, shortcut, installed host and GUI')
        run([str(setup), '/S', '/D='+str(folder)])
        installed('0.2.2',folder)
        print('PASS same-version reinstall')
        # _?= waits for the uninstaller in its own directory; no detached copy.
        run([str(app/'Uninstall.exe'), '/S', '_?='+str(app)])
        assert registry(PRODUCT) is None and registry(HOST) is None
        assert not SHORTCUT.exists()
        assert not (app/'HizliIndir.exe').exists()
        assert (folder/'user-sentinel.txt').read_text() == 'keep user file'
        assert registry(r'Software\HizliIndir\HizliIndir') == settings_before
        print('PASS uninstall removes program/host/shortcut and preserves user files/preferences')
        print('Lifecycle evidence retained:', folder)
    finally:
        values = registry(PRODUCT)
        if values and Path(values.get('InstallLocation',[''])[0]).resolve() == folder:
            app = Path(values['ApplicationPath'][0])
            subprocess.run([str(app/'Uninstall.exe'), '/S', '_?='+str(app)],timeout=180)

if __name__ == '__main__': main()
