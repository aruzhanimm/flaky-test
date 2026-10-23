"""Recalculate metrics without sklearn and audit saved splits/repeat predictions."""
import argparse,collections,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def f1(truth,pred,labels):
    scores=[]
    for label in labels:
        tp=sum(t==p==label for t,p in zip(truth,pred));fp=sum(t!=label and p==label for t,p in zip(truth,pred));fn=sum(t==label and p!=label for t,p in zip(truth,pred))
        scores.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    return sum(scores)/len(scores)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('--repeat');ap.add_argument('--write-checks',action='store_true',help='Write independent_checks.json; default is read-only');args=ap.parse_args()
    directory=ROOT/'results'/args.run;m=read(directory/'metrics.json');rows=[json.loads(x) for x in (directory/'predictions.jsonl').read_text().splitlines()];splits=read(directory/'splits.json');byid={r['sample_id']:r for r in rows}
    assert len(rows)==len(byid)==m['tests']
    assert len(splits)==m['project_groups']
    seen=[];deltas=[]
    for split in splits:
        train=split['train_sample_ids'];test=split['test_sample_ids'];seen+=test
        assert not set(train)&set(test)
        assert set(train)|set(test)==set(byid)
        assert {byid[x]['project_group'] for x in test}=={split['held_out_group']}
        assert split['held_out_group'] not in {byid[x]['project_group'] for x in train}
        assert {byid[x]['label'] for x in train}==set(m['labels'])
        truth=[byid[x]['label'] for x in test];labels=sorted(set(truth))
        delta=f1(truth,[byid[x]['predictions']['masked'] for x in test],labels)-f1(truth,[byid[x]['predictions']['original'] for x in test],labels);deltas.append(delta)
    assert sorted(seen)==sorted(byid)
    assert math.isclose(sum(deltas)/len(deltas),m['paired_delta_mean'],abs_tol=1e-12)
    for condition in ('original','masked','majority','source_format'):
        score=f1([r['label'] for r in rows],[r['predictions'][condition] for r in rows],m['labels'])
        assert math.isclose(score,m['metrics'][condition]['pooled_macro_f1'],abs_tol=1e-12)
    result=dict(run=args.run,tests=len(rows),project_groups=len(splits),metrics_recalculated_without_sklearn=True,all_saved_splits_disjoint=True,all_samples_evaluated_once=True)
    if args.repeat:
        other=ROOT/'results'/args.repeat
        assert (directory/'predictions.jsonl').read_bytes()==(other/'predictions.jsonl').read_bytes()
        fits1=read(directory/'fits.json');fits2=read(other/'fits.json')
        assert [(r['vocabulary_sha256'],r['coef_sha256']) for r in fits1]==[(r['vocabulary_sha256'],r['coef_sha256']) for r in fits2]
        result.update(repeat_run=args.repeat,predictions_byte_identical=True,vocabulary_and_coefficient_hashes_equal=True)
    if args.write_checks:(directory/'independent_checks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
if __name__=='__main__':main()
