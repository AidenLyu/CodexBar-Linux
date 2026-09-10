"""Check real single-instance process lifecycle and remote actions on an isolated bus."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]

def call(destination, path, method, *args):
    return subprocess.run(['gdbus','call','--session','--dest',destination,'--object-path',path,'--method',method,*args],capture_output=True,text=True,timeout=5)
with tempfile.TemporaryDirectory() as tmp:
    fake=Path(tmp)/'cli'
    fake.write_text('#!/bin/sh\nprintf \'[{"provider":"codex","usage":{"primary":{"usedPercent":24}}}]\\n\'\n')
    fake.chmod(0o755)
    env=dict(os.environ,CODEXBAR_BIN=str(fake))
    process=subprocess.Popen([sys.executable,str(ROOT/'codexbar-tray.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(100):
            status=call('dev.codexbar.linux.popup','/dev/codexbar/linux/popup','org.gtk.Actions.List')
            if status.returncode==0:break
            assert process.poll() is None, process.stderr.read()
            time.sleep(.05)
        assert status.returncode==0,status.stderr
        children=Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
        assert len(children)==1,children
        remote=subprocess.run([sys.executable,str(ROOT/'codexbar-tray.py'),'--popup'],env=env,capture_output=True,timeout=5)
        assert remote.returncode==0,remote.stderr
        assert process.poll() is None
        assert Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()==children
        result=call('dev.codexbar.linux.tray','/dev/codexbar/linux/tray','org.gtk.Actions.Activate','quit','[]','{}')
        assert result.returncode==0,result.stderr
        assert process.wait(timeout=5)==0
        assert all(not Path('/proc',child).exists() for child in children)
        print('PASS: tray startup, popup startup, remote open, single instance, Quit, child cleanup')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)
