"""Extract only failures attributed to an exact configured target test.

Archive paths, labels, XML properties and unrelated test outputs are provenance,
never classifier input. Missing diagnostic fields remain explicitly missing.
"""
import hashlib, json, re, xml.etree.ElementTree as ET

def target_parts(configured_test):
    if '#' not in configured_test: raise ValueError('Expected Class#method metadata')
    return configured_test.split('#',1)

def is_method(name, method):
    # Explicit Surefire parameter suffix or JUnit 5 Java type signature.
    # Never arbitrary startswith matching or display-name inference.
    return name==method or bool(re.fullmatch(re.escape(method)+r'\[[^\r\n]*\]',name)) or bool(re.fullmatch(re.escape(method)+r'\([A-Za-z0-9_.$<>,? \[\]]*\)(?:\[[^\r\n]*\])?',name))

def infrastructure_flags(text):
    rules={
        'class_initialization':r'Could not initialize class|ExceptionInInitializerError',
        'missing_runtime_class':r'ClassNotFoundException|NoClassDefFoundError',
        'unsupported_bytecode':r'UnsupportedClassVersionError',
        'missing_native_library':r'UnsatisfiedLinkError',
    }
    return [k for k,p in rules.items() if re.search(p,text)]

def surefire(data, configured_test):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper(): raise ValueError('DTD/entity XML refused')
    klass,method=target_parts(configured_test)
    root=ET.fromstring(data); records=[]; matched=0; passed=0; skipped=0
    signatures=set()
    for case in root.iter():
        if case.tag.rsplit('}',1)[-1]=='testcase' and case.get('classname')==klass:
            signature=re.fullmatch(re.escape(method)+r'(\([A-Za-z0-9_.$<>,? \[\]]*\))(?:\[[^\r\n]*\])?',case.get('name',''))
            if signature:signatures.add(signature.group(1))
    if len(signatures)>1:raise ValueError('Ambiguous overloaded target method signatures')
    for case in root.iter():
        if case.tag.rsplit('}',1)[-1]!='testcase': continue
        if case.get('classname')!=klass or not is_method(case.get('name',''),method): continue
        matched+=1
        errors=[c for c in case if c.tag.rsplit('}',1)[-1] in ('failure','error')]
        if any(c.tag.rsplit('}',1)[-1]=='skipped' for c in case): skipped+=1
        elif not errors: passed+=1
        for error in errors:
            exception=error.get('type','').strip(); message=error.get('message','').strip(); trace=(error.text or '').strip()
            # Retain each field once in a documented common diagnostic representation.
            text='\n'.join(x for x in [exception,message,trace] if x)
            if not text: continue
            records.append(dict(format='surefire_xml',testcase_name=case.get('name'),outcome=error.tag.rsplit('}',1)[-1],exception_type=exception or None,message=message or None,stack_trace=trace or None,text=text,missing_exception_type=not bool(exception),review_flags=infrastructure_flags(text)))
    return dict(matched_cases=matched,passed_cases=passed,skipped_cases=skipped,failures=records)

def nio_json(data, configured_test):
    klass,method=target_parts(configured_test); target=klass+'.'+method
    obj=json.loads(data); results=obj.get('results')
    if not isinstance(results,dict): raise ValueError('Unsupported NIO result schema')
    records=[]; matched=0; passed=0; other=0
    for key,value in results.items():
        if not isinstance(value,dict) or value.get('name')!=target: continue
        # Repetition is represented by the :integer key, not a new independent test.
        if key!=target and not re.fullmatch(re.escape(target)+r':\d+',key): continue
        matched+=1; status=value.get('result')
        if status not in ('FAILURE','FAIL','ERROR'):
            if status in ('PASS','SUCCESS','PASSED'): passed+=1
            else: other+=1
            continue
        trace=value.get('stackTrace')
        if not isinstance(trace,list) or not all(isinstance(s,str) for s in trace): continue
        text='\n'.join(trace).strip()
        if not text: continue
        records.append(dict(format='nio_json',testcase_name=key,outcome=status,exception_type=None,message=None,stack_trace=text,text=text,missing_exception_type=True,review_flags=infrastructure_flags(text)))
    return dict(matched_cases=matched,passed_cases=passed,other_cases=other,failures=records)

def surefire_text(data,configured_test):
    klass,method=target_parts(configured_test);text=data.decode('utf-8-sig')
    suite=re.search(r'^Test set:\s*(\S+)\s*$',text,re.M)
    if not suite or suite.group(1)!=klass: return dict(matched_cases=0,passed_cases=0,failures=[])
    header=re.compile(r'^(?!Tests run:)(.+?)\s+Time elapsed:\s+[^\r\n]*?<<<\s+(FAILURE|ERROR)!\s*$',re.M)
    markers=list(header.finditer(text));records=[];matched=0
    for i,marker in enumerate(markers):
        name=marker.group(1).strip()
        if name.endswith('('+klass+')'): name=name[:-(len(klass)+2)]
        elif name.startswith(klass+'.'): name=name[len(klass)+1:]
        if not is_method(name,method): continue
        matched+=1;end=markers[i+1].start() if i+1<len(markers) else len(text)
        trace=text[marker.end():end].strip()
        if not trace: continue
        first=trace.splitlines()[0]
        exception=re.match(r'^([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)(?::\s?(.*))?$',first)
        exception_type=exception.group(1) if exception else None
        message=exception.group(2) if exception else None
        # Keep the full diagnostic body, including continuation message lines.
        combined='\n'.join(x for x in (exception_type,message,trace) if x)
        records.append(dict(format='surefire_text',testcase_name=name,outcome=marker.group(2).lower(),exception_type=exception_type,message=message,stack_trace=trace,text=combined,missing_exception_type=exception_type is None,review_flags=infrastructure_flags(combined)))
    return dict(matched_cases=matched,passed_cases=0,failures=records)

def parse(data, member_path, configured_test):
    if member_path.endswith('.xml'): return surefire(data,configured_test)
    if member_path.endswith('.txt') and '/surefire-reports/' in member_path: return surefire_text(data,configured_test)
    if '/test-runs/results/' in member_path: return nio_json(data,configured_test)
    raise ValueError('Unsupported input; use target Surefire XML or NIO results JSON')

def digest(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()
