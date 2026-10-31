"""Focused EDA tables and engineering comparisons, independent of the models."""
from pathlib import Path
import pandas as pd
import numpy as np

def analyse(telemetry: pd.DataFrame, truth: pd.DataFrame, events: pd.DataFrame,
            results: Path) -> dict:
    stats = telemetry.describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
    stats['missing_pct'] = telemetry.isna().mean() * 100
    stats['max_abs_change_5min'] = telemetry.diff().abs().max()
    stats.to_csv(results / 'sensor_statistics.csv', index_label='sensor')
    focus = [c for c in telemetry if c.startswith(('pressure:', 'flow:', 'level:'))]
    telemetry[focus].corr().to_csv(results / 'correlations.csv', index_label='sensor')
    hourly = telemetry.groupby(telemetry.index.hour).mean()
    hourly.to_csv(results / 'hourly_profiles.csv', index_label='hour')
    telemetry.groupby(telemetry.index.dayofweek).mean().to_csv(results / 'weekday_profiles.csv', index_label='weekday')
    telemetry.groupby(telemetry.index.dayofweek >= 5).mean().to_csv(results / 'weekend_profiles.csv', index_label='weekend')
    telemetry.resample('D').mean().to_csv(results / 'daily_means.csv')
    telemetry.resample('W').mean().to_csv(results / 'weekly_means.csv')
    telemetry.resample('MS').mean().to_csv(results / 'monthly_means.csv')
    # Retrospective event comparison uses local before/after windows, not a causal
    # estimate of a single pipe's effect. Concurrent leaks and demand can confound it.
    comparisons = []
    for e in events.itertuples():
        before = telemetry.loc[(telemetry.index >= e.start - pd.Timedelta(hours=48)) & (telemetry.index < e.start), focus]
        during = telemetry.loc[(telemetry.index >= e.start) & (telemetry.index < e.start + pd.Timedelta(hours=72)), focus]
        recovery = telemetry.loc[(telemetry.index > e.end) & (telemetry.index <= e.end + pd.Timedelta(hours=48)), focus]
        for sensor in focus:
            pre, post = before[sensor].median(), during[sensor].median()
            comparisons.append({'pipe': e.pipe, 'sensor': sensor, 'type': e.type,
                'pre_48h_median': pre, 'onset_72h_median': post, 'change': post - pre,
                'change_in_pre_std': (post - pre) / max(before[sensor].std(), .01),
                'recovery_48h_median': recovery[sensor].median() if len(recovery) else np.nan,
                'recovery_available': len(recovery) > 0})
    comparison = pd.DataFrame(comparisons)
    comparison.to_csv(results / 'event_sensor_changes.csv', index=False)
    pressure = telemetry.filter(like='pressure:')
    flows = telemetry.filter(like='flow:')
    flow_swing = hourly[flows.columns].max() - hourly[flows.columns].min()
    insights = {
        'rows': len(telemetry), 'channels': len(telemetry.columns),
        'measurement_cells': int(telemetry.size),
        'start': str(telemetry.index.min()), 'end': str(telemetry.index.max()),
        'pressure_median_m': float(pressure.stack().median()),
        'strongest_hourly_flow': flow_swing.idxmax(),
        'strongest_hourly_flow_swing_m3h': float(flow_swing.max()),
        'flow_peak_hours': {c: int(hourly[c].idxmax()) for c in flows},
        'flow_trough_hours': {c: int(hourly[c].idxmin()) for c in flows},
        '2018_leak_presence_fraction': float(truth.loc['2018'].gt(0).any(axis=1).mean()),
        '2019_leak_presence_fraction': float(truth.loc['2019'].gt(0).any(axis=1).mean()),
        'events_2018': int(events.start.dt.year.eq(2018).sum()),
        'events_2019': int(events.start.dt.year.eq(2019).sum()),
        'pressure_flow_correlation_n1_p227': float(telemetry['pressure:n1'].corr(telemetry['flow:p227']))}
    return insights
