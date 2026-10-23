"""Revisit downloaded diagnostics after the documented TXT parser extension."""
import json
from remote_zip import ROOT
from parse_failure import parse,digest
count=0
for path in (ROOT/'data/first_failures').glob('*.json'):
    r=json.loads(path.read_text())
    if r['status']!='parser_extension_required':continue
    attempt=r['attempts'][-1];source=attempt['member']
    result=parse((ROOT/source['local_path']).read_bytes(),source['path'],r['metadata']['configured_test'])
    if result['failures']:
        failure=result['failures'][0]
        r.update(status='confirmed_failure',iteration=attempt['iteration'],source_row=attempt['row'],diagnostic_member=source,failure=failure,text_sha256=digest(failure['text']))
        r['attempts'].append(dict(row=attempt['row'],iteration=attempt['iteration'],member=source,status='parsed_after_TXT_extension',matched_cases=result['matched_cases'],failure_records=len(result['failures'])))
        path.write_text(json.dumps(r,indent=2),encoding='utf-8');count+=1
print('Locally reparsed confirmed failures:',count)
