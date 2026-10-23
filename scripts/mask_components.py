"""Post-review operation ablations; full mode must exactly reproduce v2."""
import re
from representations import GENERIC,EXCEPTION,literal_replace

MODES={'original':(False,False,False),'T':(True,False,False),'R':(False,True,False),'P':(False,False,True),'TR':(True,True,False),'TP':(True,False,True),'RP':(False,True,True),'full':(True,True,True)}

def transform(text,meta,canonical_repository,exception_type,mode):
    tests,repos,paths=MODES[mode]
    if mode=='original':return text
    klass,method=meta['configured_test'].split('#',1);simple=klass.split('.')[-1];base_method=method.split('[',1)[0]
    protected=sorted(set(EXCEPTION.findall(text))|({exception_type} if exception_type else set()),key=len,reverse=True)
    kept={}
    for i,value in enumerate(protected):
        key=f'ZZPROTECTEDEXCEPTION{i}ZZ';kept[key]=value;text=text.replace(value,key)
    names={meta['project'].rstrip('/').split('/')[-1]}
    if canonical_repository:names.add(canonical_repository.rstrip('/').split('/')[-1])
    for name in list(names):names.update(part for part in re.split(r'[-_]',name) if len(part)>=4 and part.lower() not in GENERIC)
    names={n for n in names if n.lower() not in GENERIC}
    if repos:
        for url in (meta['project'],canonical_repository):
            if url:text=text.replace(url,'PROJECT')
    if paths:
        path_re=re.compile(r'(?:[A-Za-z]:[\\/]|(?<![:\w])/)[^\s<>"\x27)\],;]+')
        identifiers=[n.lower() for n in names|{simple,klass.replace('.','/')} if len(n)>=4]
        text=path_re.sub(lambda m:'PROJECT_PATH' if any(n in m.group().lower() for n in identifiers) else m.group(),text)
    if tests:
        text=literal_replace(text,klass+'.'+method,'TEST_CLASS.TEST_METHOD')
        text=literal_replace(text,klass+'#'+method,'TEST_CLASS.TEST_METHOD')
        text=literal_replace(text,klass+'.'+base_method,'TEST_CLASS.TEST_METHOD')
        text=literal_replace(text,klass,'TEST_CLASS')
        text=literal_replace(text,simple,'TEST_CLASS')
        text=re.sub(r'(?<=TEST_CLASS\.)'+re.escape(base_method)+r'(?!\w)','TEST_METHOD',text)
        if len(method)>=6:text=literal_replace(text,method,'TEST_METHOD')
    if repos:
        for name in sorted(names,key=len,reverse=True):text=literal_replace(text,name,'PROJECT',ignorecase=True)
    for key,value in kept.items():text=text.replace(key,value)
    return text
