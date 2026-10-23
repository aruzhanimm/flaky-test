"""Project-disjoint paired baseline evaluation; all tables derive from predictions."""
import argparse, collections, datetime, hashlib, json, platform, time, warnings
from pathlib import Path
import numpy as np
import scipy, sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import f1_score, classification_report, confusion_matrix, accuracy_score
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--corpus',default='data/processed/corpus.jsonl');ap.add_argument('--name',required=True);ap.add_argument('--three-label',action='store_true');ap.add_argument('--pilot',action='store_true');ap.add_argument('--protocol',default='protocol_v3_RU.txt');ap.add_argument('--config',default='config_model_v3.json');args=ap.parse_args()
    config_path=(ROOT/args.config).resolve()
    if not config_path.is_relative_to(ROOT):raise ValueError('Config must be inside project')
    config=json.loads(config_path.read_text())
    path=(ROOT/args.corpus).resolve()
    protocol=(ROOT/args.protocol).resolve()
    if not protocol.is_relative_to(ROOT):raise ValueError('Protocol must be inside project')
    if not path.is_relative_to(ROOT):raise ValueError('Corpus must be inside project')
    if not args.pilot:
        audit=json.loads((ROOT/'data/processed/audit.json').read_text())
        if not audit['extraction_complete']:raise ValueError('Full extraction not complete')
        if audit['corpus_sha256']!=sha(path):raise ValueError('Corpus audit hash mismatch')
    labels=config['sensitivity_labels'] if args.three_label else config['primary_labels']
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    rows=[r for r in rows if r['label'] in labels]; rows.sort(key=lambda r:r['sample_id'])
    y=np.array([r['label'] for r in rows]);groups=np.array([r['project_group'] for r in rows]);ids=[r['sample_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate sample ID')
    if len({r['canonical_test_id'] for r in rows})!=len(rows):raise ValueError('Duplicate canonical test')
    coverage={label:len(set(groups[y==label])) for label in labels}
    if any(n<config['minimum_project_groups_per_class'] for n in coverage.values()):raise ValueError(f'Insufficient coverage: {coverage}')
    dest=(ROOT/'results'/args.name).resolve()
    if not dest.is_relative_to((ROOT/'results').resolve()):raise ValueError('Run must be inside results/')
    if dest.exists():raise ValueError('Use a new run name; do not overwrite previous experiment')
    dest.mkdir(parents=True)
    start=time.perf_counter();prediction_rows=[];fold_scores=[];splits=[];fit_info=[]
    settings=dict(config['vectorizer']);settings['ngram_range']=tuple(settings['ngram_range'])
    with threadpool_limits(limits=1),warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        for fold,(train,test) in enumerate(LeaveOneGroupOut().split(np.zeros(len(rows)),y,groups)):
            train_groups=set(groups[train]);test_groups=set(groups[test])
            assert train_groups.isdisjoint(test_groups) and len(test_groups)==1
            assert set(y[train])==set(labels)
            test_labels=sorted(set(y[test]));group=groups[test[0]]
            split=dict(fold=fold,held_out_group=group,held_out_repository=rows[test[0]]['canonical_repository'],train_sample_ids=[ids[i] for i in train],test_sample_ids=[ids[i] for i in test],training_labels=dict(collections.Counter(y[train])),test_labels=dict(collections.Counter(y[test])))
            splits.append(split);predictions={}
            for condition,key in [('original','original_text'),('masked','masked_text')]:
                pipeline=Pipeline([('tfidf',TfidfVectorizer(**settings)),('model',LogisticRegression(**config['classifier']))])
                fit_start=time.perf_counter()
                pipeline.fit([rows[i][key] for i in train],y[train])
                pred=pipeline.predict([rows[i][key] for i in test]);predictions[condition]=pred
                vectorizer=pipeline.named_steps['tfidf'];model=pipeline.named_steps['model']
                fit_info.append(dict(fold=fold,condition=condition,training_documents=len(train),evaluation_documents=len(test),vocabulary_size=len(vectorizer.vocabulary_),vocabulary_sha256=hashlib.sha256(json.dumps({k:int(v) for k,v in vectorizer.vocabulary_.items()},sort_keys=True).encode()).hexdigest(),coef_sha256=hashlib.sha256(model.coef_.tobytes()).hexdigest(),iterations=model.n_iter_.tolist(),seconds=time.perf_counter()-fit_start))
            majority=sorted(collections.Counter(y[train]).items(),key=lambda x:(-x[1],x[0]))[0][0]
            predictions['majority']=np.repeat(majority,len(test))
            format_labels=collections.defaultdict(collections.Counter)
            for i in train:format_labels[rows[i]['format']][y[i]]+=1
            decisions={fmt:sorted(counts.items(),key=lambda x:(-x[1],x[0]))[0][0] for fmt,counts in format_labels.items()}
            predictions['source_format']=np.array([decisions.get(rows[i]['format'],majority) for i in test])
            scores={c:float(f1_score(y[test],p,labels=test_labels,average='macro',zero_division=0)) for c,p in predictions.items()}
            fold_scores.append(dict(fold=fold,project_group=group,repository=rows[test[0]]['canonical_repository'],support=len(test),supported_labels=test_labels,scores=scores,delta=scores['masked']-scores['original']))
            for local,i in enumerate(test):
                r=rows[i]
                prediction_rows.append(dict(sample_id=r['sample_id'],canonical_test_id=r['canonical_test_id'],project_group=r['project_group'],repository=r['canonical_repository'],container=r['container'],label=r['label'],fold=fold,original_sha256=r['original_sha256'],masked_sha256=r['masked_sha256'],predictions={c:str(p[local]) for c,p in predictions.items()}))
            if fold%10==0:print(f'Completed fold {fold+1}; held out {rows[test[0]]["canonical_repository"]}; tests {len(test)}',flush=True)
    prediction_rows.sort(key=lambda r:r['sample_id'])
    predfile=dest/'predictions.jsonl';predfile.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in prediction_rows),encoding='utf-8')
    truth=[r['label'] for r in prediction_rows];metrics={}
    for condition in ('original','masked','majority','source_format'):
        pred=[r['predictions'][condition] for r in prediction_rows]
        metrics[condition]=dict(pooled_macro_f1=float(f1_score(truth,pred,labels=labels,average='macro',zero_division=0)),accuracy=float(accuracy_score(truth,pred)),mean_project_macro_f1=float(np.mean([r['scores'][condition] for r in fold_scores])),classification_report=classification_report(truth,pred,labels=labels,output_dict=True,zero_division=0),confusion_matrix=confusion_matrix(truth,pred,labels=labels).tolist())
    delta=np.array([r['delta'] for r in fold_scores]);rng=np.random.default_rng(config['seed'])
    boot=rng.choice(delta,size=(config['bootstrap_resamples'],len(delta)),replace=True).mean(axis=1)
    changed=[r for r in prediction_rows if r['predictions']['original']!=r['predictions']['masked']]
    improvements=sum(r['predictions']['original']!=r['label'] and r['predictions']['masked']==r['label'] for r in changed)
    harms=sum(r['predictions']['original']==r['label'] and r['predictions']['masked']!=r['label'] for r in changed)
    checks=dict(project_disjoint=True,each_test_evaluated_once=len(prediction_rows)==len(rows)==len({r['sample_id'] for r in prediction_rows}),paired_sample_ids_equal=True,all_training_folds_contain_all_labels=True,fresh_pipeline_per_fold_condition=True,tfidf_fit_on_training_only=True,convergence_warnings=0)
    # Checks above correspond to enforced assertions and the explicit fitting path,
    # not a claim that any implementation can be certified by booleans alone.
    summary=dict(run=args.name,pilot=args.pilot,labels=labels,tests=len(rows),project_groups=len(fold_scores),category_project_groups=coverage,metrics=metrics,paired_delta_mean=float(delta.mean()),paired_delta_median=float(np.median(delta)),conditional_project_bootstrap_95=[float(v) for v in np.quantile(boot,[.025,.975])],bootstrap_caution='Descriptive conditional interval; overlapping training folds and limited rare-category projects restrict inference. No p-value or causal conclusion.',pooled_macro_f1_delta=metrics['masked']['pooled_macro_f1']-metrics['original']['pooled_macro_f1'],changed_predictions=len(changed),changed_wrong_to_right=improvements,changed_right_to_wrong=harms,changed_wrong_to_different_wrong=len(changed)-improvements-harms,seconds=time.perf_counter()-start,corpus_sha256=sha(path),predictions_sha256=sha(predfile),config_sha256=sha(config_path),config_path=str(config_path.relative_to(ROOT)),protocol_sha256=sha(protocol),protocol_path=str(protocol.relative_to(ROOT)),code_sha256={p.name:sha(p) for p in (ROOT/'scripts').glob('*.py')},environment=dict(python=platform.python_version(),platform=platform.platform(),sklearn=sklearn.__version__,numpy=np.__version__,scipy=scipy.__version__),completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks)
    dump(dest/'metrics.json',summary);dump(dest/'project_scores.json',fold_scores);dump(dest/'splits.json',splits);dump(dest/'fits.json',fit_info);dump(dest/'changed_predictions.json',changed);dump(dest/'config.json',config)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('metrics','code_sha256')},indent=2),flush=True)

if __name__=='__main__':main()
