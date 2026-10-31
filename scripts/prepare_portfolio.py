"""Copy only the optimized static demo into a React/Vite portfolio's public dir."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]

def prepare(portfolio: Path) -> Path:
    portfolio = portfolio.resolve(strict=True)
    if not (portfolio/'package.json').is_file():
        raise ValueError('Expected a portfolio repository with package.json')
    source = ROOT/'dashboard/web/dist'
    destination = portfolio/'public/demos/water-network'
    # Do not write through symlinks into another project or unrelated directory.
    if destination.resolve() != destination or not destination.is_relative_to(portfolio):
        raise ValueError('Unexpected portfolio destination')
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if manifest['format_version'] != 1:
        raise ValueError('Unsupported browser asset format')
    destination.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,destination,dirs_exist_ok=True)
    current = {p.relative_to(source) for p in source.rglob('*') if p.is_file()}
    assets = destination/'assets'
    for path in assets.iterdir():
        if path.is_file() and path.relative_to(destination) not in current:
            path.unlink()
    index = destination/'index.html'
    text = index.read_text(encoding='utf-8')
    text = text.replace('<header><span>Water distribution / L-Town</span>',
                        '<header><a href="/projects">← Portfolio projects</a>')
    index.write_text(text,encoding='utf-8')
    provenance = {'source_repository':'https://github.com/puneetpal-singh/water-leak-detection',
        'manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
        'entry':'/demos/water-network/index.html','asset_format':1}
    (destination/'source.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    print(f'Prepared static portfolio demo: {destination}')
    return destination

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('portfolio_path',type=Path)
    prepare(parser.parse_args().portfolio_path)
