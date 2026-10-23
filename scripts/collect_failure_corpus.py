"""Obtain first confirmed target failure per container, with a resumable ledger.

One network collector only. Natural iteration order, never model-score selection.
This is extraction; eligibility, deduplication and modelling remain separate.
"""
import concurrent.futures, hashlib, json, re, time
from remote_zip import ROOT, FILE, HTTPRangeFile, RateLimited
from collect_run_tables import download_items
from audit_outcome_tables import parse_table
from parse_failure import parse, digest

def main():
    entries=json.loads((ROOT/'data/audit/archive_candidates.json').read_text())
    tables=ROOT/'data/run_tables';tables.mkdir(parents=True,exist_ok=True)
    out=ROOT/'data/first_failures';out.mkdir(parents=True,exist_ok=True)
    def collect(pair):
        c,entry=pair; meta=entry['metadata'];key=hashlib.sha256(c.encode()).hexdigest()[:24]
        dest=out/(key+'.json'); table_path=tables/(key+'.json')
        record=dict(container=c,metadata=meta,selection='earliest available confirmed target failure by recorded iteration',attempts=[],status='unresolved')
        if dest.exists():
            prior=json.loads(dest.read_text())
            if prior['status']=='confirmed_failure':return prior
        try:
            table=json.loads(table_path.read_text()) if table_path.exists() else None
            if not table or table['status']!='verified':
                table=dict(container=c,metadata=meta,members=download_items(entry['summary_files']+entry['rounds_files']),status='verified')
                table_path.write_text(json.dumps(table,indent=2),encoding='utf-8')
            members=[m for m in table['members'] if m['path'].endswith('rounds-test-results.csv')]
            if len(members)!=1: raise ValueError('Expected exactly one outcome table')
            table_member=members[0]
            outcomes,issues=parse_table((ROOT/table_member['local_path']).read_text(encoding='utf-8-sig'),meta)
            record.update(outcome_rows=len(outcomes),table_issues=issues,table_member=table_member)
            failing=sorted([r for r in outcomes if r['status'] in ('failure','fail','error')],key=lambda x:(x['iteration'],x['row']))
            record['reported_failure_rows']=len(failing)
            if meta['label']=='UNCLASSIFIED':record['status']='unclassified'
            elif not failing:record['status']='no_failure_in_outcome_table'
            else:
                for row in failing:
                    if 'embedded_nio' in row:
                        data=json.dumps(row['embedded_nio']).encode();source=table_member
                        result=parse(data,'/test-runs/results/embedded',meta['configured_test'])
                    else:
                        if 'execution_id' in row:
                            suffix='/.nondex/'+row['execution_id']+'/'+row['xml_path'].split('/')[-1]
                            choices=[i for i in entry['candidate_files'] if i['path'].endswith(suffix)]
                        else:
                            choices=[i for i in entry['candidate_files'] if f'/reports-{row["iteration"]}/' in i['path']]
                            choices.sort(key=lambda i:0 if i['path'].endswith('.xml') else 1)
                        if not choices:
                            record['attempts'].append(dict(row=row['row'],iteration=row['iteration'],status='no_archived_report_for_iteration'));continue
                        source=download_items([choices[0]])[0];data=(ROOT/source['local_path']).read_bytes()
                        try:result=parse(data,source['path'],meta['configured_test'])
                        except ValueError as e:
                            record['attempts'].append(dict(row=row['row'],iteration=row['iteration'],member=source,status='parse_error',error=str(e)))
                            # Unsupported formats require a parser review, not hundreds of downloads.
                            if 'Unsupported input' in str(e):record['status']='parser_extension_required';break
                            continue
                    record['attempts'].append(dict(row=row['row'],iteration=row['iteration'],member=source,status='parsed',matched_cases=result['matched_cases'],failure_records=len(result['failures'])))
                    # A suite-level failure may require inspecting every run.
                    # Fetch one bounded contiguous block instead of 100 tiny requests.
                    # This changes transport only; every target/CRC check still runs.
                    if not result['failures'] and len(record['attempts'])==1 and len(failing)>1 and meta['label']=='ID':
                        items=entry['candidate_files']
                        if items:
                            start=min(i['offset'] for i in items)
                            end=max(i['offset']+30+len(i['path'].encode())+512+i['compressed'] for i in items)
                            if end-start<=2_000_000:
                                try:
                                    remote=HTTPRangeFile(FILE['links']['self'],FILE['size']);remote.seek(start);remote.read(end-start)
                                    record['transport_prefetch']=dict(start=start,end=end,bytes=end-start)
                                except RateLimited:raise
                                except Exception as error:record['transport_prefetch_error']=str(error)
                    if result['failures']:
                        failure=result['failures'][0]
                        record.update(status='confirmed_failure',iteration=row['iteration'],source_row=row['row'],diagnostic_member=source,failure=failure,text_sha256=digest(failure['text']))
                        break
                else:record['status']='no_confirmed_target_diagnostic'
        except RateLimited as e:record.update(status='deferred_rate_limit',error=str(e))
        except Exception as e:record.update(status='unresolved',error=str(e))
        dest.write_text(json.dumps(record,indent=2),encoding='utf-8');return record
    order={'TD':0,'NIO':1,'OD':2,'ID':3,'UNCLASSIFIED':4}
    pairs=sorted(entries.items(),key=lambda p:(order[p[1]['metadata']['label']],p[0]));results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(collect,p) for p in pairs]
        for i,f in enumerate(concurrent.futures.as_completed(futures),1):
            r=f.result();results.append(r)
            if i%25==0 or r['status'] in ('unresolved','parser_extension_required'):print(f'Containers processed {i}/{len(entries)}; {r["container"]}: {r["status"]}',flush=True)
    (ROOT/'data/audit/first_failure_manifest.json').write_text(json.dumps(sorted(results,key=lambda x:x['container']),separators=(',',':')),encoding='utf-8')
    from collections import Counter
    print(json.dumps(dict(Counter(r['status'] for r in results))),flush=True)

if __name__=='__main__':main()
