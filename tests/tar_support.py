"""Independent structural policy oracle, deliberately separate from tarfile.
Every permitted rejection of a Python-accepted mutation names a checked wire
violation here. Complete entries before that violation must still be emitted.
"""
from decimal import Decimal
import tarfile

MAX = (1 << 63) - 1

def number(field):
    if field[0] & 128:
        return int.from_bytes(bytes([field[0] & 127]) + field[1:], 'big') - (1 << (len(field)*8 - 1) if field[0] & 64 else 0)
    field = field.lstrip(b'\0 ').rstrip(b'\0 ')
    if any(c < 48 or c > 55 for c in field): raise ValueError('numeric grammar')
    return int(field or b'0', 8)

def records(data):
    at = 0; result = []
    while at < len(data):
        stop = data.find(b' ', at)
        if stop < 0 or not data[at:stop].isdigit(): raise ValueError('PAX length syntax')
        size = int(data[at:stop]); end = at + size
        if size < stop-at+4 or end > len(data) or data[end-1:end] != b'\n': raise ValueError('PAX record span')
        body = data[stop+1:end-1]
        if b'=' not in body: raise ValueError('PAX keyword')
        key, value = body.split(b'=', 1)
        if not key or any(c < 33 or c > 126 or c == 61 for c in key): raise ValueError('PAX keyword')
        result.append((key,value)); at = end
    return result

def strict_scan(source, max_metadata=1048576, max_chain=64, max_headers=1000000, max_path=4096):
    """Return complete physical spans/effective attrs and a narrow failure reason."""
    at=0; spans=[]; globals={}; local={}; chain=0; metadata=0; headers=0; start=0; long_path=None; long_link=None
    def reject(reason): return spans, reason
    while True:
        if len(source)-at < 512: return reject('missing/truncated header/footer')
        h=source[at:at+512]
        if h==bytes(512):
            if chain: return reject('dangling extension')
            if len(source)-at < 1024 or (len(source)-at)%512 or any(source[at:]): return reject('two end blocks/zero record padding')
            return spans,None
        headers+=1
        if headers>max_headers: return reject('header limit')
        try:
            parsed=tarfile.TarInfo.frombuf(h,'utf-8','surrogateescape')
            if h[257:265] not in (bytes(8), b'ustar\00000', b'ustar  \0'): return reject('magic/version')
            fields=[number(h[o:o+n]) for o,n in [(100,8),(108,8),(116,8),(124,12),(136,12),(329,8),(337,8)]]
            if any(n < -MAX-1 or n > MAX for n in fields): return reject('numeric overflow')
            if fields[0]<0 or fields[3]<0 or fields[5]<0 or fields[6]<0: return reject('negative mode/size/device')
        except (ValueError,tarfile.TarError): return reject('checksum or numeric grammar')
        kind=h[156] or 48; size=fields[3]; extension=kind in (120,103,76,75)
        if extension:
            chain+=1; metadata+=size
            if chain>max_chain or metadata>max_metadata: return reject('extension chain/metadata limit')
        else:
            if kind not in range(48,55): return reject('unsupported member type/sparse')
            attrs=dict(globals); attrs.update(local); attrs={k:v for k,v in attrs.items() if v}
            if len(attrs)>4096: return reject('effective attribute count limit')
            if sum(len(k)+len(v) for k,v in attrs.items())>max_metadata: return reject('effective metadata limit')
            for k,v in attrs.items():
                if k in (b'size',b'uid',b'gid',b'SCHILY.devmajor',b'SCHILY.devminor'):
                    text=v[1:] if v.startswith(b'-') and k!=b'size' else v
                    if not text.isdigit(): return reject('PAX integer grammar')
                    n=int(v)
                    if n < -MAX-1 or n>MAX: return reject('PAX integer overflow')
                    if k==b'size': size=n
                if k==b'mtime':
                    text=v[1:] if v.startswith(b'-') else v; parts=text.split(b'.')
                    if len(parts)>2 or any(not x.isdigit() for x in parts): return reject('PAX timestamp grammar')
                    d=Decimal(v.decode()); nanos=d*1000000000
                    if nanos != nanos.to_integral_value() or d < -MAX-1 or d >= MAX+1: return reject('timestamp precision/range')
            path=parsed.name.encode('utf-8','surrogateescape'); link=parsed.linkname.encode('utf-8','surrogateescape')
            path=attrs.get(b'path',long_path if long_path is not None else path)
            link=attrs.get(b'linkpath',long_link if long_link is not None else link)
            for k,v in [(b'path',path),(b'linkpath',link),(b'uname',attrs.get(b'uname',b'')),(b'gname',attrs.get(b'gname',b''))]:
                if len(v)>max_path or b'\0' in v or (k==b'path' and not v): return reject('byte name limit/NUL')
            if kind!=48 and size: return reject('nonregular payload')
        payload=at+512; end=payload+size+(-size%512)
        if end>len(source): return reject('payload/padding truncation')
        if extension:
            data=source[payload:payload+size]
            if kind in (120,103):
                try: pairs=records(data)
                except ValueError as e: return reject(str(e))
                target=globals if kind==103 else local
                for k,v in pairs:
                    if k.startswith(b'GNU.sparse.') or k==b'SCHILY.realsize' or (k==b'SCHILY.filetype' and v==b'sparse'): return reject('unsupported sparse attributes')
                    if kind==103 and not v: target.pop(k,None)
                    else: target[k]=v
                if len(target)>4096 or sum(len(k)+len(v) for k,v in target.items())>max_metadata: return reject('attribute count/metadata limit')
                if kind==103: globals={k:v for k,v in globals.items() if v}
            else:
                value=data[:-1] if data.endswith(b'\0') else data
                if not value or len(value)>max_path or b'\0' in value: return reject('GNU byte name limit/NUL')
                if kind==76: long_path=value
                else: long_link=value
        else:
            spans.append((start,at,payload,end,attrs)); chain=0; metadata=0; local={}; long_path=long_link=None; start=end
        at=end
