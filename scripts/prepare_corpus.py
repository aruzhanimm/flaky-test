"""Deterministic eligibility, canonical grouping and paired representations."""
import argparse, collections, hashlib, json, re
from pathlib import Path
from representations import clean,mask,source_format
ROOT=Path(__file__).resolve().parents[1]

def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--allow-partial',action='store_true');a=ap.parse_args()
    metadata=json.loads((ROOT/'data/audit/metadata_inventory.json').read_text())
    identities={r['source_url']:r for r in json.loads((ROOT/'data/audit/repository_identities.json').read_text())}
    results={}
    for path in (ROOT/'data/first_failures').glob('*.json'):
        r=json.loads(path.read_text());results[r['container']]=r
    terminal={'confirmed_failure','no_failure_in_outcome_table','no_confirmed_target_diagnostic','unclassified'}
    pending=sum(r['status'] not in terminal for r in results.values())
    complete=len(results)==len(metadata) and pending==0
    if not complete and not a.allow_partial:raise ValueError(f'Extraction incomplete: {len(results)}/{len(metadata)} records, {pending} unresolved/deferred/parser cases. No final corpus produced.')
    exclusions=[];candidates=[]
    for m in metadata:
        r=results.get(m['container']);reason=None
        identity=identities.get(m['project'],{})
        if r is None:reason='not_processed'
        elif r['status']!='confirmed_failure':reason=r['status']
        elif identity.get('status')!='verified':reason='repository_identity_unresolved'
        elif not re.fullmatch(r'[0-9a-fA-F]{40}',m['revision']):reason='missing_or_invalid_revision'
        elif m['container']=='CURATOR-671':reason='revision_attribution_unresolved'
        elif m['label']=='UNCLASSIFIED':reason='unclassified'
        if reason:
            exclusions.append(dict(container=m['container'],label=m['label'],project=m['project'],reason=reason));continue
        canonical=identity['repository_network_root_id']+'::'+m['test']
        original=clean(r['failure']['text'])
        if not original:
            exclusions.append(dict(container=m['container'],label=m['label'],project=m['project'],reason='empty_after_common_cleanup'));continue
        canonical_repo='https://github.com/'+identity['repository_network_root_nwo'].lower()
        transformed=mask(original,m,canonical_repo,r['failure']['exception_type'])
        candidates.append(dict(sample_id=sha(canonical)[:24],canonical_test_id=canonical,project_group=identity['repository_network_root_id'],canonical_repository=canonical_repo,container=m['container'],source=m['source'],revision=m['revision'],configured_test=m['configured_test'],label=m['label'],original_text=original,masked_text=transformed,original_sha256=sha(original),masked_sha256=sha(transformed),diagnostic_member=r['diagnostic_member'],iteration=r['iteration'],source_row=r['source_row'],format=source_format(r['diagnostic_member']['path']),exception_type=r['failure']['exception_type'],review_flags=r['failure']['review_flags']))
    unique={}
    for r in sorted(candidates,key=lambda r:(0 if r['source']=='iDoFT' else 1,r['container'])):
        key=r['canonical_test_id']
        if key in unique:
            if unique[key]['label']!=r['label']:raise ValueError('Conflicting duplicate test labels')
            exclusions.append(dict(container=r['container'],label=r['label'],project=r['canonical_repository'],reason='duplicate_canonical_test',retained_container=unique[key]['container']))
        else:unique[key]=r
    corpus=[];hashes={};exact=[]
    for r in sorted(unique.values(),key=lambda r:r['canonical_test_id']):
        h=r['original_sha256'];prior=hashes.get(h)
        if prior and prior['project_group']!=r['project_group']:
            exclusions.append(dict(container=r['container'],label=r['label'],project=r['canonical_repository'],reason='exact_cross_project_duplicate',retained_container=prior['container']));exact.append([prior['canonical_test_id'],r['canonical_test_id']]);continue
        hashes.setdefault(h,r);corpus.append(r)
    coverage=collections.defaultdict(collections.Counter)
    formats=collections.defaultdict(collections.Counter);fingerprints=collections.defaultdict(list)
    for r in corpus:
        coverage[r['canonical_repository']][r['label']]+=1;formats[r['format']][r['label']]+=1
        normalized=re.sub(r'\d+','NUM',re.sub(r'\s+',' ',r['masked_text']))
        fingerprints[sha(normalized)].append(r)
    near=[dict(sample_ids=[r['sample_id'] for r in rows],projects=sorted({r['canonical_repository'] for r in rows}),labels=sorted({r['label'] for r in rows})) for rows in fingerprints.values() if len(rows)>1]
    out=ROOT/'data/processed';out.mkdir(parents=True,exist_ok=True)
    suffix='_preview' if a.allow_partial else ''
    file=out/('corpus'+suffix+'.jsonl');file.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in corpus),encoding='utf-8')
    summary=dict(extraction_complete=complete,metadata_containers=len(metadata),processed_containers=len(results),confirmed_failure_containers=sum(r['status']=='confirmed_failure' for r in results.values()),eligible_tests=len(corpus),eligible_project_groups=len(coverage),categories=dict(collections.Counter(r['label'] for r in corpus)),category_project_groups={label:sum(counts[label]>0 for counts in coverage.values()) for label in sorted({r['label'] for r in corpus})},coverage={p:dict(c) for p,c in coverage.items()},format_by_category={p:dict(c) for p,c in formats.items()},exclusions=dict(collections.Counter(r['reason'] for r in exclusions)),mask_changed=sum(r['original_text']!=r['masked_text'] for r in corpus),corpus_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),original_exact_cross_project_duplicates=len(exact),normalized_template_duplicate_groups=len(near),normalized_template_cross_project_groups=sum(len(g['projects'])>1 for g in near),near_duplicate_caution='Normalized masked/numeric fingerprints flag template similarity, not proof of shared code or statistical independence')
    (out/('audit'+suffix+'.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (out/('exclusions'+suffix+'.json')).write_text(json.dumps(exclusions,indent=2),encoding='utf-8')
    (out/('duplicates'+suffix+'.json')).write_text(json.dumps(dict(exact_cross_project=exact,normalized_templates=near),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('coverage','format_by_category')},indent=2))

if __name__=='__main__':main()
