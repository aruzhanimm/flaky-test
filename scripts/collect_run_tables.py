"""Download archived target outcome tables with provenance and ZIP CRC checks."""
import argparse, concurrent.futures, hashlib, io, json, time, zlib
from pathlib import Path
from remote_zip import ROOT, FILE, HTTPRangeFile, extract_member, RateLimited

class Window(io.BytesIO):
    def __init__(self,data,start,total): super().__init__(data);self.start=start;self.size=total
    def seek(self,offset,whence=0):
        if whence!=0: raise ValueError('Only absolute archive seeks')
        return super().seek(offset-self.start)+self.start

def verify(data,item):
    if len(data)!=item['size'] or f'{zlib.crc32(data):08x}'!=item['crc32']: raise ValueError('Member CRC/size mismatch')

def download_items(items):
    out=ROOT/'data/extracted';out.mkdir(parents=True,exist_ok=True); records=[]
    remote=HTTPRangeFile(FILE['links']['self'],FILE['size'])
    pending=[]
    for item in items:
        path=out/(hashlib.sha256(item['path'].encode()).hexdigest()[:24]+Path(item['path']).suffix)
        r=dict(**item,local_path=path.relative_to(ROOT).as_posix())
        if path.exists():
            data=path.read_bytes();verify(data,item);r.update(sha256=hashlib.sha256(data).hexdigest(),status='verified');records.append(r)
        else: pending.append((item,path,r))
    source=remote
    if len(pending)>1:
        start=min(i['offset'] for i,_,_ in pending)
        end=max(i['offset']+30+len(i['path'].encode())+512+i['compressed'] for i,_,_ in pending)
        if end-start<=128_000:
            remote.seek(start);source=Window(remote.read(end-start),start,remote.size)
    for item,path,r in pending:
        data=extract_member(source,item);verify(data,item);path.write_bytes(data)
        r.update(sha256=hashlib.sha256(data).hexdigest(),status='verified');records.append(r)
    return records

def main():
    rows=json.loads((ROOT/'data/audit/archive_candidates.json').read_text());out=ROOT/'data/run_tables';out.mkdir(parents=True,exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('--labels',nargs='+');ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    if args.labels: rows={k:r for k,r in rows.items() if r['metadata']['label'] in args.labels}
    order={'TD':0,'NIO':1,'OD':2,'ID':3,'UNCLASSIFIED':4}
    rows=dict(sorted(rows.items(),key=lambda item:(order[item[1]['metadata']['label']],item[0])))
    def collect(pair):
        container,row=pair; path=out/(hashlib.sha256(container.encode()).hexdigest()[:24]+'.json')
        if path.exists():
            prior=json.loads(path.read_text())
            if prior['status']=='verified': return prior
        r=dict(container=container,metadata=row['metadata'],status='unresolved',members=[])
        items=row['summary_files']+row['rounds_files']
        if not items: r['status']='no_outcome_table'
        else:
            for attempt in range(3):
                try: r['members']=download_items(items);r['status']='verified';break
                except RateLimited as e:
                    r.update(status='deferred_rate_limit',error=str(e));break
                except Exception as e:
                    r['error']=str(e)
                    if attempt<2: time.sleep(1)
        path.write_text(json.dumps(r,indent=2),encoding='utf-8');return r
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(collect,pair) for pair in rows.items()]
        for i,f in enumerate(concurrent.futures.as_completed(futures),1):
            r=f.result();results.append(r)
            if i%50==0 or r['status']!='verified':print(f'Outcome tables {i}/{len(rows)}; latest {r["status"]} {r["container"]}',flush=True)
    name='run_table_manifest'+('_'+'_'.join(args.labels) if args.labels else '')+'.json'
    (ROOT/'data/audit'/name).write_text(json.dumps(sorted(results,key=lambda x:x['container']),separators=(',',':')),encoding='utf-8')
    print('Verified containers:',sum(r['status']=='verified' for r in results),flush=True)

if __name__=='__main__':main()
