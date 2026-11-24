"""Prepare the bundled Chrome Extension in a stable user-owned location."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PySide6.QtCore import QStandardPaths
from downloads import ROOT


def user_extension_folder() -> Path:
    location=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    if not location:
        raise OSError('Application data folder is unavailable')
    return Path(location)/'StarlitDeskDownloader'/'ChromeExtension'


def prepare_extension() -> Path:
    source=ROOT/'browser_extension'
    if not (source/'manifest.json').is_file():
        raise FileNotFoundError('Bundled Chrome Extension is missing')
    destination=user_extension_folder()
    # Installed application directories are versioned; Chrome needs a stable path.
    shutil.copytree(source,destination,dirs_exist_ok=True)
    return destination


def chrome_command() -> list[str] | None:
    if sys.platform=='darwin':
        return ['/usr/bin/open','-a','Google Chrome','chrome://extensions/']
    candidates=[]
    if sys.platform=='win32':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe') as key:
                    candidates.append(winreg.QueryValueEx(key,'')[0])
            except OSError:
                pass
        for variable in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
            folder=os.environ.get(variable)
            if folder: candidates.append(str(Path(folder)/'Google/Chrome/Application/chrome.exe'))
    else:
        candidates.extend(filter(None,(shutil.which('google-chrome'),shutil.which('google-chrome-stable'),shutil.which('chromium'))))
    executable=next((path for path in candidates if Path(path).is_file()),None)
    return [executable,'chrome://extensions/'] if executable else None


def open_chrome_extensions() -> bool:
    command=chrome_command()
    if not command: return False
    try:
        if sys.platform=='darwin':
            subprocess.run(command,check=True,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return True
    except (OSError,subprocess.SubprocessError):
        return False


def register_native_host() -> bool:
    if sys.platform=='darwin':
        if getattr(sys,'frozen',False):
            command=[str(Path(sys.executable).with_name('HizliIndirBrowserHost'))]
        else:
            command=[sys.executable,str(ROOT/'native_host.py')]
        subprocess.run([*command,'--register-browser-host'],check=True,capture_output=True,timeout=15)
        return True
    if sys.platform=='win32' and getattr(sys,'frozen',False):
        import winreg
        host=Path(sys.executable).with_name('HizliIndirBrowserHost.exe')
        if not host.is_file(): raise FileNotFoundError(host)
        manifest=host.with_name('com.starlit.deskdownloader.json')
        if not manifest.is_file(): raise FileNotFoundError(manifest)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Google\Chrome\NativeMessagingHosts\com.starlit.deskdownloader') as key:
            winreg.SetValueEx(key,'',0,winreg.REG_SZ,str(manifest))
        return True
    return False
