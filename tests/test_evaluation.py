import pandas as pd
from waterleak.evaluation import alarm_episodes, match_events, evaluate

def test_alarm_confirmation_is_not_backdated_and_clearance_prevents_chatter():
    index = pd.date_range('2019-01-01', periods=11, freq='15min')
    active, episodes = alarm_episodes(pd.Series([1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 1], index=index))
    assert episodes.iloc[0].start == index[3]
    assert episodes.iloc[0].end == index[9]
    assert not active.iloc[2] and active.iloc[3]
    assert len(episodes) == 1

def test_preexisting_alarm_does_not_count_and_one_alarm_cannot_detect_two_leaks():
    events = pd.DataFrame({'pipe': ['p1', 'p2'], 'type': ['abrupt'] * 2,
        'start': pd.to_datetime(['2019-01-02', '2019-01-02 01:00'], format='mixed'),
        'end': pd.to_datetime(['2019-01-05'] * 2)})
    alarms = pd.DataFrame({'start': pd.to_datetime(['2019-01-01', '2019-01-02 02:00'], format='mixed'),
                           'end': pd.to_datetime(['2019-01-03'] * 2)})
    table, false = match_events(alarms, events, pd.Timestamp('2019-01-01'), pd.Timestamp('2020-01-01'))
    assert table.detected_at.notna().sum() == 1
    assert false == 1
    assert table.iloc[0].delay_hours == 2

def test_missing_samples_cannot_confirm_or_clear_an_alarm():
    index = pd.date_range('2019-01-01', periods=15, freq='15min')
    values = pd.Series([1, 1, pd.NA, 1, 1, 1, 1, 0, 0, pd.NA, 0, 0, 0, 0, 0], index=index, dtype='boolean')
    active, episodes = alarm_episodes(values)
    assert episodes.iloc[0].start == index[6]
    assert active.iloc[9]  # Missing is unknown, not proof of recovery.
    assert episodes.iloc[0].end == index[13]

def test_timestamp_gap_interrupts_confirmation_run():
    index = pd.to_datetime(['2019-01-01 00:00', '2019-01-01 00:15', '2019-01-01 01:00', '2019-01-01 01:15'])
    _, episodes = alarm_episodes(pd.Series(True, index=index))
    assert episodes.empty

def test_matching_is_chronological_even_when_input_events_are_unsorted():
    events = pd.DataFrame({'pipe': ['later', 'earlier'], 'type': ['abrupt'] * 2,
        'start': pd.to_datetime(['2019-01-02 01:00', '2019-01-02 00:00']),
        'end': pd.to_datetime(['2019-01-05'] * 2)})
    alarms = pd.DataFrame({'start': pd.to_datetime(['2019-01-02 02:00']), 'end': pd.to_datetime(['2019-01-03'])})
    table, _ = match_events(alarms, events, pd.Timestamp('2019-01-01'), pd.Timestamp('2020-01-01'))
    assert table.iloc[0]['pipe'] == 'earlier' and pd.notna(table.iloc[0].detected_at)
    assert pd.isna(table.iloc[1].detected_at)

def test_empty_events_and_alarm_period_is_valid():
    index = pd.date_range('2019-01-01', periods=8, freq='15min')
    scores = pd.Series(1., index=index)
    active, episodes = alarm_episodes(pd.Series(False, index=index))
    events = pd.DataFrame({'pipe': [], 'type': [], 'start': pd.Series([], dtype='datetime64[ns]'),
                           'end': pd.Series([], dtype='datetime64[ns]')})
    metrics, table = evaluate(scores, active, episodes, events, '2019-01-01', '2020-01-01')
    assert table.empty and metrics['false_alarms'] == 0 and metrics['pr_auc_ap'] is None
