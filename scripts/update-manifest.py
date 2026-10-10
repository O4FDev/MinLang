#!/usr/bin/env python3
"""Prepare a signed updater envelope and R2 upload plan locally; never deploy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

DOMAIN=b'MINYAR-UPDATE-SIGNATURE-V1\0'

def signed(data,key,openssl='openssl',passphrase_env=None):
    """Use the operator's existing Ed25519 key; no production key generation."""
    key=Path(key).resolve(strict=True)
    password=['-passin','env:'+passphrase_env] if passphrase_env else []
    def run(args):
        return subprocess.run([openssl,*args],check=True,capture_output=True).stdout
    public=run(['pkey','-in',str(key),*password,'-pubout','-outform','DER'])
    if len(public)!=44 or public[:12]!=bytes.fromhex('302a300506032b6570032100'):
        raise ValueError('update signing key must be Ed25519')
    with tempfile.TemporaryDirectory(prefix='minyar-metadata-sign-') as directory:
        root=Path(directory); source=root/'metadata';signature=root/'signature';pub=root/'public.der'
        source.write_bytes(DOMAIN+data);pub.write_bytes(public)
        value=run(['pkeyutl','-sign','-rawin','-inkey',str(key),*password,'-in',str(source)])
        if len(value)!=64: raise ValueError('signer returned an invalid Ed25519 signature size')
        signature.write_bytes(value)
        run(['pkeyutl','-verify','-rawin','-pubin','-inkey',str(pub),'-keyform','DER',
             '-in',str(source),'-sigfile',str(signature)])
    return value,public[12:]

def prepare(artifact,output,app,target,channel,sequence,version,issued,expires,rollout,origin,*,sign):
    artifact=Path(artifact).resolve(strict=True);output=Path(output).absolute()
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',app): raise ValueError('invalid app identifier')
    if target not in ['macos-arm64','macos-x86_64','windows-arm64','windows-x86_64','linux-arm64','linux-x86_64']:
        raise ValueError('invalid target')
    if not re.fullmatch('[a-z][a-z0-9-]{0,31}',channel): raise ValueError('invalid channel')
    if not re.fullmatch(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)',version) or any(int(n)>2147483647 for n in version.split('.')):
        raise ValueError('version must be three canonical numeric components')
    if type(sequence) is not int or not 1<=sequence<=2147483647: raise ValueError('invalid metadata sequence')
    if type(rollout) is not int or rollout not in (1,10,100): raise ValueError('rollout must be 1, 10 or 100')
    if type(issued) is not int or type(expires) is not int or issued<0 or not 0<expires-issued<=604800 or expires>9223372036854775507:
        raise ValueError('invalid metadata expiry; maximum seven days')
    address=urlsplit(origin)
    if address.scheme!='https' or not address.hostname or address.username or address.password or address.query or address.fragment or address.path:
        raise ValueError('origin must be a pinned HTTPS origin without credentials, path or query')
    if not artifact.is_file() or not re.fullmatch('[A-Za-z0-9._-]+',artifact.name): raise ValueError('artifact needs a safe filename')
    size=artifact.stat().st_size
    if not 1<=size<=134217728: raise ValueError('artifact size outside 1..128MiB limit')
    with artifact.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    asset=f'releases/{digest}/{artifact.name}'
    pointer=f'channels/{channel}/{target}.update'
    data=('\n'.join(['MINYAR-UPDATE-1',app,target,channel,str(sequence),version,str(issued),str(expires),str(rollout),
                    origin+'/'+asset,digest,str(size)])+'\n').encode('ascii')
    signature,public=sign(data)
    if len(signature)!=64 or len(public)!=32: raise ValueError('invalid signer output')
    if len(data)>4096: raise ValueError('metadata exceeds updater limit')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.minyar-publication-',dir=output.parent) as directory:
        temp=Path(directory)
        staged=temp/'artifact';shutil.copyfile(artifact,staged)
        # Detect concurrent replacement/mutation while preparing the upload.
        if staged.stat().st_size!=size or hashlib.sha256(staged.read_bytes()).hexdigest()!=digest:
            raise ValueError('artifact changed during publication preparation')
        envelope=signature+data
        plan={'schema':1,'publicOrigin':origin,'objects':[
            {'key':asset,'sha256':digest,'size':size,'httpMetadata':{'contentType':'application/octet-stream','cacheControl':'public, max-age=31536000, immutable'}},
            {'key':pointer,'sha256':hashlib.sha256(envelope).hexdigest(),'size':len(envelope),
             'httpMetadata':{'contentType':'application/vnd.minyar.update','cacheControl':'no-store'}}],
             'order':'upload immutable artifact first; replace the single channel envelope last',
             'publicKeyHex':public.hex()}
        destination=output/asset;destination.parent.mkdir(parents=True,exist_ok=True)
        os.replace(staged,destination)
        channel_file=output/pointer;channel_file.parent.mkdir(parents=True,exist_ok=True)
        staged_envelope=temp/'envelope';staged_envelope.write_bytes(envelope);os.replace(staged_envelope,channel_file)
        staged_plan=temp/'plan';staged_plan.write_text(json.dumps(plan,indent=2)+'\n')
        os.replace(staged_plan,output/'r2-publish-plan.json')
    return plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['artifact','output','app','target','channel','version','origin','key']:
        parser.add_argument('--'+name,required=True)
    for name in ['sequence','issued','expires','rollout']:
        parser.add_argument('--'+name,required=True,type=int)
    parser.add_argument('--openssl',default='openssl')
    parser.add_argument('--passphrase-env')
    args=parser.parse_args()
    try:
        prepare(args.artifact,args.output,args.app,args.target,args.channel,args.sequence,args.version,args.issued,
                args.expires,args.rollout,args.origin,sign=lambda data:signed(data,args.key,args.openssl,args.passphrase_env))
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        parser.exit(1,f'update publication failed: {error}\n')

if __name__=='__main__': main()
