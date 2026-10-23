"""Resume the complete public ZIP directory; bounded concurrent range downloads.

Downloads directory metadata only, not the 2.6 GB archive or project code.
Leaves the previous index intact until all directory records are verified.
"""
import concurrent.futures, collections, hashlib, json, struct, time
from pathlib import Path
from remote_zip import ROOT, FILE, HTTPRangeFile

def main():
    remote=HTTPRangeFile(FILE['links']['self'], FILE['size'])
    remote.seek(-22,2)
    end=struct.unpack('<4s4H2LH',remote.read(22))
    if end[0]!=b'PK\x05\x06' or end[-1]: raise ValueError('Unsupported ZIP footer')
    size,offset=end[5:7]
    expected=end[4]
    if expected==65535:
        remote.seek(FILE['size']-42)
        loc=struct.unpack('<4sLQL',remote.read(20))
        if loc[0]!=b'PK\x06\x07': raise ValueError('Missing ZIP64 locator')
        remote.seek(loc[2]); z=struct.unpack('<4sQ2H2L4Q',remote.read(56))
        if z[0]!=b'PK\x06\x06' or z[8:]!=(size,offset): raise ValueError('ZIP64 directory disagreement')
        expected=z[7]
    chunk=1_000_000
    spans=[(s,min(chunk,offset+size-s)) for s in range(offset,offset+size,chunk)]
    # Reuse existing larger preview ranges without another network transfer.
    caches=[]
    for path in remote.cache.glob('*.bin'):
        a,b=map(int,path.stem.split('_'))
        if b-a+1>chunk and offset<=a<offset+size: caches.append((a,b,path))
    def fetch(span):
        s,n=span; r=HTTPRangeFile(FILE['links']['self'],FILE['size'])
        target=r.cache/f'{s}_{s+n-1}.bin'
        if not target.exists():
            for a,b,path in caches:
                if a<=s and s+n-1<=b:
                    with path.open('rb') as f: f.seek(s-a); data=f.read(n)
                    if len(data)!=n: raise ValueError('Short cache')
                    target.write_bytes(data); break
        for attempt in range(3):
            try:
                r.seek(s); data=r.read(n)
                if len(data)!=n: raise ValueError('Cache size mismatch')
                return s,len(data)
            except Exception:
                if attempt==2: raise
                time.sleep(1+attempt)
    print(json.dumps({'directory_bytes':size,'expected_entries':expected,'chunks':len(spans)}),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(fetch,span):span for span in spans}
        for done,f in enumerate(concurrent.futures.as_completed(futures),1):
            f.result()
            if done%10==0 or done==len(spans): print(f'Directory ranges verified: {done}/{len(spans)}',flush=True)
    out=ROOT/'data/source/result_zip_index.complete.jsonl'
    buffer=b''; count=0; files=0; categories=collections.Counter(); containers=collections.Counter()
    directory_hash=hashlib.sha256()
    with out.open('w',encoding='utf-8') as f:
        for s,n in spans:
            data=(remote.cache/f'{s}_{s+n-1}.bin').read_bytes(); directory_hash.update(data); buffer+=data
            pos=0
            while pos+46<=len(buffer):
                h=struct.unpack_from('<4s6H3L5H2L',buffer,pos)
                if h[0]!=b'PK\x01\x02': raise ValueError('Bad directory signature')
                length=46+h[10]+h[11]+h[12]
                if pos+length>len(buffer): break
                name=buffer[pos+46:pos+46+h[10]].decode('utf-8' if h[3]&0x800 else 'cp437')
                if 0xffffffff in (h[8],h[9],h[16]): raise ValueError('ZIP64 member requires explicit parser extension')
                count+=1
                if not name.endswith('/'):
                    row=dict(path=name,size=h[9],compressed=h[8],crc32=f'{h[7]:08x}',offset=h[16],method=h[4])
                    f.write(json.dumps(row,separators=(',',':'))+'\n'); files+=1
                    parts=name.split('/'); containers[parts[1] if len(parts)>1 else name]+=1; categories[Path(name).suffix]+=1
                pos+=length
            buffer=buffer[pos:]
    if buffer or count!=expected: raise ValueError(f'Incomplete directory: {count}/{expected}, tail={len(buffer)}')
    summary=dict(complete=True,entries=count,files=files,containers=dict(containers),suffixes=dict(categories),central_directory_bytes=size,central_directory_sha256=directory_hash.hexdigest(),archive_md5_verified=False)
    (ROOT/'data/source/result_zip_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    out.replace(ROOT/'data/source/result_zip_index.jsonl')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('containers','suffixes')}),flush=True)

if __name__=='__main__': main()
