"""Version 1 common extraction cleanup and explicit identifier masking."""
import re
ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
HARNESS=re.compile(r'^\s*(?:at\s+)?(?:edu\.illinois\.(?:cs\.)?(?:nondex|testrunner|dt)|org\.apache\.maven\.surefire|org\.jacoco)\.',re.I)
EXCEPTION=re.compile(r'\b(?:[A-Za-z_$][\w$]*\.)*[A-Z_$][\w$]*(?:Exception|Error|Failure)\b')
GENERIC={'java','core','test','tests','main','api','common','commons','org','com','net','apache','incubator','project','server','client','junit','testng','hamcrest','mockito','jupiter'}

def clean(text):
    text=ANSI.sub('',text.replace('\r\n','\n').replace('\r','\n'))
    return '\n'.join(line.rstrip() for line in text.splitlines() if not HARNESS.match(line)).strip()

def literal_replace(text,value,replacement,ignorecase=False):
    if not value:return text
    return re.sub(r'(?<![\w$])'+re.escape(value)+r'(?![\w])',replacement,text,flags=re.I if ignorecase else 0)

def mask(text,meta,canonical_repository=None,exception_type=None):
    klass,method=meta['configured_test'].split('#',1);simple=klass.split('.')[-1];base_method=method.split('[',1)[0]
    protected=sorted(set(EXCEPTION.findall(text))|({exception_type} if exception_type else set()),key=len,reverse=True)
    kept={}
    for i,value in enumerate(protected):
        key=f'ZZPROTECTEDEXCEPTION{i}ZZ';kept[key]=value;text=text.replace(value,key)
    names={meta['project'].rstrip('/').split('/')[-1]}
    if canonical_repository:names.add(canonical_repository.rstrip('/').split('/')[-1])
    for name in list(names):names.update(part for part in re.split(r'[-_]',name) if len(part)>=4 and part.lower() not in GENERIC)
    names={n for n in names if n.lower() not in GENERIC}
    for url in (meta['project'],canonical_repository):
        if url:text=text.replace(url,'PROJECT')
    path_re=re.compile(r'(?:[A-Za-z]:[\\/]|(?<![:\w])/)[^\s<>"\x27)\],;]+')
    path_identifiers=[n.lower() for n in names|{simple,klass.replace('.','/')} if len(n)>=4]
    text=path_re.sub(lambda m:'PROJECT_PATH' if any(n in m.group().lower() for n in path_identifiers) else m.group(),text)
    text=literal_replace(text,klass+'.'+method,'TEST_CLASS.TEST_METHOD')
    text=literal_replace(text,klass+'#'+method,'TEST_CLASS.TEST_METHOD')
    text=literal_replace(text,klass+'.'+base_method,'TEST_CLASS.TEST_METHOD')
    text=literal_replace(text,klass,'TEST_CLASS')
    text=literal_replace(text,simple,'TEST_CLASS')
    text=re.sub(r'(?<=TEST_CLASS\.)'+re.escape(base_method)+r'(?!\w)','TEST_METHOD',text)
    if len(method)>=6:text=literal_replace(text,method,'TEST_METHOD')
    for name in sorted(names,key=len,reverse=True):text=literal_replace(text,name,'PROJECT',ignorecase=True)
    for key,value in kept.items():text=text.replace(key,value)
    return text

def source_format(member_path):
    if '/.nondex/' in member_path:return 'nondex_report'
    if member_path.endswith('rounds-test-results.csv') or '/dtfixingtools/' in member_path:return 'nio_json'
    if member_path.endswith('.xml'):return 'surefire_xml'
    if member_path.endswith('.txt'):return 'surefire_text'
    return 'other'
