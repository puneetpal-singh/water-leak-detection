import base64
import gzip
import json
import numpy as np
import pandas as pd
import pytest
from waterleak.web_assets import time_grid,pack_flags,AssetWriter

def test_time_grid_preserves_wall_clock_across_dst_dates():
    index = pd.date_range('2019-03-30 23:00',periods=10,freq='1h')
    clock = time_grid(index,3600)
    rebuilt = pd.date_range(clock['start'],periods=clock['count'],freq='1h')
    pd.testing.assert_index_equal(index,rebuilt)

def test_irregular_clock_cannot_be_silently_compacted():
    with pytest.raises(ValueError,match='regular'):
        time_grid(pd.to_datetime(['2019-01-01','2019-01-03']),86400)

def test_packed_flags_preserve_values_and_padding():
    values = [True,False,True,False,False,False,False,True,True,False]
    packed = np.frombuffer(base64.b64decode(pack_flags(values)),dtype=np.uint8)
    assert np.unpackbits(packed,bitorder='little')[:len(values)].tolist() == values
    assert pack_flags(None) is None

def test_identical_exports_keep_the_same_immutable_asset_url(tmp_path):
    writer = AssetWriter(tmp_path)
    first = writer.json('sensor',{'y':[1.125,None,2]})
    second = writer.json('sensor',{'y':[1.125,None,2]})
    assert first == second
    assert json.loads(gzip.decompress((tmp_path/first).read_bytes())) == {'y':[1.125,None,2]}
