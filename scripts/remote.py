"""Run a bounded Python command over the generated SSH config, with strict keys."""
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def python(host, code, timeout=180):
    if os.name=='nt':
        prefix=['wsl','-d','Ubuntu','--']
        config='/mnt/'+ROOT.drive[0].lower()+str(ROOT).replace('\\','/')[2:]+'/.local/ssh_config'
    else:
        prefix=[]
        config=str(ROOT/'.local/ssh_config')
    result=subprocess.run(prefix+['ssh','-F',config,'-o','ConnectTimeout=15',host,'sudo python3 -'],
                          input=code,capture_output=True,text=True,encoding='utf-8',timeout=timeout)
    if result.returncode:
        # Code is sent through stdin, never interpolated into shell arguments.
        # Do not use this helper for commands which print secret configuration.
        raise RuntimeError(f'Remote command failed on {host}: '+result.stderr[-3000:])
    return json.loads(result.stdout)
