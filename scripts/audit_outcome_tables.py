"""Read archived tables, distinguish access failure from a passing test.

NonDex's header has more fields than data rows. Use only the first five
documented positions, then validate failures against original diagnostics.
"""
import collections, csv, io, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
csv.field_size_limit(10_000_000)

def parse_table(text,meta):
    rows=list(csv.reader(io.StringIO(text)));out=[];issues=[]
    if not rows: return out,['empty_table']
    if rows[0][:2]==['Iteration','Execution ID']:
        for n,row in enumerate(rows[1:],2):
            if len(row)<5: issues.append(f'short_row_{n}');continue
            try: iteration=int(row[0])
            except ValueError: issues.append(f'bad_iteration_{n}');continue
            out.append(dict(iteration=iteration,status=row[4].strip().lower(),execution_id=row[1],xml_path=row[3],row=n,scope='NonDex report; target testcase needs validation'))
    else:
        target=meta['configured_test'].replace('#','.')
        for n,row in enumerate(rows,1):
            if len(row)<4: issues.append(f'short_row_{n}');continue
            if row[0]!=target and not re.fullmatch(re.escape(target)+r'\[[^\r\n]*\]',row[0]):
                issues.append(f'target_name_mismatch_row_{n}');continue
            item=dict(status=row[1].strip().lower(),row=n,scope='exact target')
            if row[3].lstrip().startswith('{'):
                try: item.update(embedded_nio=json.loads(row[3]),iteration=n-1)
                except json.JSONDecodeError: issues.append(f'bad_json_{n}');continue
            else:
                try: item['iteration']=int(row[3])
                except ValueError: issues.append(f'bad_iteration_{n}');continue
                item['xml_path']=row[4] if len(row)>4 else None
            out.append(item)
    return out,issues

def main():
    candidates=json.loads((ROOT/'data/audit/archive_candidates.json').read_text());stored={}
    for p in (ROOT/'data/run_tables').glob('*.json'):
        row=json.loads(p.read_text());stored[row['container']]=row
    inventory=[]
    for c,entry in candidates.items():
        state=stored.get(c)
        result=dict(container=c,label=entry['metadata']['label'],project=entry['metadata']['project'],access_status=state['status'] if state else 'not_downloaded',outcomes=[],table_issues=[])
        if state and state['status']=='verified':
            tables=[m for m in state['members'] if m['path'].endswith('rounds-test-results.csv')]
            if len(tables)!=1: result['table_issues'].append(f'table_count_{len(tables)}')
            else:
                result['outcomes'],result['table_issues']=parse_table((ROOT/tables[0]['local_path']).read_text(encoding='utf-8-sig'),entry['metadata'])
                result['table_member']=tables[0]
        result['counts']=dict(collections.Counter(r['status'] for r in result['outcomes']))
        result['failure_rows']=sum(r['status'] in ('failure','error','fail') for r in result['outcomes'])
        inventory.append(result)
    (ROOT/'data/audit/outcome_inventory.json').write_text(json.dumps(inventory,separators=(',',':')),encoding='utf-8')
    summary=dict(containers=len(inventory),access_status=dict(collections.Counter(r['access_status'] for r in inventory)),verified_tables_with_failure=sum(r['failure_rows']>0 for r in inventory),verified_tables_with_no_failure=sum(bool(r['outcomes']) and not r['failure_rows'] for r in inventory),containers_with_table_issues=sum(bool(r['table_issues']) for r in inventory),failure_containers_by_label=dict(collections.Counter(r['label'] for r in inventory if r['failure_rows'])),caution='Table failures must be confirmed in target diagnostic; not a usable corpus count')
    (ROOT/'data/audit/outcome_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
