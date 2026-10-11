#!/usr/bin/env python3
"""Unknown-CID Initial flood must remain stateless; exact final reactor counters."""
import argparse
from pathlib import Path
import socket
import struct
import tempfile
import time
from peer_edge_support import Lab,rss
def initial(index,token=b'',destination=None):
    dcid=destination or struct.pack('>Q',index+1);scid=b'client01'
    header=b'\xc0'+struct.pack('>I',1)+bytes([len(dcid)])+dcid+bytes([8])+scid
    n=len(token);encoded=bytes([n]) if n<64 else (n|0x4000).to_bytes(2,'big')
    # Two-byte QUIC Length includes one packet-number byte + opaque payload.
    packet=header+encoded+token
    return packet+(1200-len(packet)-2|0x4000).to_bytes(2,'big')+bytes(1200-len(packet)-2)
def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path);p.add_argument('--sanitize',action='store_true');p.add_argument('--evidence',type=Path);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='minyar-edge-retry-') as folder:
        lab=None
        try:
            lab=Lab(a.evidence or Path(folder),a.binary,a.sanitize,duration=7000,maximum=128)
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));sock.settimeout(1)
            sock.sendto(initial(0),('127.0.0.1',lab.udp_port));reply,_=sock.recvfrom(1500)
            assert reply[0]&0xf0==0xf0 and int.from_bytes(reply[1:5],'big')==1,'not a QUIC v1 Retry'
            at=5;n=reply[at];at+=1;assert reply[at:at+n]==b'client01';at+=n
            n=reply[at];at+=1;source=reply[at:at+n];at+=n;token=reply[at:-16]
            assert source!=struct.pack('>Q',1) and token.startswith(b'MQR1')
            before=rss(lab.edge.pid);count=4096
            for index in range(1,count+1):
                sock.sendto(initial(index),('127.0.0.1',lab.udp_port))
                response,_=sock.recvfrom(1500);assert response[0]&0xf0==0xf0
            # A token bound to the first source port cannot validate another.
            other=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);other.settimeout(.25)
            other.sendto(initial(0,token,source),('127.0.0.1',lab.udp_port))
            try:other.recvfrom(1500);raise AssertionError('unbound token got response')
            except socket.timeout:pass
            after=rss(lab.edge.pid);assert after-before<2048,(before,after)
            lines=lab.completed(timeout=10);counts=next(line for line in lines if line.startswith('EDGE_COUNTS ')).split()
            values=dict(part.split('=') for part in counts[1:])
            assert int(values['allocated'])==int(values['active'])==int(values['peer_slots'])==0,values
            assert int(values['retries'])==count+1 and int(values['retry_validated'])==0,values
            print(f'GREEN {count+1} independently encoded unknown Initials, wrong-address token denied; exact zero allocated/active/retained peers; RSS delta={after-before} KiB')
            sock.close();other.close()
        finally:
            if lab:lab.close()
if __name__=='__main__':main()
