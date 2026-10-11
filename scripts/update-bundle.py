#!/usr/bin/env python3
"""Build a local deterministic updater bundle. This does not sign or publish it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile

MAGIC=b'MINYAR-BUNDLE-1\n'
MAX_BYTES=134217728
MAX_ENTRIES=4096
MAX_PATH=512

def safe_path(value):
    if not isinstance(value,str) or not 1<=len(value.encode('utf-8'))<=MAX_PATH:
        raise ValueError('bundle path exceeds its limit')
    try:value.encode('ascii')
    except UnicodeEncodeError:raise ValueError('bundle v1 requires portable ASCII paths') from None
    for component in value.split('/'):
        if not 1<=len(component)<=64 or component in ('.','..') or component.startswith(' ') or component.endswith(('.', ' ')):
            raise ValueError('invalid bundle path component')
        if not re.fullmatch(r'[A-Za-z0-9._ -]+',component):
            raise ValueError('bundle paths cannot contain separators, controls or Windows streams')
        stem=component.split('.')[0].upper()
        if stem in ('CON','PRN','AUX','NUL','CONIN$','CONOUT$') or re.fullmatch(r'(?:COM|LPT)[0-9]',stem):
            raise ValueError('reserved Windows bundle filename')
    return value

def snapshot(info):
    return (info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
            getattr(info,'st_file_attributes',0))

def forbidden(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&0x400)

def native_image(data):
    return data[:4] in (b'\x7fELF',b'\xfe\xed\xfa\xce',b'\xce\xfa\xed\xfe',
        b'\xfe\xed\xfa\xcf',b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',
        b'\xca\xfe\xba\xbf',b'\xbf\xba\xfe\xca') or data[:2]==b'MZ'

def inspect_attributes(path):
    if hasattr(os,'listxattr'):
        # File-data bundles cannot retain xattr-only signatures/resource forks,
        # including attributes attached to the bundle root or directories.
        names=os.listxattr(path,follow_symlinks=False)
        if any(name.startswith('com.apple.cs.') or name=='com.apple.ResourceFork' for name in names):
            raise ValueError('xattr code signatures/resource forks are unsupported; use regular-file resources')

def prepare(root,output,entrypoint,*,notarized_app=None):
    entrypoint=safe_path(entrypoint)
    root=Path(root).absolute();output=Path(output).absolute()
    if forbidden(root.lstat()) or not root.is_dir():
        raise ValueError('bundle root must be a real directory')
    root=root.resolve(strict=True)
    if output.resolve().is_relative_to(root):
        raise ValueError('bundle output cannot be inside its input tree')
    records=[];observed={};folded=set();root_stat=snapshot(root.lstat())
    inspect_attributes(root)
    def scan(directory):
        for path in sorted(directory.iterdir(),key=lambda p:p.name):
            relative=safe_path(path.relative_to(root).as_posix())
            fold=relative.lower()
            if fold in folded:raise ValueError('case-insensitive duplicate bundle path')
            folded.add(fold);info=path.lstat()
            if forbidden(info):raise ValueError('bundle links and reparse points are not supported')
            inspect_attributes(path)
            if len(records)>=MAX_ENTRIES:raise ValueError('bundle has too many entries')
            if stat.S_ISDIR(info.st_mode):
                records.append((relative,'D',0,0,path));observed[path]=snapshot(info);scan(path)
            elif stat.S_ISREG(info.st_mode):
                if info.st_nlink!=1:raise ValueError('bundle hardlinks are not supported')
                if info.st_size>MAX_BYTES:raise ValueError('bundle file exceeds size limit')
                mode=int(relative==entrypoint or bool(info.st_mode&0o111))
                records.append((relative,'F',mode,info.st_size,path));observed[path]=snapshot(info)
            else:raise ValueError('bundle contains a special file')
    scan(root)
    records.sort(key=lambda record:record[0])
    main=[record for record in records if record[0]==entrypoint and record[1]=='F']
    if len(main)!=1:raise ValueError('entrypoint is not a regular bundle file')
    with main[0][4].open('rb') as stream:
        if not native_image(stream.read(4)):
            raise ValueError('entrypoint must be a native executable, never an interpreter script')
    app=None
    if notarized_app is not None:
        if sys.platform!='darwin':raise ValueError('notarized application verification requires actual macOS')
        app=root/safe_path(notarized_app)
        if not app.is_dir() or app.suffix!='.app':raise ValueError('expected an application bundle under the input root')
        def verify_app():
            for command in [
                ['codesign','--verify','--deep','--strict','--verbose=2',str(app)],
                ['xcrun','stapler','validate',str(app)],
                ['spctl','--assess','--type','execute','--verbose=2',str(app)]]:
                subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
        verify_app()
    entry=entrypoint.encode('ascii')
    expected=len(MAGIC)+4+len(entry)+4+sum(14+len(name.encode('ascii'))+size for name,_,_,size,_ in records)
    if expected>MAX_BYTES:raise ValueError('bundle exceeds 128 MiB including its index')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.minyar-bundle-',dir=output.parent,delete=False) as stream:
        temporary=Path(stream.name)
        try:
            stream.write(MAGIC+struct.pack('>I',len(entry))+entry+struct.pack('>I',len(records)))
            for name,kind,mode,size,path in records:
                encoded=name.encode('ascii')
                stream.write(struct.pack('>BBIQ',ord(kind),mode,len(encoded),size)+encoded)
                if kind=='F':
                    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0))
                    with os.fdopen(fd,'rb') as source:
                        if snapshot(os.fstat(source.fileno()))!=observed[path]:
                            raise ValueError('bundle input changed while preparing output')
                        remaining=size
                        while remaining:
                            chunk=source.read(min(65536,remaining))
                            if not chunk:raise ValueError('bundle file was truncated')
                            stream.write(chunk);remaining-=len(chunk)
                        if source.read(1) or snapshot(os.fstat(source.fileno()))!=observed[path]:
                            raise ValueError('bundle file changed during copying')
            stream.flush();os.fsync(stream.fileno())
            # Rescan the actual index too. Directory timestamps/sizes alone
            # cannot prove that no unindexed entry was added or removed.
            previous_records,previous_observed=records,observed
            records=[];observed={};folded=set()
            scan(root);records.sort(key=lambda record:record[0])
            if snapshot(root.lstat())!=root_stat or records!=previous_records or observed!=previous_observed:
                raise ValueError('bundle tree changed while preparing output')
            if app is not None:verify_app()
            with temporary.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
            if temporary.stat().st_size!=expected:raise ValueError('bundle size mismatch')
            # Close before replace so Windows never publishes an open temporary.
            stream.close();os.replace(temporary,output)
            if os.name=='posix':
                fd=os.open(output.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
                try:os.fsync(fd)
                finally:os.close(fd)
        finally:
            # Close on failure too: Windows will not unlink an open temporary.
            stream.close()
            if temporary.exists():temporary.unlink()
    return {'format':1,'entrypoint':entrypoint,'entries':len(records),'size':expected,'sha256':digest}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--entrypoint',required=True)
    parser.add_argument('--notarized-app',help='relative .app path; verify codesign, stapler and Gatekeeper on macOS')
    args=parser.parse_args()
    try:print(json.dumps(prepare(args.root,args.output,args.entrypoint,notarized_app=args.notarized_app),sort_keys=True))
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        parser.exit(1,f'update bundle preparation failed: {error}\n')

if __name__=='__main__':main()
