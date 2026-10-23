"""Fetch public evidence without executing downloaded code; record SHA256."""
import argparse, datetime, hashlib, json, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('url'); parser.add_argument('destination')
args=parser.parse_args()
dest=(ROOT/args.destination).resolve()
if not dest.is_relative_to(ROOT): raise ValueError('Destination outside project')
dest.parent.mkdir(parents=True,exist_ok=True)
record={'url':args.url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'local_date':datetime.datetime.now().astimezone().date().isoformat(),'path':dest.relative_to(ROOT).as_posix()}
try:
    req=urllib.request.Request(args.url,headers={'User-Agent':'ResearchMethodsDatasetAudit/1.0'})
    with urllib.request.urlopen(req,timeout=45) as resp:
        data=resp.read(100_000_001)
        if len(data)>100_000_000: raise ValueError('File exceeds 100 MB audit limit')
        record.update(status=resp.status,final_url=resp.url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),content_type=resp.headers.get('Content-Type'))
    dest.write_bytes(data)
except Exception as e:
    record.update(status='failed',error=str(e))
(ROOT/'evidence').mkdir(exist_ok=True)
with (ROOT/'evidence'/'downloads.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(record)+'\n')
print(json.dumps(record,indent=2))
if record['status']=='failed': raise SystemExit(1)
