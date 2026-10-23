"""Audit every archive path, then retain candidate target diagnostics only."""
import collections, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def natural(path):
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)',path)]

def main():
    summary=json.loads((ROOT/'data/source/result_zip_summary.json').read_text())
    if not summary['complete']: raise ValueError('Complete archive index required')
    metadata=json.loads((ROOT/'data/audit/metadata_inventory.json').read_text())
    by={m['container']:m for m in metadata}; records={}
    unknown=collections.Counter(); counts=collections.Counter(); examples={}
    for m in metadata:
        records[m['container']]=dict(metadata=m,archive_files=0,flaky_files=0,conditions=collections.Counter(),candidate_files=[],summary_files=[],rounds_files=[],flaky_info=None)
    for line in (ROOT/'data/source/result_zip_index.jsonl').open():
        item=json.loads(line); path=item['path'];parts=path.split('/')
        if len(parts)<3: continue
        container=parts[1]
        if container not in by: unknown[container]+=1;continue
        rec=records[container];m=by[container];rec['archive_files']+=1
        if path==f'result/{container}/flaky_info.txt': rec['flaky_info']=item
        if len(parts)>4 and parts[2]=='result': rec['conditions'][parts[3]]+=1
        prefix=f'result/{container}/result/Flaky/'
        if not path.startswith(prefix): continue
        rec['flaky_files']+=1
        if m['label'] not in examples: examples[m['label']]=[]
        if len(examples[m['label']])<20: examples[m['label']].append(path)
        klass=m['configured_test'].split('#')[0]
        if path.endswith('/TEST-'+klass+'.xml') or path.endswith('/'+klass+'.txt') and '/surefire-reports/' in path or '/dtfixingtools/' in path and '/test-runs/results/' in path:
            rec['candidate_files'].append(item)
        elif path==prefix+'summary.txt': rec['summary_files'].append(item)
        elif path==prefix+'rounds-test-results.csv': rec['rounds_files'].append(item)
    for r in records.values():
        r['candidate_files'].sort(key=lambda x:natural(x['path']))
        counts[r['metadata']['label']]+=bool(r['candidate_files'])
    audit=dict(archive_complete=True,archive_files=summary['files'],metadata_containers=len(metadata),matched_containers=sum(r['archive_files']>0 for r in records.values()),containers_with_flaky_condition=sum(r['flaky_files']>0 for r in records.values()),containers_with_candidates=sum(bool(r['candidate_files']) for r in records.values()),candidate_containers_by_label=dict(counts),candidate_files=sum(len(r['candidate_files']) for r in records.values()),unknown_containers=dict(unknown),examples=examples,missing_containers=[c for c,r in records.items() if not r['archive_files']],no_candidate_containers=[c for c,r in records.items() if not r['candidate_files']])
    (ROOT/'data/audit/archive_candidates.json').write_text(json.dumps(records,separators=(',',':')),encoding='utf-8')
    (ROOT/'data/audit/archive_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit,indent=2))

if __name__=='__main__': main()
