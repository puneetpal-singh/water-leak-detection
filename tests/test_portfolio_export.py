import importlib.util
import json
from pathlib import Path

def test_copy_preserves_unicode_and_only_adds_a_portfolio_back_link(tmp_path):
    script=Path(__file__).resolve().parents[1]/'scripts/prepare_portfolio.py'
    spec=importlib.util.spec_from_file_location('prepare_portfolio',script)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source_root=tmp_path/'source'
    source=source_root/'dashboard/web/dist'
    source.mkdir(parents=True)
    (source/'assets').mkdir()
    original='<html><header><span>Water distribution / L-Town</span>2018–2019 · SCADA</header></html>'
    (source/'index.html').write_text(original,encoding='utf-8')
    (source/'manifest.json').write_text(json.dumps({'format_version':1}),encoding='utf-8')
    (source/'assets/payload.json.gz').write_bytes(b'asset')
    portfolio=tmp_path/'portfolio'
    portfolio.mkdir()
    (portfolio/'package.json').write_text('{}')
    module.ROOT=source_root
    output=module.prepare(portfolio)
    copied=(output/'index.html').read_text(encoding='utf-8')
    assert '2018–2019 · SCADA' in copied and '← Portfolio projects' in copied
    assert (source/'index.html').read_text(encoding='utf-8')==original
    assert (output/'assets/payload.json.gz').read_bytes()==b'asset'
