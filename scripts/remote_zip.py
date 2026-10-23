"""Read a public ZIP through HTTP ranges; never download/execute project code."""
import argparse, collections, datetime, email.utils, hashlib, io, json, struct, urllib.request, urllib.error, zlib, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'evidence').mkdir(exist_ok=True)
RECORD=json.loads((ROOT/'data/source/zenodo_results_record.json').read_text())
FILE=RECORD['files'][0]
_network_lock=threading.Lock()
_next_request=0.0
_request_history=None
_covering_ranges=None
class RateLimited(RuntimeError): pass

def respectful_open(request):
    """One collector: <=48 requests/minute, <=1800/hour; obey server cooldown.

    Public guest limits checked at developers.zenodo.org on 2026-10-13:
    60/minute and 2000/hour. Lower internal caps preserve a safety margin.
    """
    global _next_request,_request_history
    pause=ROOT/'evidence/zenodo_rate_limit.json'
    with _network_lock:
        attempts=ROOT/'evidence/http_attempts.jsonl'
        if _request_history is None:
            existing=[json.loads(s)['epoch'] for s in attempts.read_text().splitlines()] if attempts.exists() else []
            first=min(existing) if existing else float('inf')
            legacy=ROOT/'evidence/range_requests.jsonl'
            earlier=[datetime.datetime.fromisoformat(json.loads(s)['utc']).timestamp() for s in legacy.read_text().splitlines()] if legacy.exists() else []
            _request_history=sorted([t for t in earlier if t<first]+existing)
        now=time.time();_request_history=[t for t in _request_history if t>now-3600]
        if len(_request_history)>=1800:
            raise RateLimited('Internal hourly cap reached; resume after oldest request expires')
        if pause.exists():
            state=json.loads(pause.read_text())
            if time.time()<state['retry_at_epoch']:
                raise RateLimited(f'Zenodo cooldown until {state["retry_at_utc"]}')
        delay=max(0,_next_request-time.monotonic())
        if delay: time.sleep(delay)
        _next_request=time.monotonic()+1.25
        now=time.time();_request_history.append(now)
        with attempts.open('a') as f:f.write(json.dumps(dict(epoch=now,url=request.full_url,utc=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat()))+'\n')
    try:
        response=urllib.request.urlopen(request,timeout=60)
        headers={k:v for k,v in response.headers.items() if k.lower().startswith('x-ratelimit')}
        if headers:
            with (ROOT/'evidence/http_rate_headers.jsonl').open('a') as f:f.write(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),headers=headers))+'\n')
        return response
    except urllib.error.HTTPError as error:
        if error.code!=429: raise
        retry=error.headers.get('Retry-After','')
        try: seconds=max(300,float(retry))
        except ValueError:
            try:seconds=max(300,email.utils.parsedate_to_datetime(retry).timestamp()-time.time())
            except (ValueError,TypeError):seconds=300
        until=time.time()+seconds
        state=dict(status=429,retry_after_header=retry,retry_at_epoch=until,retry_at_utc=datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat(),observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),headers=dict(error.headers))
        pause.write_text(json.dumps(state,indent=2),encoding='utf-8')
        raise RateLimited(f'Zenodo returned 429; cooldown until {state["retry_at_utc"]}') from error
class HTTPRangeFile(io.RawIOBase):
    def __init__(self,url,size):
        self.url=url; self.size=size; self.pos=0; self.transferred=0
        self.cache=ROOT/'data/cache/ranges'; self.cache.mkdir(parents=True,exist_ok=True)
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self,offset,whence=0):
        self.pos = offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        if self.pos<0: raise ValueError('Negative seek')
        return self.pos
    def read(self,n=-1):
        global _covering_ranges
        n=min(n if n>=0 else self.size-self.pos,self.size-self.pos)
        if n<=0: return b''
        if n>150_000_000: raise ValueError(f'Oversized range {n}')
        start=self.pos; end=start+n-1
        cache=self.cache/f'{start}_{end}.bin'
        if cache.exists(): data=cache.read_bytes()
        else:
            if _covering_ranges is None:
                _covering_ranges=[]
                for candidate in self.cache.glob('*.bin'):
                    try:a,b=map(int,candidate.stem.split('_'))
                    except ValueError:continue
                    if b-a>=200_000:_covering_ranges.append((a,b,candidate))
            covering=next(((a,b,p) for a,b,p in _covering_ranges if a<=start and end<=b),None)
            if covering:
                a,b,p=covering
                with p.open('rb') as stream:stream.seek(start-a);data=stream.read(n)
                if len(data)!=n:raise ValueError('Cached covering range is incomplete')
                self.pos+=len(data);return data
            req=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{end}','User-Agent':'ResearchMethodsDatasetAudit/1.0'})
            with respectful_open(req) as r:
                if r.status!=206: raise RuntimeError(f'Server ignored range: {r.status}')
                expected=f'bytes {start}-{end}/{self.size}'
                if r.headers.get('Content-Range')!=expected: raise RuntimeError(f'Wrong Content-Range: {r.headers.get("Content-Range")} expected {expected}')
                data=r.read(n+1)
                if len(data)!=n: raise RuntimeError(f'Range length mismatch expected={n} actual={len(data)} headers={dict(r.headers)}')
            cache.write_bytes(data); self.transferred+=len(data)
            if n>=200_000:_covering_ranges.append((start,end,cache))
            with (ROOT/'evidence/range_requests.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(dict(url=self.url,start=start,end=end,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))+'\n')
        self.pos+=len(data)
        return data

def extract_member(remote,item):
    """Extract using the recorded central entry and verify size and CRC32."""
    offset=item['offset']; n=min(30+len(item['path'].encode('utf-8'))+512+item['compressed'],remote.size-offset)
    remote.seek(offset); packet=remote.read(n)
    h=struct.unpack_from('<4s5H3L2H',packet)
    if h[0]!=b'PK\x03\x04' or h[2]&1: raise ValueError('Invalid or encrypted member')
    name=packet[30:30+h[9]].decode('utf-8' if h[2]&0x800 else 'cp437')
    if name!=item['path']: raise ValueError('Local/central name mismatch')
    start=30+h[9]+h[10]; need=start+item['compressed']
    if need>len(packet):
        remote.seek(offset+len(packet)); packet+=remote.read(need-len(packet))
    compressed=packet[start:need]
    if item['method']==8: data=zlib.decompress(compressed,-15)
    elif item['method']==0: data=compressed
    else: raise ValueError('Unsupported ZIP compression')
    if len(data)!=item['size'] or f'{zlib.crc32(data):08x}'!=item['crc32']: raise ValueError('Member integrity failure')
    return data

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--index',action='store_true'); ap.add_argument('--preview',action='store_true'); ap.add_argument('--member'); a=ap.parse_args()
    remote=HTTPRangeFile(FILE['links']['self'],FILE['size'])
    if a.index or a.preview:
        remote.seek(-22,2); end=struct.unpack('<4s4H2LH',remote.read(22))
        size,offset=end[5:7]
        print(json.dumps({'central_directory_bytes':size,'central_directory_offset':offset}),flush=True)
        buffer=b''; count=0; kept=0; suffixes=collections.Counter(); top=collections.Counter(); examples=[]
        out=ROOT/'data/source/result_zip_index.jsonl'
        with out.open('w',encoding='utf-8') as f:
            chunk_size=8_000_000 if a.preview else 1_000_000
            for start in range(offset,offset+size,chunk_size):
                remote.seek(start); buffer+=remote.read(min(chunk_size,offset+size-start))
                pos=0
                while pos+46<=len(buffer):
                    if buffer[pos:pos+4]!=b'PK\x01\x02': raise ValueError('Bad central directory signature')
                    h=struct.unpack_from('<4s6H3L5H2L',buffer,pos)
                    length=46+h[10]+h[11]+h[12]
                    if pos+length>len(buffer): break
                    name=buffer[pos+46:pos+46+h[10]].decode('utf-8' if h[3]&0x800 else 'cp437')
                    item=dict(path=name,size=h[9],compressed=h[8],crc32=f'{h[7]:08x}',offset=h[16],method=h[4])
                    count+=1; suffixes[Path(name).suffix]+=1
                    parts=name.split('/'); top['/'.join(parts[:3])]+=1
                    if len(examples)<45: examples.append(item)
                    # Preserve every file index, excluding directory entries only.
                    if not name.endswith('/'):
                        f.write(json.dumps(item)+'\n'); kept+=1
                    pos+=length
                buffer=buffer[pos:]
                print(f'Indexed {count} entries; downloaded {remote.transferred} bytes',flush=True)
                if a.preview: break
        summary=dict(entries=count,files=kept,complete=not a.preview,suffixes=dict(suffixes),top=dict(top),http_bytes=remote.transferred,examples=examples)
        (ROOT/'data/source/result_zip_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(json.dumps(examples[:20],indent=2)); return
    if a.member:
        item=next((json.loads(line) for line in (ROOT/'data/source/result_zip_index.jsonl').open() if json.loads(line)['path']==a.member),None)
        if item is None: raise ValueError('Member absent from local index; index may be incomplete')
        data=extract_member(remote,item)
        out=ROOT/'data/sample'/(hashlib.sha256(a.member.encode()).hexdigest()[:16]+Path(a.member).suffix)
        out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
        print(json.dumps({'member':a.member,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'http_bytes':remote.transferred,'path':str(out)},indent=2))
if __name__=='__main__': main()
