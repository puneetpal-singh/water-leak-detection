"""Streaming alarm state and one-to-one onset matching, independent of models."""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_fscore_support

def alarm_episodes(exceedance: pd.Series, persistence: int = 4,
                   clearance: int = 4) -> tuple[pd.Series, pd.DataFrame]:
    """Emit on the fourth consecutive exceedance; clear after four normal bins.

    Detection is timestamped at confirmation, never backdated to the first sample.
    An episode still active at the split boundary remains one episode.
    """
    if persistence < 1 or clearance < 1:
        raise ValueError('Persistence and clearance must be positive')
    if not exceedance.index.is_unique or not exceedance.index.is_monotonic_increasing:
        raise ValueError('Alarm timestamps must be sorted and unique')
    active = np.zeros(len(exceedance), dtype=bool)
    episodes, run, clear, start = [], 0, 0, None
    previous = None
    for i, (time, value) in enumerate(exceedance.items()):
        if previous is not None and time - previous != pd.Timedelta('15min'):
            run, clear = 0, 0
        previous = time
        if pd.isna(value):
            # Missing telemetry proves neither anomaly nor recovery. Keep an
            # existing episode, but interrupt both confirmation and clearance runs.
            run, clear = 0, 0
            active[i] = start is not None
            continue
        if start is None:
            run = run + 1 if value else 0
            if run >= persistence:
                start, clear = time, 0
        else:
            clear = 0 if value else clear + 1
            if clear >= clearance:
                episodes.append({'start': start, 'end': time, 'right_censored': False})
                start, run, clear = None, 0, 0
        active[i] = start is not None
    if start is not None:
        episodes.append({'start': start, 'end': exceedance.index[-1], 'right_censored': True})
    return pd.Series(active, index=exceedance.index), pd.DataFrame(episodes, columns=['start', 'end', 'right_censored'])

def onset_labels(index: pd.DatetimeIndex, events: pd.DataFrame, hours: int = 72) -> pd.Series:
    """Positive means within the declared window after a new onset, not any leak."""
    y = pd.Series(False, index=index)
    for e in events.itertuples():
        y |= (index >= e.start) & (index <= min(e.end, e.start + pd.Timedelta(hours=hours)))
    return y

def match_events(episodes: pd.DataFrame, events: pd.DataFrame,
                 start: pd.Timestamp, end: pd.Timestamp, hours: int = 72) -> tuple[pd.DataFrame, int]:
    """One alarm can match at most one onset. Pre-onset alarms receive no credit."""
    alarms = episodes[(episodes.start >= start) & (episodes.start < end)].sort_values('start').reset_index(drop=True)
    eligible = events[(events.start >= start) & (events.start < end)].sort_values('start')
    used, rows = set(), []
    for event in eligible.itertuples():
        deadline = min(event.end, event.start + pd.Timedelta(hours=hours), end)
        candidates = alarms[(alarms.start >= event.start) & (alarms.start <= deadline)]
        candidates = candidates.loc[~candidates.index.isin(used)]
        detection = pd.NaT
        if len(candidates):
            alarm_id = candidates.start.idxmin()
            used.add(alarm_id)
            detection = candidates.loc[alarm_id, 'start']
        rows.append({'pipe': event.pipe, 'type': event.type, 'start': event.start, 'end': event.end,
                     'detected_at': detection,
                     'delay_hours': (detection - event.start).total_seconds() / 3600 if pd.notna(detection) else np.nan})
    columns = ['pipe', 'type', 'start', 'end', 'detected_at', 'delay_hours']
    return pd.DataFrame(rows, columns=columns), len(alarms) - len(used)

def evaluate(scores: pd.Series, active: pd.Series, episodes: pd.DataFrame,
             events: pd.DataFrame, start: str, end: str, hours: int = 72) -> tuple[dict, pd.DataFrame]:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    selection = (scores.index >= start) & (scores.index < end) & scores.notna()
    y = onset_labels(scores.index, events, hours)[selection]
    precision, recall, f1, _ = precision_recall_fscore_support(y, active[selection], average='binary', zero_division=0)
    table, false_alarms = match_events(episodes, events, start, end, hours)
    detected = int(table.detected_at.notna().sum()) if len(table) else 0
    event_precision = detected / (detected + false_alarms) if detected + false_alarms else 0
    event_recall = detected / len(table) if len(table) else 0
    metrics = {'precision': float(precision), 'recall': float(recall), 'f1': float(f1),
               'pr_auc_ap': float(average_precision_score(y, scores[selection])) if y.any() else None,
               'positive_fraction': float(y.mean()), 'point_count': int(selection.sum()),
               'leaks_detected': detected, 'leaks_total': len(table), 'missed_leaks': len(table) - detected,
               'event_precision': event_precision, 'event_recall': event_recall,
               'event_f1': 2 * event_precision * event_recall / (event_precision + event_recall) if event_precision + event_recall else 0,
               'false_alarms': false_alarms,
               'false_alarms_per_week': false_alarms / ((end - start).total_seconds() / 604800),
               'mean_delay_hours': float(table.delay_hours.mean()) if detected else None,
               'median_delay_hours': float(table.delay_hours.median()) if detected else None}
    return metrics, table

def circular_alarm_control(episodes: pd.DataFrame, events: pd.DataFrame,
                           seed: int = 42, repeats: int = 200, hours: int = 72) -> dict:
    """Shift test alarm starts around the year to expose chance window matches.

    This is a descriptive negative control, not a significance test. It preserves
    alarm count and relative spacing; annual nonstationarity limits interpretation.
    """
    start, end = pd.Timestamp('2019-01-01'), pd.Timestamp('2020-01-01')
    alarms = episodes[(episodes.start >= start) & (episodes.start < end)].copy()
    seconds = (alarms.start - start).dt.total_seconds().to_numpy()
    span = (end - start).total_seconds()
    rng, recalls = np.random.default_rng(seed), []
    for _ in range(repeats):
        shifted = alarms.copy()
        shifted['start'] = start + pd.to_timedelta((seconds + rng.uniform(0, span)) % span, unit='s')
        table, _ = match_events(shifted, events, start, end, hours)
        recalls.append(float(table.detected_at.notna().mean()))
    return {'shift_control_mean_recall': float(np.mean(recalls)),
            'shift_control_p05_recall': float(np.quantile(recalls, .05)),
            'shift_control_p95_recall': float(np.quantile(recalls, .95))}
