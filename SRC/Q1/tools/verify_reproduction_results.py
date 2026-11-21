from __future__ import annotations
import gzip, hashlib, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF=json.loads((ROOT/'REPRODUCTION_REFERENCE.json').read_text(encoding='utf-8'))
tol=float(REF.get('float_abs_tolerance',1e-9)); problems=[]

def sha256(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def normalized_content_hash(p):
    data=gzip.open(p,'rb').read() if p.suffix=='.gz' else p.read_bytes()
    data=data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    return hashlib.sha256(data).hexdigest()

def compare(exp,got,path='root'):
    if isinstance(exp,dict):
        if not isinstance(got,dict): problems.append(f'{path}: type mismatch'); return
        for k,v in exp.items():
            if 'sha256' in k.lower():
                continue
            if k not in got: problems.append(f'{path}.{k}: missing'); continue
            compare(v,got[k],f'{path}.{k}')
    elif isinstance(exp,list):
        if not isinstance(got,list) or len(exp)!=len(got): problems.append(f'{path}: list mismatch'); return
        for i,(a,b) in enumerate(zip(exp,got)): compare(a,b,f'{path}[{i}]')
    elif isinstance(exp,(int,float)) and not isinstance(exp,bool):
        if not isinstance(got,(int,float)) or isinstance(got,bool): problems.append(f'{path}: numeric type mismatch'); return
        if isinstance(exp,int) and isinstance(got,int):
            if exp!=got: problems.append(f'{path}: expected {exp}, got {got}')
        elif not math.isclose(float(exp),float(got),rel_tol=0.0,abs_tol=tol):
            problems.append(f'{path}: expected {exp}, got {got}')
    else:
        if exp!=got: problems.append(f'{path}: expected {exp!r}, got {got!r}')

for rel,exp in REF['expected_json'].items():
    p=ROOT/rel
    if not p.is_file(): problems.append(f'missing result: {rel}'); continue
    try: got=json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc: problems.append(f'invalid json {rel}: {exc}'); continue
    compare(exp,got,rel)
for rel,want in REF['normalized_content_sha256'].items():
    p=ROOT/rel
    if not p.is_file(): problems.append(f'missing content result: {rel}')
    elif normalized_content_hash(p)!=want: problems.append(f'content mismatch: {rel}')
for rel,want in REF['model_sha256'].items():
    p=ROOT/rel
    if not p.is_file(): problems.append(f'missing model: {rel}')
    elif sha256(p)!=want: problems.append(f'model byte mismatch: {rel}')
report={'status':'PASS' if not problems else 'FAIL','float_abs_tolerance':tol,'problems':problems}
(ROOT/'REPRODUCTION_VERIFICATION_STATUS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if not problems else 1)
