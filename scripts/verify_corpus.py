"""Trace every retained example back to a CRC/hash-verified target diagnostic."""
import argparse,collections,hashlib,json,re,zlib
from pathlib import Path
from parse_failure import parse,digest
from audit_outcome_tables import parse_table
from representations import clean,EXCEPTION
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--corpus',default='data/processed/corpus.jsonl');ap.add_argument('--output',default='data/audit/corpus_verification.json');args=ap.parse_args()
    rows=[json.loads(x) for x in (ROOT/args.corpus).read_text(encoding='utf-8').splitlines()]
    ledger={r['container']:r for p in (ROOT/'data/first_failures').glob('*.json') for r in [json.loads(p.read_text())]}
    checked=[];residuals=[]
    for r in rows:
        entry=ledger[r['container']];m=entry['diagnostic_member'];data=(ROOT/m['local_path']).read_bytes()
        assert len(data)==m['size'] and f'{zlib.crc32(data):08x}'==m['crc32']
        assert hashlib.sha256(data).hexdigest()==m['sha256']
        if r['format']=='nio_json':
            outcomes,issues=parse_table(data.decode('utf-8-sig'),entry['metadata'])
            target=next(v for v in outcomes if v['row']==entry['source_row'])
            parsed=parse(json.dumps(target['embedded_nio']).encode(),'/test-runs/results/embedded',r['configured_test'])
        else:parsed=parse(data,m['path'],r['configured_test'])
        assert parsed['failures'] and digest(parsed['failures'][0]['text'])==entry['text_sha256']
        assert clean(parsed['failures'][0]['text'])==r['original_text']
        assert digest(r['original_text'])==r['original_sha256'] and digest(r['masked_text'])==r['masked_sha256']
        exceptions=set(EXCEPTION.findall(r['original_text']))
        if r['exception_type']:exceptions.add(r['exception_type'])
        assert all(value in r['masked_text'] for value in exceptions)
        klass,method=r['configured_test'].split('#',1)
        stripped=r['masked_text']
        for exception in sorted(exceptions,key=len,reverse=True):stripped=stripped.replace(exception,'EXCEPTION')
        assert klass not in stripped
        # Names of other classes, line numbers and common runtime frames remain by design.
        packages=sorted(set(re.findall(r'\b(?:org|com|net)\.[\w$.]+',stripped)))
        own=[p for p in packages if not p.startswith(('org.junit.','org.mockito.','org.hamcrest.','org.testng.','org.opentest4j.','org.PROJECT.','com.PROJECT.','net.PROJECT.'))]
        if own:residuals.append(dict(sample_id=r['sample_id'],container=r['container'],label=r['label'],remaining_qualified_tokens=own[:20]))
        checked.append(r['sample_id'])
    result=dict(corpus=args.corpus,tests=len(rows),all_members_crc_size_sha256_verified=True,all_rows_reparsed_exact_target=True,all_original_texts_match_source=True,all_recorded_exception_names_preserved=True,target_fully_qualified_class_absent_outside_preserved_exceptions=True,rows_with_remaining_qualified_tokens=len(residuals),residual_caution='Heuristic flags for manual inspection; includes third-party libraries and does not quantify complete de-identification',residual_examples=residuals)
    (ROOT/args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='residual_examples'}))
if __name__=='__main__':main()
