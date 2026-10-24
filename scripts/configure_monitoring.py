"""Create USE items, thresholds, graphs and a dashboard using Zabbix 7 API."""
import argparse
import json
from pathlib import Path
from zabbix_bootstrap import Zabbix
from finish_debug import request, ROOT

# metric key: (label, unit); dependent items consume the root-owned JSON collector.
METRICS = {
    'cpu_util': ('CPU utilization', '%'),
    'cpu_load_per_core': ('CPU load per logical core', ''),
    'cpu_queue': ('Runnable tasks', ''),
    'ram_used_pct': ('RAM utilization', '%'),
    'ram_available_bytes': ('Available RAM', 'B'),
    'swap_pages_per_second': ('Swap activity', 'pages/s'),
    'oom_kills_per_second': ('Guest OOM kills', 'events/s'),
    'cpu_psi_pct': ('CPU pressure avg10', '%'),
    'memory_psi_pct': ('Memory pressure avg10', '%'),
    'io_psi_pct': ('IO pressure avg10', '%'),
    'disk_used_pct': ('Root filesystem utilization', '%'),
    'disk_util_pct': ('Disk IO utilization (busiest disk)', '%'),
    'disk_await_ms': ('Disk latency (busiest disk)', 'ms'),
    'disk_queue': ('Disk requests in flight', ''),
    'disk_io_errors_60s': ('Guest kernel IO errors in last minute', ''),
    'kernel_errors_60s': ('Guest kernel fault messages in last minute', ''),
    'net_rx_per_second': ('Network receive', 'Bps'),
    'net_tx_per_second': ('Network transmit', 'Bps'),
    'net_errors_per_second': ('Network errors', 'events/s'),
    'net_drops_per_second': ('Network drops', 'events/s'),
    'http_rps': ('HTTP requests per second', 'req/s'),
    'http_active': ('HTTP active connections', ''),
    'http_waiting': ('HTTP waiting connections', ''),
    'http_requests_60s': ('HTTP sample size in last minute', ''),
    'http_5xx_pct': ('HTTP server error share', '%'),
    'http_latency_seconds': ('HTTP average response time', 's'),
    'http_sample_truncated': ('HTTP sample truncated (reduce load or increase tail)', ''),
}

def configure(api, hosts, web_names):
    pages = []
    for host in hosts:
        hostid, fqdn = host['hostid'], host['host']
        existing = {i['key_']: i['itemid'] for i in api.call('item.get', {'hostids': [hostid], 'output': ['key_', 'itemid']})}
        def item(key, name, **extra):
            if key in existing:
                return existing[key]
            value = api.call('item.create', dict(hostid=hostid, key_=key, name=name, **extra))['itemids'][0]
            existing[key] = value
            return value
        master = item('irina.health', 'Irina: guest USE metrics JSON', type=7, value_type=4, delay='15s', history='1d', trends='0')
        items = {}
        for key, (label, unit) in METRICS.items():
            if key.startswith('http_') and fqdn not in web_names:
                continue
            items[key] = item('irina.'+key, label, type=18, value_type=0, master_itemid=master, delay='0',
                              units=unit, history='7d', trends='30d',
                              preprocessing=[{'type':12,'params':'$.'+key,'error_handler':0}])
        def threshold(value):
            return item('irina.threshold['+str(value)+']', 'Threshold: '+str(value), type=15,
                        value_type=0, params=str(value), delay='30s', history='7d', trends='30d')
        definitions = [
            ('CPU utilization', ['cpu_util'], 80),
            ('CPU saturation: load per core', ['cpu_load_per_core'], 1),
            ('RAM utilization', ['ram_used_pct'], 90),
            ('RAM saturation: pressure and swap', ['memory_psi_pct','swap_pages_per_second'], None),
            ('Disk space utilization', ['disk_used_pct'], 80),
            ('Disk IO utilization', ['disk_util_pct'], 90),
            ('Disk saturation: await', ['disk_await_ms'], 50),
            ('Disk saturation: queue', ['disk_queue'], None),
            ('Network utilization', ['net_rx_per_second','net_tx_per_second'], None),
            ('Network errors and drops', ['net_errors_per_second','net_drops_per_second'], 0),
            ('Guest errors: kernel, IO, OOM', ['kernel_errors_60s','disk_io_errors_60s','oom_kills_per_second'], 0),
            ('Pressure: CPU and IO', ['cpu_psi_pct','io_psi_pct'], 5),
        ]
        if fqdn in web_names:
            definitions += [
                ('HTTP utilization: request rate', ['http_rps'], None),
                ('HTTP saturation: connections', ['http_active','http_waiting'], None),
                ('HTTP latency', ['http_latency_seconds'], 1),
                ('HTTP errors: 5xx share', ['http_5xx_pct'], 1),
            ]
        graphs = {g['name']:g['graphid'] for g in api.call('graph.get', {'hostids':[hostid], 'output':['name','graphid']})}
        widgets = []
        palette = ['199C0D','2774A4','A54F10']
        for number, (label, keys, limit) in enumerate(definitions):
            name = 'USE: '+label
            gitems = [{'itemid':items[key], 'color':palette[i], 'sortorder':i, 'drawtype':0} for i,key in enumerate(keys)]
            if limit is not None:
                gitems.append({'itemid':threshold(limit), 'color':'E53935', 'sortorder':len(keys), 'drawtype':2})
            params = {'name':name,'width':900,'height':220,'show_legend':1,'gitems':gitems}
            if name in graphs:
                api.call('graph.update',dict(graphid=graphs[name], **params))
            else:
                graphs[name]=api.call('graph.create',params)['graphids'][0]
            widgets.append({'type':'graph','name':label,'x':(number%2)*36,'y':(number//2)*5,'width':36,'height':5,
                            'fields':[{'type':0,'name':'source_type','value':0}, {'type':6,'name':'graphid','value':graphs[name]}]})
        pages.append({'name':fqdn.split('.')[0], 'widgets':widgets})
        triggers = {t['description'] for t in api.call('trigger.get',{'hostids':[hostid],'output':['description']})}
        rules = [
            ('CPU busy >80% for 5m','cpu_util','avg', '5m','>80',3),
            ('CPU load/core >1 for 5m','cpu_load_per_core','avg','5m','>1',2),
            ('RAM used >90% for 5m','ram_used_pct','avg','5m','>90',3),
            ('Filesystem used >80%','disk_used_pct','last','','>80',3),
            ('Disk busy >90% for 5m','disk_util_pct','avg','5m','>90',3),
            ('Disk await >50ms for 5m','disk_await_ms','avg','5m','>50',2),
            ('Guest IO errors detected','disk_io_errors_60s','max','1m','>0',4),
            ('Guest kernel fault detected','kernel_errors_60s','max','1m','>0',4),
            ('Guest OOM kill detected','oom_kills_per_second','max','1m','>0',4),
            ('Network errors detected','net_errors_per_second','max','1m','>0',3),
            ('Network drops detected','net_drops_per_second','avg','5m','>0',2),
        ]
        if fqdn in web_names:
            rules += [('HTTP mean latency >1s','http_latency_seconds','avg','5m','>1',3),
                      ('HTTP 5xx >1%','http_5xx_pct','avg','5m','>1',3),
                      ('HTTP sample truncated','http_sample_truncated','last','','>0',2)]
        for label,key,func,window,comparison,priority in rules:
            name='Irina: '+label
            expression=f'{func}(/{fqdn}/irina.{key}'+(','+window if window else '')+')'+comparison
            if key=='http_5xx_pct':
                expression+=f' and last(/{fqdn}/irina.http_requests_60s)>=20'
            if name not in triggers:
                api.call('trigger.create',{'description':name,'expression':expression,'priority':priority,
                                          'tags':[{'tag':'project','value':'irina'},{'tag':'resource','value':key.split('_')[0]}]})
        if fqdn in web_names:
            name='Irina: HTTP scenario failed'
            if name not in triggers:
                api.call('trigger.create',{'description':name,'expression':f'last(/{fqdn}/web.test.fail[Homepage])<>0','priority':4})
        print('USE metrics/graphs/triggers ready:',fqdn,flush=True)
    name='Irina — USE infrastructure'
    dashboards=api.call('dashboard.get',{'filter':{'name':[name]}})
    params={'name':name,'display_period':30,'auto_start':0,'private':0,'pages':pages}
    if dashboards:
        dashboardid=dashboards[0]['dashboardid']
        api.call('dashboard.update',dict(dashboardid=dashboardid,**params))
    else:
        dashboardid=api.call('dashboard.create',params)['dashboardids'][0]
    export=api.call('dashboard.get',{'dashboardids':[dashboardid],'selectPages':'extend','output':'extend'})
    (ROOT/'evidence/zabbix-dashboard.json').write_text(json.dumps(export,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    host_export=api.call('configuration.export',{'format':'json','options':{'hosts':[h['hostid'] for h in hosts]}})
    (ROOT/'evidence/zabbix-hosts-export.json').write_text(host_export+'\n',encoding='utf-8')
    return dashboardid

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:18080')
    parser.add_argument('--inventory',type=Path,default=ROOT/'ansible/inventory/hosts.yml')
    args=parser.parse_args()
    secrets=json.loads((ROOT/'.local/service-credentials.json').read_text())
    result=request(args.url+'/api_jsonrpc.php',{'jsonrpc':'2.0','id':1,'method':'user.login','params':{'username':'Admin','password':secrets['zabbix_admin_password']}})
    api=Zabbix(args.url,result['result'])
    try:
        inventory=json.loads(args.inventory.read_text())
        names={h for g in inventory['all']['children'].values() for h in g['hosts']}
        hosts=api.call('host.get',{'filter':{'host':sorted(names)},'output':['hostid','host']})
        dashboard=configure(api,hosts,set(inventory['all']['children']['web']['hosts']))
        groupid=api.call('hostgroup.get',{'filter':{'name':['Irina infrastructure']}})[0]['groupid']
        reviewer_groups=api.call('usergroup.get',{'filter':{'name':['Irina reviewers']}})
        reviewer_group=reviewer_groups[0]['usrgrpid'] if reviewer_groups else api.call('usergroup.create',{
            'name':'Irina reviewers','hostgroup_rights':[{'id':groupid,'permission':2}]})['usrgrpids'][0]
        roles=api.call('role.get',{'output':['roleid','type']})
        role=next(r['roleid'] for r in roles if r['type']=='1')
        if not api.call('user.get',{'filter':{'username':['reviewer']}}):
            api.call('user.create',{'username':'reviewer','passwd':secrets['reviewer_password'],
                                   'roleid':role,'usrgrps':[{'usrgrpid':reviewer_group}]})
        print('Dashboard ID:',dashboard)
    finally:
        api.call('user.logout',[])

if __name__=='__main__':
    main()
