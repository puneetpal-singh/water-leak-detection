import numpy as np
import pandas as pd
import pytest
from waterleak.data import audit_and_clean

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
