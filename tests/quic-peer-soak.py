#!/usr/bin/env python3
"""Remote independent Quinn process monitor with no stdout pipe deadlock."""
import argparse,hashlib,json,os,platform,subprocess,time
from pathlib import Path
def sample(pid):
    fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return {'rss_bytes':int(fields[21])*os.sysconf('SC_PAGE_SIZE'),'cpu_seconds':(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--peer-binary',type=Path,required=True);parser.add_argument('--fixtures',type=Path,required=True);parser.add_argument('--address',required=True);parser.add_argument('--duration',type=int,required=True);parser.add_argument('--peers',type=int,required=True);parser.add_argument('--interval-ms',type=int,default=15000);parser.add_argument('--setup-delay-ms',type=int,default=10);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--log',type=Path,required=True);options=parser.parse_args()
    if platform.system()!='Linux' or os.environ.get('MINYAR_REMOTE_LOAD')!='1':parser.error('remote Linux opt-in required')
    if not 1<=options.peers<=16384 or options.duration<1 or options.interval_ms<1 or not 0<=options.setup_delay_ms<=10000:parser.error('invalid bounded scale configuration')
    command=[str(options.peer_binary),options.address,str(options.fixtures/'root.der'),str(options.fixtures/'client.der'),str(options.fixtures/'client.pk8'),str(options.duration),str(options.peers),str(options.interval_ms)]
    idle_seconds=int(os.environ.get('MINYAR_QUINN_IDLE_SECONDS','0'))
    if not 0<=idle_seconds<=120:parser.error('invalid bounded idle window')
    started=time.monotonic();process=None
    report={'peers':options.peers,'duration_after_all_authenticated':options.duration,'idle_seconds':idle_seconds,'heartbeat_interval_ms':options.interval_ms,'setup_delay_ms':options.setup_delay_ms,'binary_sha256':hashlib.sha256(options.peer_binary.read_bytes()).hexdigest(),'samples':[]}
    with options.log.open('w') as log:
        try:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,MINYAR_QUINN_SETUP_DELAY_MS=str(options.setup_delay_ms)))
            report['pid']=process.pid;print('PEER_PID',process.pid,flush=True)
            while process.poll() is None:
                if time.monotonic()-started>options.duration+660+idle_seconds+(options.peers*5+999)//1000:raise TimeoutError('independent peer exceeded setup/run deadline')
                try:
                    data=sample(process.pid);data['elapsed_seconds']=time.monotonic()-started;data['host_load_average']=list(os.getloadavg());report['samples'].append(data)
                except FileNotFoundError:break
                options.report.write_text(json.dumps(report,indent=2)+'\n');time.sleep(10)
            report['status']=process.wait();report['elapsed_seconds']=time.monotonic()-started
            options.report.write_text(json.dumps(report,indent=2)+'\n')
            assert process.returncode==0,options.log.read_text()[-4000:]
        finally:
            if process and process.poll() is None:process.terminate();process.wait(timeout=10)
if __name__=='__main__':main()
