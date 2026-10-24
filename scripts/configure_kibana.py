"""Create read-only reviewer access and a reproducible nginx log dashboard."""
import json
from finish_debug import request,ROOT

def main():
    secrets=json.loads((ROOT/'.local/service-credentials.json').read_text())
    auth={'user':'elastic','password':secrets['elastic_password']}
    base='http://127.0.0.1:15601'
    headers={'kbn-xsrf':'true'}
    views=request(base+'/api/data_views',**auth)['data_view']
    view=next(v['id'] for v in views if v['title']=='nginx-*')
    searches=[]
    for ident,title,query in [('irina-nginx-access','Nginx access — both web servers','log_type: access'),
                              ('irina-nginx-errors','Nginx errors — both web servers','log_type: error')]:
        attributes={'title':title,'description':'Real Filebeat logs, grouped by source host using the host.name column.',
                    'columns':['host.name','log_type','message'],'sort':[['@timestamp','desc']],
                    'kibanaSavedObjectMeta':{'searchSourceJSON':json.dumps({'indexRefName':'kibanaSavedObjectMeta.searchSourceJSON.index','query':{'query':query,'language':'kuery'},'filter':[]})}}
        refs=[{'id':view,'type':'index-pattern','name':'kibanaSavedObjectMeta.searchSourceJSON.index'}]
        request(base+'/api/saved_objects/search/'+ident+'?overwrite=true',body={'attributes':attributes,'references':refs},headers=headers,**auth)
        searches.append(ident)
    panels=[{'type':'search','panelRefName':'panel_'+str(n),'panelIndex':str(n),
             'gridData':{'x':0,'y':n*14,'w':48,'h':14,'i':str(n)},'embeddableConfig':{}} for n in range(2)]
    dashboard='irina-nginx-logs'
    request(base+'/api/saved_objects/dashboard/'+dashboard+'?overwrite=true',headers=headers,body={
        'attributes':{'title':'Irina — nginx access and error logs','description':'Two nginx sources in different availability zones.',
                      'panelsJSON':json.dumps(panels),'optionsJSON':json.dumps({'useMargins':True,'hidePanelTitles':False}),
                      'timeRestore':True,'timeFrom':'now-24h','timeTo':'now','version':1,
                      'kibanaSavedObjectMeta':{'searchSourceJSON':json.dumps({'query':{'language':'kuery','query':''},'filter':[]})}},
        'references':[{'type':'search','id':ident,'name':'panel_'+str(n)} for n,ident in enumerate(searches)]},**auth)
    request(base+'/api/security/role/irina_reviewer',method='PUT',headers=headers,body={
        'elasticsearch':{'cluster':[],'indices':[{'names':['nginx-*'],'privileges':['read','view_index_metadata']}],'run_as':[]},
        'kibana':[{'base':['read'],'spaces':['*']}]
    },**auth)
    request('http://127.0.0.1:19200/_security/user/reviewer',method='PUT',body={
        'password':secrets['reviewer_password'],'roles':['irina_reviewer'],'full_name':'Diploma reviewer'},**auth)
    # Export saved object definitions only, without accounts, passwords or tokens.
    objects=[]
    for type_,ident in [('dashboard',dashboard)]+[('search',s) for s in searches]:
        objects.append(request(base+'/api/saved_objects/'+type_+'/'+ident,**auth))
    (ROOT/'evidence/kibana-saved-objects.json').write_text(json.dumps(objects,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Kibana dashboard ready:',dashboard,'; reviewer has read-only access to nginx-* only.')

if __name__=='__main__':main()
