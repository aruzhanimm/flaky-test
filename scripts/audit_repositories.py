"""Read public GitHub identity metadata. Never infer independence from URL text."""
import concurrent.futures, datetime, hashlib, json, time, urllib.request
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORRECTIONS={f'https://github.com/apache/apache/{p}':f'https://github.com/apache/{p}' for p in ('apex-core','curator','storm')}
class Meta(HTMLParser):
    def __init__(self): super().__init__(); self.items={}
    def handle_starttag(self,tag,attrs):
        if tag=='meta':
            a=dict(attrs)
            if a.get('name','').startswith('octolytics-dimension-repository_'): self.items[a['name'].removeprefix('octolytics-dimension-')]=a.get('content')

def main():
    meta=json.loads((ROOT/'data/audit/metadata_inventory.json').read_text())
    urls=sorted({m['project'] for m in meta}); dest=ROOT/'evidence/repositories';dest.mkdir(parents=True,exist_ok=True)
    def fetch(url):
        checked=CORRECTIONS.get(url,url); path=dest/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')
        if path.exists():
            prior=json.loads(path.read_text())
            if prior['status']=='verified': return prior
        r=dict(source_url=url,checked_url=checked,correction='Duplicate apache path segment' if checked!=url else None)
        for attempt in range(3):
            try:
                req=urllib.request.Request(checked,headers={'User-Agent':'ResearchMethodsDatasetAudit/1.0'})
                with urllib.request.urlopen(req,timeout=25) as response:
                    data=response.read(2_000_001); final=response.url
                if len(data)>2_000_000: raise ValueError('HTML size ceiling')
                parser=Meta();parser.feed(data.decode('utf-8'))
                if not parser.items.get('repository_id') or not parser.items.get('repository_network_root_id'): raise ValueError('No GitHub repository identity metadata')
                html_path=path.with_suffix('.html');html_path.write_bytes(data)
                r.update(status='verified',final_url=final,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),html_path=html_path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),**parser.items)
                break
            except Exception as e:
                r.update(status='unresolved',error=str(e))
                if attempt<2: time.sleep(2)
        path.write_text(json.dumps(r,indent=2),encoding='utf-8');return r
    result=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,url) for url in urls]
        for i,f in enumerate(concurrent.futures.as_completed(futures),1):
            r=f.result();result.append(r)
            if r['status']!='verified' or i%10==0: print(f'Repository identities {i}/{len(urls)}; latest {r["status"]} {r["source_url"]}',flush=True)
    result.sort(key=lambda x:x['source_url'])
    (ROOT/'data/audit/repository_identities.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    groups={r['repository_network_root_id'] for r in result if r['status']=='verified'}
    print(json.dumps(dict(urls=len(urls),verified=sum(r['status']=='verified' for r in result),github_network_groups=len(groups))),flush=True)

if __name__=='__main__': main()
