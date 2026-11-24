"""Optional Windows Chromium/real packaged Native Messaging end-to-end check.
Requires Playwright and its Chromium installed separately; uses no personal profile.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
import winreg

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.deps/browsers'))
from playwright.sync_api import sync_playwright
HOST=r'Software\Google\Chrome\NativeMessagingHosts\com.starlit.deskdownloader'
SETTINGS=r'Software\HizliIndir\HizliIndir'
PAYLOAD=b'%PDF-1.7\n'+b'Chrome native download fixture\n'*1024

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path=='/':
            body=b'<html><title>Downloader fixture</title><a id="link" href="/second.pdf">Download fixture</a></html>'
            kind='text/html'
        else:
            body=PAYLOAD
            kind='application/pdf'
        self.send_response(200)
        self.send_header('Content-Type',kind)
        if self.path!='/': self.send_header('Content-Disposition','attachment; filename="chrome-fixture.pdf"')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def main():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,HOST): pass
    except FileNotFoundError: pass
    else: raise RuntimeError('Existing host registration; nothing changed')
    with tempfile.TemporaryDirectory(prefix='chrome-native-',dir=ROOT/'.deps') as directory:
        folder=Path(directory)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,SETTINGS) as key:
            try: prior=winreg.QueryValueEx(key,'downloadFolder')
            except FileNotFoundError: prior=None
            winreg.SetValueEx(key,'downloadFolder',0,winreg.REG_SZ,str(folder))
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,HOST) as key:
            winreg.SetValueEx(key,'',0,winreg.REG_SZ,str(ROOT/'dist/HizliIndir/com.starlit.deskdownloader.json'))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        Thread(target=server.serve_forever,daemon=True).start()
        context=None
        try:
            with sync_playwright() as p:
                context=p.chromium.launch_persistent_context(str(folder/'profile'),channel='chromium',headless=True,args=['--disable-extensions-except='+str(ROOT/'browser_extension'),'--load-extension='+str(ROOT/'browser_extension')])
                worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
                assert 'jnhpcainmeohhdljgolpbgkhoodcfape' in worker.url
                profiles=worker.evaluate("async()=>await chrome.runtime.sendNativeMessage('com.starlit.deskdownloader',{action:'get_profiles'})")
                assert len(profiles['formats'])==15 and sum(len(x['qualities']) for x in profiles['formats'])==58
                print('PASS real Chromium extension -> packaged Native Messaging: 15 formats / 58 qualities',flush=True)
                page=context.pages[0]
                url=f'http://127.0.0.1:{server.server_port}/first.pdf'
                # Keep the fixture URL active without letting Chromium download it.
                page.route(url,lambda route:route.fulfill(status=200,content_type='text/html',body='<html><title>Fixture</title></html>'))
                page.goto(url)
                worker.evaluate('async()=>await chrome.action.openPopup()')
                cdp=context.new_cdp_session(page)
                targets=cdp.send('Target.getTargets')['targetInfos']
                popup=next(x for x in targets if x['url'].endswith('/popup.html'))
                session=cdp.send('Target.attachToTarget',{'targetId':popup['targetId'],'flatten':False})['sessionId']
                replies={}
                cdp.on('Target.receivedMessageFromTarget',lambda event: replies.update({json.loads(event['message']).get('id'):json.loads(event['message'])}))
                counter=0
                def evaluate(expression):
                    nonlocal counter
                    counter+=1
                    cdp.send('Target.sendMessageToTarget',{'sessionId':session,'message':json.dumps({'id':counter,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':True}})})
                    deadline=time.monotonic()+15
                    while counter not in replies and time.monotonic()<deadline: page.wait_for_timeout(50)
                    reply=replies.pop(counter)
                    assert 'error' not in reply,reply
                    assert 'exceptionDetails' not in reply.get('result',{}),reply
                    return reply['result']['result'].get('value')
                deadline=time.monotonic()+20
                while evaluate('document.querySelector("#profiles").hidden') and time.monotonic()<deadline: page.wait_for_timeout(100)
                assert evaluate('document.querySelector("#format").options.length')==15
                assert evaluate('document.querySelector("#page").textContent')==url
                evaluate('document.querySelector("#send").click()')
                target=folder/'chrome-fixture.pdf'
                deadline=time.monotonic()+25
                while not target.exists() and time.monotonic()<deadline: page.wait_for_timeout(100)
                assert target.read_bytes()==PAYLOAD
                assert evaluate('document.querySelector("#status").dataset.state')=='accepted'
                print('PASS actual extension popup -> closed packaged GUI launch -> exact localhost PDF',flush=True)
                print('NOTE native OS context-menu selection is not covered by this headless test',flush=True)
                evaluate('window.close()')
                context.close()
                context=None
        finally:
            if context: context.close()
            server.shutdown()
            server.server_close()
            # All fixture downloads completed before stopping our own packaged process.
            command="Get-CimInstance Win32_Process -Filter \"Name='HizliIndir.exe'\" | Where-Object { $_.ExecutablePath -eq '"+str(ROOT/'dist/HizliIndir/HizliIndir.exe')+"' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            subprocess.run(['powershell','-NoProfile','-Command',command],check=True,timeout=15)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,HOST)
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,SETTINGS,0,winreg.KEY_SET_VALUE) as key:
                if prior: winreg.SetValueEx(key,'downloadFolder',0,prior[1],prior[0])
                else: winreg.DeleteValue(key,'downloadFolder')

if __name__=='__main__': main()
