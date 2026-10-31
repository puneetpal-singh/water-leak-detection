"""Small, immutable browser assets without dropping measurement precision."""
from pathlib import Path
import base64
import gzip
import hashlib
import json

def write_preview(destination: Path, measurements, event) -> None:
    """Small portfolio thumbnail drawn from the real p523 pressure window."""
    values = measurements['pressure:n506'].dropna()
    low, high = float(values.min()), float(values.max())
    def point(time, value):
        x = 64 + 772 * (time - values.index[0]).total_seconds() / (values.index[-1] - values.index[0]).total_seconds()
        y = 326 - 176 * (value - low) / (high - low)
        return f'{x:.1f},{y:.1f}'
    sampled = values.iloc[::2]
    points = ' '.join(point(t,float(v)) for t,v in sampled.items())
    onset_x = point(event.start,low).split(',')[0]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 420" role="img" aria-labelledby="title desc">
<title id="title">Water network sensor analytics</title><desc id="desc">Real BattLeDIM pressure n506 measurements around the p523 onset in January 2019</desc>
<rect width="900" height="420" rx="24" fill="#f3f6f1"/>
<g font-family="Segoe UI,Arial,sans-serif" fill="#20352e"><text x="48" y="52" font-size="24">L-Town / water network analytics</text>
<text x="48" y="86" font-size="16" fill="#53645d">119 measured channels · 19 test-year onsets · five detection methods</text>
<text x="64" y="130" font-size="14">Pressure n506 (m)</text>
<path d="M64 150H836 M64 238H836 M64 326H836" stroke="#d8e0da" fill="none"/>
<text x="12" y="155" font-size="13" fill="#53645d">{high:.1f}</text><text x="12" y="331" font-size="13" fill="#53645d">{low:.1f}</text>
<polyline points="{points}" fill="none" stroke="#087782" stroke-width="2" stroke-linejoin="round"/>
<path d="M{onset_x} 145V334" stroke="#a66a17" stroke-dasharray="4 4"/>
<text x="{float(onset_x)+8}" y="144" font-size="13" fill="#916019">Known onset</text>
<text x="64" y="358" font-size="13" fill="#53645d">14 January 2019</text><text x="722" y="358" font-size="13" fill="#53645d">19 January</text>
<text x="48" y="396" font-size="13" fill="#53645d">BattLeDIM simulation benchmark · CC BY 4.0 · sampled preview of the measured trace</text></g></svg>'''
    destination.write_text(svg,encoding='utf-8')

PLOTLY_SHA256 = '36e6a865de8830e2cb572b6787176ab28b597672493663e1043ab8f22d8192d1'

def time_grid(index, step_seconds: int) -> dict:
    if len(index) > 1:
        differences = (index[1:] - index[:-1]).total_seconds()
        if not (differences == step_seconds).all():
            raise ValueError('Compact time encoding requires a regular grid')
    return {'start': index[0].strftime('%Y-%m-%dT%H:%M:%S'),
            'step_seconds': step_seconds, 'count': len(index)}

def pack_flags(values: list[bool] | None) -> str | None:
    if values is None:
        return None
    packed = bytearray((len(values) + 7) // 8)
    for i, value in enumerate(values):
        if value:
            packed[i // 8] |= 1 << (i % 8)
    return base64.b64encode(packed).decode('ascii')

class AssetWriter:
    def __init__(self, destination: Path):
        self.destination = destination
        self.assets = destination / 'assets'
        self.assets.mkdir(parents=True, exist_ok=True)
        self.written: set[Path] = set()

    def bytes(self, name: str, data: bytes, extension: str) -> str:
        digest = hashlib.sha256(data).hexdigest()[:16]
        path = self.assets / f'{name}.{digest}.{extension}'
        path.write_bytes(data)
        self.written.add(path)
        return path.relative_to(self.destination).as_posix()

    def json(self, name: str, value) -> str:
        data = json.dumps(value, allow_nan=False, separators=(',', ':')).encode('utf-8')
        # mtime=0 keeps immutable asset URLs stable across identical exports.
        return self.bytes(name, gzip.compress(data, compresslevel=9, mtime=0), 'json.gz')

    def plotly(self, source: Path) -> str:
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != PLOTLY_SHA256:
            raise ValueError('Chart vendor checksum mismatch')
        return self.bytes('plotly-cartesian-3.6.0', data, 'min.js')

    def finish(self) -> None:
        # This directory is generated output. Remove obsolete generated files only.
        for path in self.assets.iterdir():
            if path.is_file() and path not in self.written:
                path.unlink()
        # Migrate the former uncompressed export, whose content is now in assets/.
        for directory in ['sensors', 'events']:
            old = self.destination / directory
            if old.exists():
                for path in old.glob('*.json'):
                    path.unlink()
                if not any(old.iterdir()):
                    old.rmdir()
        for filename in ['data.json', 'plotly.min.js']:
            (self.destination / filename).unlink(missing_ok=True)
