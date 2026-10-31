import numpy as np
import pandas as pd
import pytest
from waterleak.data import audit_and_clean, verify_sources

def test_missing_grid_is_filled_only_from_past_with_limit():
    index = pd.to_datetime(['2018-01-01 00:00', '2018-01-01 00:05', '2018-01-01 00:30'])
    x = pd.DataFrame({'a': [np.nan, 5, 9]}, index=index)
    clean, audit = audit_and_clean(x, 'pressure')
    assert np.isnan(clean.iloc[0, 0])
    assert clean.iloc[2:4, 0].tolist() == [5, 5]
    assert np.isnan(clean.iloc[4, 0])
    assert audit['missing_timestamps'] == 4

def test_conflicting_duplicate_is_rejected():
    x = pd.DataFrame({'a': [1, 2]}, index=pd.to_datetime(['2018-01-01'] * 2))
    with pytest.raises(ValueError, match='Conflicting'):
        audit_and_clean(x, 'flow')

def test_signed_flow_retained_negative_demand_replaced():
    x = pd.DataFrame({'a': [-1, 2]}, index=pd.date_range('2018-01-01', periods=2, freq='5min'))
    assert audit_and_clean(x, 'flow')[0].iloc[0, 0] == -1
    assert np.isnan(audit_and_clean(x, 'demand')[0].iloc[0, 0])

def test_shifted_grid_is_not_accepted_as_five_minute_sampling():
    x = pd.DataFrame({'a': [1, 2]}, index=pd.date_range('2018-01-01 00:02', periods=2, freq='5min'))
    with pytest.raises(ValueError, match='Off-grid'):
        audit_and_clean(x, 'pressure')

def test_identical_duplicates_with_missing_cells_are_deduplicated():
    x = pd.DataFrame({'a': [np.nan, np.nan], 'b': [2, 2]}, index=pd.to_datetime(['2018-01-01'] * 2))
    clean, audit = audit_and_clean(x, 'pressure')
    assert len(clean) == 1 and audit['duplicate_timestamps'] == 1

def test_empty_measurements_are_rejected():
    with pytest.raises(ValueError, match='nonempty'):
        audit_and_clean(pd.DataFrame(), 'pressure')

def test_modified_raw_file_is_rejected(tmp_path):
    import hashlib
    import json
    path = tmp_path / 'source.csv'
    path.write_bytes(b'original')
    checksum = 'md5:' + hashlib.md5(path.read_bytes()).hexdigest()
    (tmp_path / 'zenodo_record.json').write_text(json.dumps({'files': [{'key': path.name, 'checksum': checksum}]}))
    assert verify_sources(tmp_path) == {path.name: checksum}
    path.write_bytes(b'modified')
    with pytest.raises(ValueError, match='checksum mismatch'):
        verify_sources(tmp_path)
