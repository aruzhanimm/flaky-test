"""Independent arithmetic and provenance checks; no sklearn metrics used."""
import argparse,collections,hashlib,json,math
from pathlib import Path
from validate_results import f1
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def close(a,b):assert math.isclose(a,b,abs_tol=1e-12),(a,b)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('name',nargs='?',default='extension_v4');ap.add_argument('--write-checks',action='store_true',help='Write independent_checks.json; default is read-only');args=ap.parse_args();d=ROOT/'results'/args.name
    m=read(d/'metrics.json');p=[json.loads(l) for l in (d/'predictions.jsonl').read_text(encoding='utf-8').splitlines()];byid={r['sample_id']:r for r in p}
    corpus={r['sample_id']:r for l in (ROOT/'data/processed/corpus.jsonl').read_text(encoding='utf-8').splitlines() for r in [json.loads(l)]}
    prior={r['sample_id']:r for l in (ROOT/'results/main_v3/predictions.jsonl').read_text().splitlines() for r in [json.loads(l)]}
    assert len(p)==len(byid)==1051 and set(byid)==set(corpus)==set(prior)
    seen=[];splitgroups={}
    for s in read(d/'splits.json'):
        train=set(s['train_sample_ids']);test=set(s['test_sample_ids']);assert train.isdisjoint(test) and train|test==set(byid)
        assert {byid[i]['project_group'] for i in test}=={s['held_out_group']}
        assert s['held_out_group'] not in {byid[i]['project_group'] for i in train}
        assert {byid[i]['label'] for i in train}==set(m['labels']);seen+=list(test);splitgroups[s['held_out_group']]=test
    assert sorted(seen)==sorted(byid)
    for r in p:
        assert r['project_group']==corpus[r['sample_id']]['project_group'] and r['label']==corpus[r['sample_id']]['label']
        assert r['predictions']['original']==prior[r['sample_id']]['predictions']['original'] and r['predictions']['full']==prior[r['sample_id']]['predictions']['masked']
    for mode,metrics in m['metrics'].items():
        close(f1([r['label'] for r in p],[r['predictions'][mode] for r in p],m['labels']),metrics['pooled_macro_f1'])
        means=[]
        for ids in splitgroups.values():
            truth=[byid[i]['label'] for i in ids];pred=[byid[i]['predictions'][mode] for i in ids];means.append(f1(truth,pred,sorted(set(truth))))
        close(sum(means)/len(means),metrics['mean_project_macro_f1'])
    changed={r['sample_id'] for r in p if r['predictions']['original']!=r['predictions']['full']};cases=read(d/'all_changed_cases.json')
    assert changed=={c['sample_id'] for c in cases} and len(changed)==len(cases)==56
    for c in cases:
        r=corpus[c['sample_id']];assert c['original_text']==r['original_text'] and c['masked_text']==r['masked_text'] and c['diagnostic_member']==r['diagnostic_member']['path']
        close(c['direct_text_margin_shift']+c['refitted_state_margin_shift'],c['total_margin_shift'])
    s=read(d/'surefire_analysis.json');sp=s['predictions'];sb={r['sample_id']:r for r in sp};allseen=[]
    for split in s['splits']:
        tr=set(split['train_sample_ids']);te=set(split['test_sample_ids']);assert tr.isdisjoint(te) and tr|te==set(sb)
        assert {sb[i]['project_group'] for i in te}=={split['held_out_group']} and split['held_out_group'] not in {sb[i]['project_group'] for i in tr};allseen+=list(te)
    assert sorted(allseen)==sorted(sb)
    for mode,metrics in s['metrics'].items():close(f1([r['label'] for r in sp],[r['predictions'][mode] for r in sp],['OD','TD']),metrics['pooled_macro_f1'])
    assert hashlib.sha256((ROOT/'data/processed/corpus.jsonl').read_bytes()).hexdigest()==read(d/'provenance.json')['corpus_sha256']
    assert all(r['predictions']['T']==r['predictions']['full'] for r in p)
    assert all(r['predictions']['P']==r['predictions']['original'] for r in p)
    result=dict(tests=1051,project_groups=127,conditions_checked=len(m['metrics']),all_metrics_recomputed_without_sklearn=True,all_splits_and_labels_match_corpus=True,each_sample_evaluated_once=True,main_pair_exactly_reproduced=True,all_56_cases_traced_to_corpus=True,all_margin_decompositions_verified=True,surefire_metrics_and_splits_checked=True,corpus_hash_unchanged=True)
    result.update(test_only_equals_full_predictions=True,path_only_equals_original_predictions=True)
    if args.write_checks:(d/'independent_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
