import pandas as pd
from waterleak.evaluation import alarm_episodes, match_events

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
