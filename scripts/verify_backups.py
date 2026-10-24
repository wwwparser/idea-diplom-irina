"""Verify PostgreSQL restore and a read-only mount of a scheduled web disk copy."""
import argparse,hashlib,json,time
from datetime import datetime,timezone
import remote
from prepare_cloud import load_env,ROOT
from src.services.yandex_client import YandexClient

def dump_check(vm):
    return remote.python(vm['fqdn'], '''
import os,subprocess,json,pathlib
os.chdir('/tmp')
def pg(*args):return subprocess.check_output(['sudo','-u','postgres',*args],text=True).strip()
pg('/usr/local/sbin/zabbix-dump')
dump=max(pathlib.Path('/var/backups/zabbix').glob('zabbix-*.dump'),key=lambda p:p.stat().st_mtime)
db='irina_diploma_restore_check'
assert pg('psql','-Atc',"SELECT count(*) FROM pg_database WHERE datname='"+db+"'")=='0','Test database already exists'
pg('createdb',db)
try:
 pg('pg_restore','--no-owner','--exit-on-error','--dbname='+db,str(dump))
 hosts=int(pg('psql','-d',db,'-Atc',"SELECT count(*) FROM hosts WHERE host LIKE 'irina-%.ru-central1.internal'"))
 assert hosts==6,hosts
 result={'dump':str(dump),'bytes':dump.stat().st_size,'restore_ok':True,'managed_hosts_restored':hosts}
finally:pg('dropdb',db)
result['temporary_database_removed']=True
print(json.dumps(result))
''',timeout=240)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump-only',action='store_true')
    args=parser.parse_args()
    load_env();c=YandexClient()
    machines=json.loads((ROOT/'terraform/output.json').read_bytes())['machines']['value']
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'postgresql':dump_check(machines['zabbix'])}
    evidence=ROOT/'evidence/full-backup-restore.json'
    evidence.write_text(json.dumps(result,indent=2)+'\n')
    if args.dump_only:
        print('PostgreSQL dump restored; six managed hosts verified; test database removed.')
        return
    disks={vm['disk_id'] for vm in machines.values()}
    snapshots=c.request('compute','compute/v1/snapshots?folderId=b1gj512d2ohptmg6691o&pageSize=1000').get('snapshots',[])
    ready=[s for s in snapshots if s.get('sourceDiskId') in disks and s.get('status')=='READY']
    assert {s['sourceDiskId'] for s in ready}==disks,'Need READY snapshots of all six current disks'
    result['snapshots']=[{k:s.get(k) for k in ('id','name','sourceDiskId','createdAt','status')} for s in ready]
    snapshot=next(s for s in ready if s['sourceDiskId']==machines['web-a']['disk_id'])
    existing=c.request('compute','compute/v1/disks?folderId=b1gj512d2ohptmg6691o').get('disks',[])
    assert not any(d.get('name')=='irina-restore-check' for d in existing),'Restore disk already exists; inspect before retry'
    disk=c.wait(c.request('compute','compute/v1/disks',method='POST',body={
        'folderId':'b1gj512d2ohptmg6691o','name':'irina-restore-check','zoneId':'ru-central1-d',
        'typeId':'network-ssd','size':snapshot['diskSize'],'snapshotId':snapshot['id']}))
    attached=False
    try:
        c.wait(c.request('compute','compute/v1/instances/'+machines['web-b']['id']+':attachDisk',method='POST',body={
            'attachedDiskSpec':{'diskId':disk['id'],'deviceName':'irina-restore-check','mode':'READ_WRITE','autoDelete':False}}))
        attached=True
        check=remote.python(machines['web-b']['fqdn'], '''
import json,pathlib,subprocess,time,hashlib
device='/dev/disk/by-id/virtio-irina-restore-check'
for _ in range(20):
 if pathlib.Path(device).exists():break
 time.sleep(1)
tree=json.loads(subprocess.check_output(['lsblk','-J','-o','PATH,FSTYPE',device],text=True))
def flatten(nodes):
 for n in nodes:
  yield n
  yield from flatten(n.get('children',[]))
roots=[n for n in flatten(tree['blockdevices']) if n.get('fstype')=='ext4']
assert len(roots)==1,roots
mount=pathlib.Path('/mnt/irina-restore-check')
mount.mkdir(exist_ok=True)
assert subprocess.run(['mountpoint','-q',str(mount)]).returncode!=0,'Mountpoint already in use'
subprocess.run(['mount','-o','ro,noload',roots[0]['path'],str(mount)],check=True)
try:
 digest=hashlib.sha256((mount/'var/www/html/index.html').read_bytes()).hexdigest()
 result={'snapshot_filesystem':roots[0]['path'],'mount_options':'ro,noload','site_sha256':digest}
finally:subprocess.run(['umount',str(mount)],check=True)
print(json.dumps(result))
''')
        expected=hashlib.sha256((ROOT/'site/index.html').read_bytes()).hexdigest()
        assert check['site_sha256']==expected
        result['web_disk_restore']={'snapshot_id':snapshot['id'],'temporary_disk_id':disk['id'],**check}
    finally:
        if attached:
            c.wait(c.request('compute','compute/v1/instances/'+machines['web-b']['id']+':detachDisk',method='POST',body={'diskId':disk['id']}))
        c.wait(c.request('compute','compute/v1/disks/'+disk['id'],method='DELETE'))
    result['temporary_disk_removed']=True
    evidence.write_text(json.dumps(result,indent=2)+'\n')
    print('All six snapshots READY; restored website hash matches; temporary disk detached/deleted.')

if __name__=='__main__':main()
