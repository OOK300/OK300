import json, urllib.parse, urllib.request, datetime, pathlib, time
ROOT=pathlib.Path(__file__).resolve().parent
QUERIES=['коммерческий директор','операционный директор','директор по развитию','директор по продажам','директор по клиентскому сервису','руководитель клиентского опыта','директор по партнерствам']
items={}
for q in QUERIES:
    params=urllib.parse.urlencode({'text':q,'area':113,'per_page':100,'page':0,'order_by':'publication_time'})
    req=urllib.request.Request('https://api.hh.ru/vacancies?'+params,headers={'User-Agent':'OK300 personal vacancy tracker (GitHub Actions)','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r: data=json.load(r)
    except Exception as e:
        print('Source error:',q,str(e));continue
    for v in data.get('items',[]):
        salary=v.get('salary') or {}; amount=salary.get('from') or salary.get('to')
        if salary.get('currency')!='RUR' or not amount or amount<250000:continue
        schedule=v.get('schedule') or {}; fmt='remote' if schedule.get('id')=='remote' else 'hybrid' if schedule.get('id')=='flexible' else 'office'
        if fmt!='remote':continue
        url=v.get('alternate_url')
        if not url:continue
        items[str(v['id'])]={'id':str(v['id']),'title':v.get('name',''),'company':(v.get('employer') or {}).get('name',''),'pay':amount,'salary_from':salary.get('from'),'salary_to':salary.get('to'),'work':fmt,'location':(v.get('area') or {}).get('name',''),'url':url,'published':v.get('published_at',''),'source':'hh.ru'}
    time.sleep(.4)
if not items:
    print('No results: keeping previous data to avoid replacing with empty data')
    raise SystemExit(0)
output={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'jobs':sorted(items.values(),key=lambda x:x['published'],reverse=True)}
(ROOT/'vacancies.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved',len(items),'vacancies')
