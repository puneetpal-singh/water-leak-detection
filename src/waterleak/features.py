"""Causal features: every row uses only measurements available by its timestamp."""
import numpy as np
import pandas as pd

def aggregate(telemetry: pd.DataFrame, frequency: str = '15min') -> pd.DataFrame:
    """Right label completed bins. A 00:15 row contains 00:00, 00:05, 00:10."""
    duration = pd.Timedelta(frequency)
    if duration < pd.Timedelta('5min') or duration % pd.Timedelta('5min'):
        raise ValueError('Aggregation frequency must be a positive multiple of 5 minutes')
    bins = telemetry.resample(frequency, closed='left', label='right')
    expected = int(pd.Timedelta(frequency) / pd.Timedelta('5min'))
    return bins.mean().where(bins.count() >= expected)

def causal_features(measurements: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """15-minute inputs; trailing daily baselines adapt to existing background leaks.

    All features include the most recently completed measurement bin. No centered
    windows, backward fill, future demand, or retrospective labels are used.
    """
    index = measurements.index
    if not isinstance(index, pd.DatetimeIndex) or not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError('Features require a sorted, unique DatetimeIndex')
    if len(index) > 1 and not (index.to_series().diff().dropna() == pd.Timedelta('15min')).all():
        raise ValueError('Features require a regular 15-minute grid; resample first')
    x = measurements[[c for c in measurements if c.startswith(('pressure:', 'flow:', 'level:'))]]
    # Same quarter-hour on the preceding seven days; excludes today's observation.
    baseline = pd.DataFrame(index=x.index, columns=x.columns, dtype=float)
    for column in x:
        days = pd.concat([x[column].shift(96 * day) for day in range(1, 8)], axis=1)
        baseline[column] = days.median(axis=1).where(days.notna().sum(axis=1) >= 5)
    residual = x - baseline
    blocks = {
        'residual': residual,
        'residual_mean_1h': residual.rolling(4, min_periods=4).mean(),
        'difference_1h': x.diff(4),
        'std_1h': x.rolling(4, min_periods=4).std(),
        'range_1h': x.rolling(4, min_periods=4).max() - x.rolling(4, min_periods=4).min(),
        'residual_lag_1h': residual.shift(4),
        'weekly_difference': x - x.shift(672),
    }
    features = pd.concat([v.rename(columns=lambda c: f'{c}|{k}') for k, v in blocks.items()], axis=1)
    # n1 and n4 are real pressure locations in the same AMR area. This is a
    # pressure contrast, not a claimed adjacent-pipe gradient.
    if {'pressure:n1', 'pressure:n4'}.issubset(x.columns):
        features['pressure:n1-n4|contrast_change_1h'] = (x['pressure:n1'] - x['pressure:n4']).diff(4)
    # p227 and p235 are distinct metered links; ratio is descriptive, not mass balance.
    if {'flow:p227', 'flow:p235'}.issubset(x.columns):
        ratio = x['flow:p227'] / x['flow:p235'].where(x['flow:p235'].abs() > 1)
        features['flow:p227-p235|ratio_change_1h'] = ratio.diff(4)
    return features.replace([np.inf, -np.inf], np.nan), residual

def stable_training_mask(index: pd.DatetimeIndex, events: pd.DataFrame,
                         end: str, exclusion_hours: int = 168) -> pd.Series:
    """Retrospectively select stable 2018 operating states, not leak-free states."""
    mask = pd.Series(index < pd.Timestamp(end), index=index)
    for event in events.itertuples():
        # Only historical labels available before the training cutoff may select rows.
        if event.start < pd.Timestamp(end):
            delta = pd.Timedelta(hours=exclusion_hours)
            mask &= ~((index >= event.start - delta) & (index <= event.start + delta))
        if event.end < pd.Timestamp(end):
            delta = pd.Timedelta(hours=72)
            mask &= ~((index >= event.end - delta) & (index <= event.end + delta))
    return mask
