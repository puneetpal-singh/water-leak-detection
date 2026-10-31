import numpy as np
import pandas as pd
from waterleak.models import fit_and_score

def test_future_data_cannot_refit_scales_or_change_historical_scores():
    rng = np.random.default_rng(42)
    index = pd.date_range('2018-01-01', periods=160, freq='15min')
    features = pd.DataFrame(rng.normal(size=(160, 6)), index=index,
        columns=[f'pressure:n{i}|residual' for i in range(6)])
    fit = pd.Series(np.arange(160) < 120, index=index)
    before, z_before, metadata_before = fit_and_score(features, fit, sample_limit=100)
    changed = features.copy()
    changed.iloc[140:] = 1000
    after, z_after, metadata_after = fit_and_score(changed, fit, sample_limit=100)
    pd.testing.assert_frame_equal(before.iloc[:140], after.iloc[:140])
    pd.testing.assert_frame_equal(z_before.iloc[:140], z_after.iloc[:140])
    assert metadata_before['training_feature_medians'] == metadata_after['training_feature_medians']
