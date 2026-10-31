import numpy as np
import pandas as pd
from waterleak.features import aggregate, causal_features, stable_training_mask

def test_features_invariant_to_future_measurement_changes():
    x = pd.DataFrame({'pressure:n1': np.sin(np.arange(1000) / 20)},
                     index=pd.date_range('2018-01-01', periods=1000, freq='15min'))
    before, _ = causal_features(x)
    changed = x.copy()
    changed.iloc[850:] = 10000
    after, _ = causal_features(changed)
    pd.testing.assert_frame_equal(before.iloc[:850], after.iloc[:850])
    truncated, _ = causal_features(x.iloc[:850])
    pd.testing.assert_frame_equal(before.iloc[:850], truncated)

def test_aggregation_timestamp_is_availability_time():
    x = pd.DataFrame({'pressure:n1': [1, 2, 3, 100]},
                     index=pd.date_range('2018-01-01', periods=4, freq='5min'))
    y = aggregate(x)
    assert y.index[0] == pd.Timestamp('2018-01-01 00:15')
    assert y.iloc[0, 0] == 2
    assert pd.isna(y.iloc[1, 0])  # A partial bin must not hide missing data.

def test_test_labels_cannot_change_training_selection():
    index = pd.date_range('2018-01-01', '2018-09-30', freq='1D')
    events = pd.DataFrame({'start': pd.to_datetime(['2019-01-01']), 'end': pd.to_datetime(['2019-02-01'])})
    assert stable_training_mask(index, events, '2018-10-01').all()
