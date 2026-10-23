"""Audit original metadata; do not infer log availability from metadata rows."""
import collections, csv, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'data/source'; OUT=ROOT/'data/audit'; OUT.mkdir(parents=True,exist_ok=True)
def read(name):
    with (SRC/name).open(encoding='utf-8-sig',newline='') as f:
        return [{k.strip():v.strip() for k,v in r.items() if k is not None} for r in csv.DictReader(f)]
config=read('test_config.csv')
meta=[]
for source in ['JIRA','iDoFT']:
    for r in read(f'Reproducible_{source}_info.csv'):
        meta.append(dict(source=source,container=r['Container Name'],project=r['Project (Github Link)'].removesuffix('.git').rstrip('/').lower(),revision=r['Flaky commit SHA'],test=r.get('Flaky Test Name',r.get('Flaky test name')),label=r['Type'].upper(),module=r['Module'],zip=r['Zip name']))
by_container=collections.defaultdict(list)
for m in meta: by_container[m['container']].append(m)
inventory=[]; issues=[]
for i,c in enumerate(config,2):
    candidates=by_container[c['result_container']]
    if len(candidates)!=1:
        issues.append(dict(config_row=i,container=c['result_container'],reason='metadata_match_count',count=len(candidates)))
        continue
    m=dict(candidates[0]); m['config_row']=i; m['configured_test']=c['flaky_test']; m['configured_type']=c['test_type']; m['iterations']=c['iterations']
    m['test_id']=m['project']+'::'+m['test']; m['variant_id']=m['test_id']+'::'+m['revision']+'::'+m['module']
    m['log_verified']=False
    if c['flaky_test'].replace('#','.')!=m['test']:
        issues.append(dict(config_row=i,container=m['container'],reason='test_name_mismatch',config=c['flaky_test'],metadata=m['test']))
    inventory.append(m)
def duplicates(rows,key):
    groups=collections.defaultdict(list)
    for r in rows: groups[r[key]].append(r['container'])
    return {k:v for k,v in groups.items() if len(v)>1}
coverage=collections.defaultdict(collections.Counter)
for m in meta: coverage[m['project']][m['label']]+=1
with (OUT/'metadata_project_category.csv').open('w',newline='',encoding='utf-8') as f:
    labels=sorted({m['label'] for m in meta}); w=csv.DictWriter(f,fieldnames=['project']+labels);w.writeheader()
    for p,counts in sorted(coverage.items()): w.writerow({'project':p,**counts})
summary=dict(config_rows=len(config),metadata_rows=len(meta),metadata_by_source=dict(collections.Counter(m['source'] for m in meta)),metadata_categories=dict(collections.Counter(m['label'] for m in meta)),config_types=dict(collections.Counter(c['test_type'] for c in config)),mapped_config_rows=len(inventory),unique_repository_urls=len(coverage),unique_test_ids=len({m['test_id'] for m in inventory}),unique_variants=len({m['variant_id'] for m in inventory}),category_repository_counts={l:sum(counts[l]>0 for counts in coverage.values()) for l in labels},duplicate_test_ids=duplicates(inventory,'test_id'),duplicate_variant_ids=duplicates(inventory,'variant_id'),issues=issues,eligibility_status='Metadata only. No logs verified and no independent-fork audit yet.')
(OUT/'metadata_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(OUT/'metadata_inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['duplicate_test_ids','duplicate_variant_ids','issues']},indent=2)); print('Issues:',len(issues));print(json.dumps(issues[:12],indent=2));print('Duplicate tests:',len(summary['duplicate_test_ids']))
