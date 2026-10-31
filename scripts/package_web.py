"""Create a small drop-in portfolio demo archive, excluding research artifacts."""
from pathlib import Path
import argparse
import zipfile

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('output',type=Path)
output=parser.parse_args().output.resolve()
if output.is_relative_to(root/'dashboard/web/dist'):
    raise ValueError('Archive must be outside the static asset directory')
output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for path in (root/'dashboard/web/dist').rglob('*'):
        if path.is_file():
            archive.write(path,Path('water-network')/path.relative_to(root/'dashboard/web/dist'))
    archive.write(root/'docs/vercel.md','INSTALL.md')
print(f'Created {output}: {output.stat().st_size:,} bytes')
