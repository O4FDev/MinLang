#!/usr/bin/env python3
"""Export all scalar primitive ratios and controls; no new measurement."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'runtime-list-bulk-cpu-results.json'
data = json.loads(SOURCE.read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
figure,axes=plt.subplots(1,2,figsize=(12,8.7),gridspec_kw={'width_ratios':[1.8,1]})
colors={'system':'#2365a8','fixed':'#c06a24'}
labels=[]
for i,row in enumerate(data['pointwise_summary']):
    profile,n,mode=row['case']
    name='idle' if mode==0 else ('debt' if mode==1 else 'references')
    labels.append(f'{profile}, n={n:,}, {name}')
    for axis in axes:
        if axis==axes[1] and (mode==0 and n>=31):
            continue
        ratio=row['geometric_ratio'];lo,hi=row['geometric_interval95']
        axis.plot(row['ratios'],[i]*len(row['ratios']),'.',color=colors[profile],alpha=.25,markersize=5)
        axis.errorbar(ratio,i,xerr=[[ratio-lo],[hi-ratio]],fmt='o',color=colors[profile],capsize=3,markersize=5)
for axis in axes:
    axis.axvline(1,color='#666666',linewidth=1)
    axis.set_ylim(15.8,-.8)
    axis.grid(axis='x',alpha=.17)
    axis.set_xlabel('Baseline / candidate CPU ratio')
axes[0].set_yticks(range(16),labels)
axes[0].set_xlim(.88,2.65)
axes[0].set_title('All 192 adjacent pairs; full workload')
axes[1].set_yticks(range(16),['']*16)
axes[1].set_xlim(.89,1.12)
axes[1].set_title('Small and fallback controls (zoom)')
figure.suptitle('Scalar List bulk-copy primitive: test-accounted CPU observations',fontsize=14,y=.97)
figure.text(.02,.025,'Dots: every retained pair. Bars: geometric means and pointwise 95% paired-resampling intervals.\n'
    'Append + opaque full-value checksum + release/drain; debt includes construction. Loaded host and paced soak.\n'
    'MINYAR_RC_TESTING telemetry retained; system empty adverse rows retained. No production/app/latency claim.',fontsize=9)
figure.subplots_adjust(left=.28,right=.97,top=.92,bottom=.14,wspace=.12)
outputs=[]
for extension in ['svg','pdf','png']:
    path=HERE/f'runtime-list-bulk-timing.{extension}'
    figure.savefig(path,dpi=180)
    outputs.append({'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(HERE/'runtime-list-bulk-figure.json').write_text(json.dumps({'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input':SOURCE.name,'input_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'matplotlib_version':matplotlib.__version__,
    'outputs':outputs,'scope':'All192 retained pairs and saved intervals, no new measurement; zoom omits high-ratio idle rows labelled in fullpanel.'},indent=2)+'\n')
