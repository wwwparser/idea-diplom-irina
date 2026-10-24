"""Keep local SSH tunnels open for administrative service access (Ctrl+C closes)."""
import os,subprocess,time
from remote import ROOT

def main():
    windows=os.name=='nt'
    config=('/mnt/'+ROOT.drive[0].lower()+str(ROOT).replace('\\','/')[2:]+'/.local/ssh_config') if windows else str(ROOT/'.local/ssh_config')
    prefix=['wsl','-d','Ubuntu','--'] if windows else []
    processes=[]
    try:
        for host,local,port in [('zabbix',18080,8080),('kibana',15601,5601),('elasticsearch',19200,9200)]:
            processes.append(subprocess.Popen(prefix+['ssh','-N','-F',config,'-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30',
                '-L',f'127.0.0.1:{local}:127.0.0.1:{port}',f'irina-{host}.ru-central1.internal'],stdout=subprocess.DEVNULL))
        print('Tunnels: Zabbix 127.0.0.1:18080; Kibana 127.0.0.1:15601; Elasticsearch 127.0.0.1:19200',flush=True)
        while all(p.poll() is None for p in processes):time.sleep(3)
        raise RuntimeError('An SSH tunnel exited; check connectivity before restarting.')
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()

if __name__=='__main__':main()
