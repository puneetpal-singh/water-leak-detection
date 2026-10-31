"""Measure shipped static bytes and reproducible gzip transfer estimates."""
from pathlib import Path
import gzip
import json

ROOT=Path(__file__).resolve().parents[1]
web=ROOT/'dashboard/web/dist'
manifest=json.loads((web/'manifest.json').read_text(encoding='utf-8'))
data=json.loads(gzip.decompress((web/manifest['bootstrap']).read_bytes()))
event=next(e for e in data['events'] if e['pipe']=='p523')
initial=['index.html','style.css','app.js','manifest.json',manifest['plotly'],manifest['bootstrap'],event['file']]
baseline=json.loads((ROOT/'results/web_performance_baseline.json').read_text())
report={
    'total_static_bytes':sum(p.stat().st_size for p in web.rglob('*') if p.is_file()),
    'overview_gzip_estimate_bytes':sum((web/f).stat().st_size if f.endswith('.gz')
                                     else len(gzip.compress((web/f).read_bytes(),mtime=0)) for f in initial),
    'chart_library_bytes':(web/manifest['plotly']).stat().st_size,
    'chart_library_gzip_estimate_bytes':len(gzip.compress((web/manifest['plotly']).read_bytes(),mtime=0)),
    'bootstrap_asset_bytes':(web/manifest['bootstrap']).stat().st_size,
    'initial_files':initial,
    'preserved_channels':len(data['sensors']),
    'preserved_event_windows':len(data['events']),
    'measurement_decimals':3,'score_decimals':5,
    'transfer_measurement':'Local gzip estimate; actual Vercel compression and caching may differ',
    'server_inference_required':False,
}
report['static_size_reduction_pct']=100*(1-report['total_static_bytes']/baseline['total_static_bytes'])
report['initial_gzip_reduction_pct']=100*(1-report['overview_gzip_estimate_bytes']/baseline['overview_gzip_estimate_bytes'])
assert report['total_static_bytes']<10_000_000,'Static bundle exceeded its 10 MB budget'
assert report['overview_gzip_estimate_bytes']<650_000,'Initial estimate exceeded its 650 KB budget'
(ROOT/'results/web_performance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['initial_files']},indent=2))
