"""Check the full deployment and test loss of one nginx, always restoring it."""
from datetime import datetime,timezone
import hashlib,json,time
from urllib.error import HTTPError
from urllib.request import build_opener,ProxyHandler
from prepare_cloud import load_env,ROOT
from src.services.yandex_client import YandexClient
import remote

def main():
    load_env(); cloud=YandexClient()
    output=json.loads((ROOT/'terraform/output.json').read_bytes())
    machines=output['machines']['value']; url=output['site_url']['value']
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'site_url':url,'machines':{},'http':{}}
    expected=hashlib.sha256((ROOT/'site/index.html').read_bytes()).hexdigest()
    common=['zabbix-agent','irina-metrics.timer']
    services={'web-a':['nginx','filebeat'],'web-b':['nginx','filebeat'],'bastion':[],
              'elasticsearch':['elasticsearch'],'zabbix':['zabbix-server','postgresql','nginx'],'kibana':['kibana']}
    for key,vm in machines.items():
        actual=cloud.request('compute','compute/v1/instances/'+vm['id'])
        assert actual['status']=='RUNNING'
        assert not actual['schedulingPolicy'].get('preemptible',False)
        if key in ('web-a','web-b','elasticsearch'):
            assert not actual['networkInterfaces'][0]['primaryV4Address'].get('oneToOneNat')
        code='import subprocess,json,pathlib,hashlib; units='+repr(common+services[key])+'; result={"services":{u:subprocess.check_output(["systemctl","is-active",u],text=True).strip() for u in units},"metrics":json.loads(pathlib.Path("/var/lib/irina-metrics/metrics.json").read_text())}; '
        if key.startswith('web-'):
            code+='result["site_sha256"]=hashlib.sha256(pathlib.Path("/var/www/html/index.html").read_bytes()).hexdigest(); '
        code+='print(json.dumps(result))'
        check=remote.python(vm['fqdn'],code)
        if key.startswith('web-'):assert check['site_sha256']==expected
        result['machines'][key]={'id':vm['id'],'zone':actual['zoneId'],'status':actual['status'],
                                  'preemptible':False,'private_ip':vm['private_ip'],'public_ip':vm['public_ip'],**check}
    opener=build_opener(ProxyHandler({}))
    def sample(count=20):
        rows=[]
        for _ in range(count):
            try:
                with opener.open(url+'/',timeout=10) as r:
                    body=r.read();rows.append({'status':r.status,'backend':r.headers.get('X-Backend'),
                                               'sha256':hashlib.sha256(body).hexdigest()})
            except HTTPError as e:
                rows.append({'status':e.code})
        return rows
    result['http']['normal']=sample()
    assert all(x['status']==200 and x['sha256']==expected for x in result['http']['normal'])
    assert {x['backend'] for x in result['http']['normal']}=={'irina-web-a','irina-web-b'}
    # Both access and error files receive real requests from the monitoring host.
    code='import urllib.request,urllib.error,json; result={}; '
    code+='\nfor host in '+repr([machines[k]['fqdn'] for k in ('web-a','web-b')])+':\n try:\n  urllib.request.urlopen("http://"+host+"/nginx_status",timeout=10)\n except urllib.error.HTTPError as e:\n  result[host]=e.code\nprint(json.dumps(result))'
    result['http']['restricted_status']=remote.python(machines['zabbix']['fqdn'],code)
    assert set(result['http']['restricted_status'].values())=={403}
    stopped=False
    try:
        remote.python(machines['web-a']['fqdn'],'import subprocess,json; subprocess.run(["systemctl","stop","nginx"],check=True);print(json.dumps({"stopped":True}))')
        stopped=True
        time.sleep(25)
        result['http']['web_a_stopped']=sample()
        assert all(x.get('status')==200 and x.get('backend')=='irina-web-b' and x.get('sha256')==expected for x in result['http']['web_a_stopped'])
    finally:
        if stopped:
            remote.python(machines['web-a']['fqdn'],'import subprocess,json; subprocess.run(["systemctl","start","nginx"],check=True);print(json.dumps({"restarted":True}))')
            result['http']['web_a_restarted']=True
        (ROOT/'evidence/full-infrastructure.json').write_text(json.dumps(result,indent=2)+'\n')
    time.sleep(25)
    result['http']['recovered']=sample()
    assert {x.get('backend') for x in result['http']['recovered']}=={'irina-web-a','irina-web-b'}
    (ROOT/'evidence/full-infrastructure.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Six native hosts verified; ALB balances both nodes and survives nginx shutdown; site SHA256 matches.')

if __name__=='__main__':main()
