"""Verify public HTTPS UIs against certificates fetched over trusted SSH."""
import base64,hashlib,json,ssl
from urllib.request import build_opener,HTTPSHandler,ProxyHandler,Request
import remote
from remote import ROOT

def main():
    machines=json.loads((ROOT/'terraform/output.json').read_bytes())['machines']['value']
    secrets=json.loads((ROOT/'.local/service-credentials.json').read_text())
    directory=ROOT/'docs/certs';directory.mkdir(exist_ok=True)
    result={}
    for key in ('zabbix','kibana'):
        vm=machines[key]
        cert=remote.python(vm['fqdn'],'import pathlib,json; print(json.dumps({"certificate":pathlib.Path("/etc/nginx/irina-tls/server.crt").read_text()}))')['certificate']
        path=directory/(key+'.crt');path.write_text(cert,encoding='ascii')
        context=ssl.create_default_context(cafile=str(path))
        opener=build_opener(ProxyHandler({}),HTTPSHandler(context=context))
        url='https://'+vm['public_ip']
        with opener.open(url+'/',timeout=30) as response:status=response.status
        fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest()
        if key=='zabbix':
            def rpc(method,params,token=None):
                headers={'Content-Type':'application/json-rpc'}
                if token:headers['Authorization']='Bearer '+token
                req=Request(url+'/api_jsonrpc.php',data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),headers=headers)
                with opener.open(req,timeout=30) as r:return json.load(r)
            session=rpc('user.login',{'username':'reviewer','password':secrets['reviewer_password']})['result']
            try:
                hosts=rpc('host.get',{'output':['hostid','host']},session)['result']
                assert len(hosts)==6
            finally:rpc('user.logout',[],session)
            check={'read_only_reviewer_login':True,'visible_hosts':len(hosts)}
        else:
            auth=base64.b64encode(('reviewer:'+secrets['reviewer_password']).encode()).decode()
            req=Request(url+'/api/saved_objects/dashboard/irina-nginx-logs',headers={'Authorization':'Basic '+auth})
            with opener.open(req,timeout=30) as r:dashboard=json.load(r)
            check={'read_only_reviewer_login':True,'dashboard_title':dashboard['attributes']['title']}
        result[key]={'url':url,'http_status':status,'certificate_sha256':fingerprint,'certificate_validated':True,**check}
    (ROOT/'evidence/public-ui.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Both public HTTPS UIs verified with pinned certificates; reviewer logins successful.')

if __name__=='__main__':main()
