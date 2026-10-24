"""Run the pinned WSL Ansible environment and preserve a private execution log."""
import argparse,subprocess
from datetime import datetime,timezone
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit')
    parser.add_argument('--syntax-check',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    linux='/mnt/'+root.drive[0].lower()+str(root).replace('\\','/')[2:]
    command=['wsl','-d','Ubuntu','--','env','PYTHONPATH=/home/yuri/.cache/irina-check/libs',
        'PATH=/home/yuri/.cache/irina-check/libs/bin:/usr/bin:/bin',
        'ANSIBLE_COLLECTIONS_PATH=/home/yuri/.cache/irina-check/collections',
        'ANSIBLE_CONFIG='+linux+'/ansible/ansible.cfg','/home/yuri/.cache/irina-check/libs/bin/ansible-playbook',
        linux+'/ansible/site.yml','-i',linux+'/ansible/inventory/hosts.yml',
        '--vault-password-file','/home/yuri/.local/share/diplom-irina/vault-pass']
    if args.limit:command+=['--limit',args.limit]
    if args.syntax_check:command+=['--syntax-check']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log=root/'.local'/('ansible-full-'+stamp+'.log')
    print('Log:',log,flush=True)
    with log.open('w',encoding='utf-8') as stream:
        process=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    print('Ansible exit:',process.returncode,flush=True)
    print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-12:]))
    return process.returncode

if __name__=='__main__':raise SystemExit(main())
