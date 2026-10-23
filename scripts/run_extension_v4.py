"""Run the complete disclosed post-review analysis, never overwrite a run."""
import argparse,collections,datetime,hashlib,json,platform,time,warnings
from pathlib import Path
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import f1_score,classification_report,confusion_matrix
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
from mask_components import transform,MODES

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def python_scalar(x):
    if isinstance(x,np.generic):return x.item()
    raise TypeError(f'Unsupported JSON value: {type(x).__name__}')
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=python_scalar),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(x.encode()).hexdigest()

def pipeline(config,svc=False):
    settings=dict(config['vectorizer']);settings['ngram_range']=tuple(settings['ngram_range'])
    model=LinearSVC(C=1,class_weight='balanced',dual='auto',loss='squared_hinge',max_iter=10000,tol=0.0001,random_state=config['seed']) if svc else LogisticRegression(**config['classifier'])
    return Pipeline([('tfidf',TfidfVectorizer(**settings)),('model',model)])

def fit_record(pipe,fold,condition):
    v=pipe.named_steps['tfidf'];m=pipe.named_steps['model']
    return dict(fold=fold,condition=condition,vocabulary_size=len(v.vocabulary_),vocabulary_sha256=digest(json.dumps({k:int(v) for k,v in v.vocabulary_.items()},sort_keys=True)),coef_sha256=hashlib.sha256(m.coef_.tobytes()).hexdigest())

def contribution(pipe,text,old,new):
    v=pipe.named_steps['tfidf'];m=pipe.named_steps['model'];x=v.transform([text]);names=v.get_feature_names_out();classes=list(m.classes_)
    coef=m.coef_[classes.index(new)]-m.coef_[classes.index(old)]
    effects=x.data*coef[x.indices];rank=np.argsort(-np.abs(effects),kind='stable')[:10]
    scores=m.decision_function(x)[0];margin=float(scores[classes.index(new)]-scores[classes.index(old)])
    return dict(margin=margin,intercept=float(m.intercept_[classes.index(new)]-m.intercept_[classes.index(old)]),top_terms=[dict(token=str(names[x.indices[k]]),contribution=float(effects[k])) for k in rank],feature_count=x.nnz)

def summarize(rows,conditions,labels,project_rows):
    truth=[r['label'] for r in rows];out={}
    for c in conditions:
        pred=[r['predictions'][c] for r in rows]
        out[c]=dict(pooled_macro_f1=float(f1_score(truth,pred,labels=labels,average='macro',zero_division=0)),mean_project_macro_f1=float(np.mean([g['scores'][c] for g in project_rows])),classification_report=classification_report(truth,pred,labels=labels,output_dict=True,zero_division=0),confusion_matrix=confusion_matrix(truth,pred,labels=labels).tolist())
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='extension_v4');ap.add_argument('--strict-reference-hashes',action='store_true');args=ap.parse_args();dest=(ROOT/'results'/args.name).resolve()
    if not dest.is_relative_to((ROOT/'results').resolve()):raise ValueError('Run must be inside results/')
    if dest.exists():raise ValueError('Choose a new run name; previous results will not be overwritten')
    config=read(ROOT/'config_model_v3.json');labels=config['primary_labels'];rows=sorted([json.loads(x) for x in (ROOT/'data/processed/corpus.jsonl').read_text(encoding='utf-8').splitlines()],key=lambda r:r['sample_id'])
    metadata={r['container']:r for r in read(ROOT/'data/audit/metadata_inventory.json')}
    old={r['sample_id']:r for r in [json.loads(x) for x in (ROOT/'results/main_v3/predictions.jsonl').read_text().splitlines()]}
    oldfits={(r['fold'],r['condition']):r for r in read(ROOT/'results/main_v3/fits.json')}
    y=np.array([r['label'] for r in rows]);groups=np.array([r['project_group'] for r in rows]);texts={m:[] for m in MODES};differences={}
    for r in rows:
        for mode in MODES:texts[mode].append(transform(r['original_text'],metadata[r['container']],r['canonical_repository'],r['exception_type'],mode))
        assert texts['original'][-1]==r['original_text'] and texts['full'][-1]==r['masked_text']
    for mode in MODES:differences[mode]=sum(a!=b for a,b in zip(texts[mode],texts['original']))
    dest.mkdir(parents=True);(dest/'folds').mkdir()
    shutil_files=['run_extension_v4.py','mask_components.py','representations.py']
    provenance=dict(protocol_sha256=sha(ROOT/'protocol_extension_v4_RU.txt'),corpus_sha256=sha(ROOT/'data/processed/corpus.jsonl'),config_sha256=sha(ROOT/'config_model_v3.json'),code={f:sha(ROOT/'scripts'/f) for f in shutil_files},python=platform.python_version(),sklearn=sklearn.__version__,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),post_hoc=True)
    dump(dest/'provenance.json',provenance)
    dump(dest/'config.json',dict(original_config=config,svc=dict(C=1,class_weight='balanced',dual='auto',loss='squared_hinge',max_iter=10000,tol=.0001,random_state=config['seed']),modes=MODES))
    conditions=list(MODES)+['svc_original','svc_full','original_model_masked_text','masked_model_original_text']
    predrows=[];projects=[];fits=[];splits=[];cases=[];svc_repeat_ok=True;reference_coefficients_equal=True;source_counts=collections.defaultdict(collections.Counter)
    for r in rows:source_counts[r['format']][r['label']]+=1
    start=time.perf_counter()
    with threadpool_limits(limits=1),warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        for fold,(train,test) in enumerate(LeaveOneGroupOut().split(np.zeros(len(rows)),y,groups)):
            pred_start=len(predrows);case_start=len(cases)
            assert set(groups[train]).isdisjoint(set(groups[test])) and set(y[train])==set(labels)
            splits.append(dict(fold=fold,held_out_group=groups[test[0]],train_sample_ids=[rows[i]['sample_id'] for i in train],test_sample_ids=[rows[i]['sample_id'] for i in test]))
            preds={};retained={}
            for mode in MODES:
                pipe=pipeline(config);pipe.fit([texts[mode][i] for i in train],y[train]);preds[mode]=pipe.predict([texts[mode][i] for i in test]);info=fit_record(pipe,fold,mode);fits.append(info)
                if mode in ('original','full'):
                    prior=oldfits[(fold,'original' if mode=='original' else 'masked')]
                    assert info['vocabulary_sha256']==prior['vocabulary_sha256']
                    coefficient_equal=info['coef_sha256']==prior['coef_sha256']
                    reference_coefficients_equal=reference_coefficients_equal and coefficient_equal
                    if args.strict_reference_hashes:assert coefficient_equal, 'Reference coefficient bytes differ'
                    assert preds[mode].tolist()==[old[rows[i]['sample_id']]['predictions']['original' if mode=='original' else 'masked'] for i in test]
                    retained[mode]=pipe
            for mode in ('original','full'):
                key='svc_'+mode
                pipe=pipeline(config,True);pipe.fit([texts[mode][i] for i in train],y[train]);preds[key]=pipe.predict([texts[mode][i] for i in test]);info=fit_record(pipe,fold,key);fits.append(info)
                repeat=pipeline(config,True);repeat.fit([texts[mode][i] for i in train],y[train]);again=repeat.predict([texts[mode][i] for i in test]);rf=fit_record(repeat,fold,key)
                assert np.array_equal(preds[key],again) and info==rf
            preds['original_model_masked_text']=retained['original'].predict([texts['full'][i] for i in test])
            preds['masked_model_original_text']=retained['full'].predict([texts['original'][i] for i in test])
            supported=sorted(set(y[test]));scores={k:float(f1_score(y[test],p,labels=supported,average='macro',zero_division=0)) for k,p in preds.items()}
            project=dict(fold=fold,project_group=str(groups[test[0]]),repository=rows[test[0]]['canonical_repository'],support=len(test),category_counts=dict(collections.Counter(y[test])),scores=scores,full_delta=scores['full']-scores['original'],changed=sum(preds['full']!=preds['original']))
            projects.append(project)
            for j,i in enumerate(test):
                r=rows[i];p=dict(sample_id=r['sample_id'],project_group=r['project_group'],repository=r['canonical_repository'],label=r['label'],format=r['format'],fold=fold,predictions={k:str(v[j]) for k,v in preds.items()});predrows.append(p)
                if preds['original'][j]!=preds['full'][j]:
                    before=str(preds['original'][j]);after=str(preds['full'][j]);a=contribution(retained['original'],texts['original'][i],before,after);b=contribution(retained['original'],texts['full'][i],before,after);c=contribution(retained['full'],texts['full'][i],before,after)
                    direct=b['margin']-a['margin'];refit=c['margin']-b['margin'];total=c['margin']-a['margin'];assert abs(direct+refit-total)<1e-12
                    cases.append(dict(**p,container=r['container'],configured_test=r['configured_test'],project_support=len(test),source=r['source'],original_chars=len(texts['original'][i]),masked_chars=len(texts['full'][i]),diagnostic_member=r['diagnostic_member']['path'],original_text=texts['original'][i],masked_text=texts['full'][i],contrast=f'{after} minus {before}',original=a,original_model_masked_text=b,masked=c,direct_text_margin_shift=direct,refitted_state_margin_shift=refit,total_margin_shift=total,original_vocabulary_size=len(retained['original'].named_steps['tfidf'].vocabulary_),masked_vocabulary_size=len(retained['full'].named_steps['tfidf'].vocabulary_)))
            dump(dest/'folds'/f'{fold:03d}.json',dict(project=project,split=splits[-1],predictions=predrows[pred_start:],cases=cases[case_start:],fits=[f for f in fits if f['fold']==fold],svc_repeat_hashes_and_predictions_equal=True))
            if fold%10==0:print(f'Extension fold {fold+1}/127 complete and saved; {time.perf_counter()-start:.1f}s',flush=True)
    predrows.sort(key=lambda r:r['sample_id']);cases.sort(key=lambda r:r['sample_id'])
    metrics=summarize(predrows,conditions,labels,projects)
    for mode in MODES:
        metrics[mode]['delta_vs_original']=metrics[mode]['pooled_macro_f1']-metrics['original']['pooled_macro_f1']
        metrics[mode]['changed']=sum(r['predictions'][mode]!=r['predictions']['original'] for r in predrows)
        metrics[mode]['improved']=sum(r['predictions'][mode]==r['label'] and r['predictions']['original']!=r['label'] for r in predrows)
        metrics[mode]['harmed']=sum(r['predictions'][mode]!=r['label'] and r['predictions']['original']==r['label'] for r in predrows)
    assert len(cases)==56 and sum(g['changed']>0 for g in projects)==10
    summary=dict(tests=len(rows),groups=len(projects),labels=labels,metrics=metrics,mask_changed_texts=differences,format_by_category={k:dict(v) for k,v in source_counts.items()},all_main_predictions_and_vocab_reproduced=True,all_main_predictions_vocab_coefficients_reproduced=reference_coefficients_equal,svc_repeat_predictions_vocab_coefficients_identical=svc_repeat_ok,changed_cases=len(cases),affected_projects=[g for g in projects if g['changed']],case_counts=dict(original_model_masked_text_keeps_original=sum(c['predictions']['original_model_masked_text']==c['predictions']['original'] for c in cases),masked_model_original_text_already_has_final_error=sum(c['predictions']['masked_model_original_text']==c['predictions']['full'] for c in cases),direct_shift_toward_error=sum(c['direct_text_margin_shift']>1e-12 for c in cases),refit_shift_toward_error=sum(c['refitted_state_margin_shift']>1e-12 for c in cases)),seconds=time.perf_counter()-start)
    dump(dest/'metrics.json',summary);dump(dest/'project_scores.json',projects);dump(dest/'fits.json',fits);dump(dest/'splits.json',splits);dump(dest/'all_changed_cases.json',cases)
    (dest/'predictions.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in predrows),encoding='utf-8')
    subset=[i for i,r in enumerate(rows) if r['format'].startswith('surefire_') and r['label'] in ('OD','TD')]
    coverage={lab:len({rows[i]['project_group'] for i in subset if rows[i]['label']==lab}) for lab in ('OD','TD')}
    if all(v>=3 for v in coverage.values()):
        subrows=[];subprojects=[];subsplits=[];sy=y[subset];sg=groups[subset]
        with threadpool_limits(limits=1),warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            for fold,(tr,te) in enumerate(LeaveOneGroupOut().split(np.zeros(len(subset)),sy,sg)):
                train=[subset[j] for j in tr];test=[subset[j] for j in te];assert set(y[train])=={'OD','TD'};pred={}
                for mode in ('original','full'):
                    pipe=pipeline(config);pipe.fit([texts[mode][i] for i in train],y[train]);pred[mode]=pipe.predict([texts[mode][i] for i in test])
                majority=collections.Counter(y[train]).most_common(1)[0][0];pred['majority']=np.repeat(majority,len(test))
                byformat=collections.defaultdict(collections.Counter)
                for i in train:byformat[rows[i]['format']][rows[i]['label']]+=1
                decisions={k:v.most_common(1)[0][0] for k,v in byformat.items()};pred['format']=np.array([decisions.get(rows[i]['format'],majority) for i in test])
                subprojects.append(dict(project_group=str(groups[test[0]]),repository=rows[test[0]]['canonical_repository'],support=len(test),scores={k:float(f1_score(y[test],v,labels=sorted(set(y[test])),average='macro',zero_division=0)) for k,v in pred.items()}))
                subsplits.append(dict(train_sample_ids=[rows[i]['sample_id'] for i in train],test_sample_ids=[rows[i]['sample_id'] for i in test],held_out_group=str(groups[test[0]])))
                for j,i in enumerate(test):subrows.append(dict(sample_id=rows[i]['sample_id'],project_group=rows[i]['project_group'],label=rows[i]['label'],predictions={k:str(v[j]) for k,v in pred.items()}))
        subrows.sort(key=lambda r:r['sample_id']);sm=summarize(subrows,['original','full','majority','format'],['OD','TD'],subprojects)
        dump(dest/'surefire_analysis.json',dict(tests=len(subset),groups=len(subprojects),category_groups=coverage,metrics=sm,projects=subprojects,splits=subsplits,predictions=subrows,caution='Same collector family, mixed XML/TXT; restricted OD/TD task, not a controlled four-category corpus'))
    else:dump(dest/'surefire_analysis.json',dict(status='insufficient category coverage',coverage=coverage))
    provenance['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(dest/'provenance.json',provenance)
    print(json.dumps({k:summary[k] for k in ('tests','groups','mask_changed_texts','case_counts','seconds')},indent=2),flush=True)
    print('All extension runs completed',flush=True)

if __name__=='__main__':main()
