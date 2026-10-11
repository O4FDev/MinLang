#!/usr/bin/env python3
"""Signed KU/path constraints from OpenSSL, enforcing TLS1.3 RFC8446 signing use."""
import argparse, importlib.util, os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("tls_tests",ROOT/"tests/tls-local.py")
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def main():
    p=argparse.ArgumentParser();p.add_argument("--sanitize",action="store_true");a=p.parse_args()
    if a.sanitize:
        for name in ("MINYAR_CLANG_FLAGS","MINYAR_NATIVE_FLAGS","MINYAR_RUNTIME_FLAGS"):
            os.environ[name]="-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module"
    results=[]
    with tempfile.TemporaryDirectory(prefix="minyar-signing-usage-") as d:
        ca=fixtures.Certificates(d);ca.root("root")
        for name,usage,bits in (("server-sign","serverAuth","digitalSignature"),
                                ("server-encipher","serverAuth","keyEncipherment"),
                                ("server-agreement","serverAuth","keyAgreement"),
                                ("client-sign","clientAuth","digitalSignature"),
                                ("client-agreement","clientAuth","keyAgreement"),
                                ("server-both","serverAuth","digitalSignature,keyEncipherment")):
            ca.leaf(name,"root",usage=usage,extra="keyUsage=critical,"+bits)
            text=subprocess.check_output(["openssl","x509","-in",str(ca.path(name,"pem")),"-noout","-text"],text=True)
            assert "Digital Signature" in text if "digitalSignature" in bits else "Digital Signature" not in text
        ca.leaf("no-ku","root")
        config=ca.path("no-ku","cnf");config.write_text(config.read_text().replace("keyUsage=critical,digitalSignature\n",""))
        ca.path("no-ku","index").write_text("")
        fixtures.openssl("ca","-batch","-notext","-config",config,"-in",ca.path("no-ku","csr"),"-out",ca.path("no-ku","pem"));ca.der("no-ku")
        ca.leaf("intermediate0","root",ca=True);ca.leaf("child-ca","intermediate0",ca=True)
        # Self-issued intermediates do not consume pathLenConstraint. Give the
        # child a distinct subject so this is a real depth violation.
        fixtures.openssl("req","-new","-key",ca.path("child-ca","key"),"-subj","/CN=distinct-child-ca","-out",ca.path("child-ca","csr"))
        ca.path("child-ca","index").write_text("")
        fixtures.openssl("ca","-batch","-notext","-config",ca.path("child-ca","cnf"),"-in",ca.path("child-ca","csr"),"-out",ca.path("child-ca","pem"));ca.der("child-ca")
        ca.leaf("bad-path","child-ca")
        chain_pem=Path(d)/"bad-path-chain.pem"
        chain_pem.write_bytes(ca.path("child-ca","pem").read_bytes()+ca.path("intermediate0","pem").read_bytes())
        oracle=subprocess.run(["openssl","verify","-x509_strict","-purpose","sslserver","-CAfile",str(ca.path("root","pem")),"-untrusted",str(chain_pem),str(ca.path("bad-path","pem"))],capture_output=True,text=True)
        assert oracle.returncode and "path length constraint exceeded" in oracle.stderr,(oracle.stdout,oracle.stderr)
        binary=Path(d)/"usage";fixtures.compile_program(ROOT/"tests/tls-signing-usage.min",binary)
        cases=[("server-sign","server",True,[]),("server-both","server",True,[]),("no-ku","server",True,[]),
               ("server-encipher","server",False,[]),("server-agreement","server",False,[]),
               ("client-sign","client",True,[]),("client-agreement","client",False,[]),
               ("client-sign","server",False,[]),("server-sign","client",False,[]),
               ("bad-path","server",False,["child-ca","intermediate0"])]
        for name,role,valid,chain in cases:
            r=subprocess.run([str(binary),str(ca.path(name,"der")),str(ca.path("root","der")),role,"valid" if valid else "invalid",
                              *([str(ca.path(part,"der")) for part in chain]+[""]*(2-len(chain)))],capture_output=True,text=True,timeout=30)
            print(name,role,r.returncode,r.stdout.strip(),r.stderr.strip(),flush=True)
            results.append((name,role,r.returncode,r.stdout,r.stderr))
    assert all(row[2]==0 for row in results),results
if __name__=="__main__":main()
