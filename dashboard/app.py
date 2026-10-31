"""Local Streamlit investigation workbench using full-resolution measurements."""
from pathlib import Path
import json
import sys
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waterleak.data import read_events, read_topology

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title='L-Town | Water network analytics', layout='wide')
st.markdown('''<style>
    .stApp {background:#fafafa} h1,h2,h3 {font-weight:500!important}
    [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums}
    </style>''', unsafe_allow_html=True)

@st.cache_data
def load():
    processed, results = ROOT / 'data/processed', ROOT / 'results'
    return {
        'telemetry': pd.read_parquet(processed / 'telemetry.parquet'),
        'measurements': pd.read_parquet(processed / 'model_measurements.parquet'),
        'scores': pd.read_parquet(processed / 'scores.parquet'),
        'activity': pd.read_parquet(processed / 'activity.parquet'),
        'sensor_z': pd.read_parquet(processed / 'sensor_z.parquet'),
        'events': read_events(ROOT / 'data/raw'),
        'metrics': pd.read_csv(results / 'model_comparison.csv'),
        'detections': pd.read_csv(results / 'event_detections.csv', parse_dates=['start', 'end', 'detected_at']),
        'experiment': json.loads((results / 'experiment.json').read_text()),
        'insights': json.loads((results / 'insights.json').read_text()),
        'topology': read_topology(ROOT / 'data/raw/L-TOWN.inp')}

def chart(fig, ylabel=None, height=380):
    fig.update_layout(template='plotly_white', height=height, margin=dict(l=32,r=16,t=32,b=32),
                      colorway=['#087782','#a66a17','#69737b','#ac493b'],
                      hovermode='x unified', paper_bgcolor='#fafafa',
                      font=dict(family='Segoe UI, sans-serif'), legend=dict(orientation='h',y=1.12))
    if ylabel:
        fig.update_yaxes(title=ylabel)
    st.plotly_chart(fig, width='stretch')

def metrics_table(frame):
    columns = ['method','precision','recall','f1','pr_auc_ap','leaks_detected','leaks_total',
               'false_alarms','false_alarms_per_week','mean_delay_hours','shift_control_mean_recall']
    st.dataframe(frame[columns], hide_index=True, width='stretch')

try:
    d = load()
except FileNotFoundError:
    st.info('Run python scripts/download_data.py, python scripts/inspect_data.py and python scripts/run_pipeline.py first.')
    st.stop()

st.sidebar.title('L-Town')
st.sidebar.caption('Water network analytics · BattLeDIM')
page = st.sidebar.radio('Analysis view', ['Overview','Operating patterns','Sensor explorer','Leak event explorer',
                                         'Model comparison','Network & relationships'])
st.sidebar.caption('Retrospective study · simulated telemetry')
st.sidebar.markdown('[Source & methodology](https://github.com/puneetpal-singh/water-leak-detection)')
x, events, scores = d['telemetry'], d['events'], d['scores']

if page == 'Overview':
    st.title('Water network leak detection')
    st.write('Explore real BattLeDIM measurements, causal features and new-onset alarms on a chronological holdout.')
    for col, label, value in zip(st.columns(4), ['Measurement channels','Five-minute timestamps','New 2019 onsets','Missing values'],
                                 [119, len(x), 19, int(x.isna().sum().sum())]):
        col.metric(label, f'{value:,}')
    st.warning('Evaluation concerns new onsets within 72 hours. Persistent leaks make the entire 2019 year leak-positive. High recall can coexist with unreliable alarms.')
    st.subheader('Measured results · 2019 holdout')
    metrics_table(d['metrics'])
    st.subheader('Engineering insights')
    st.write(f"The largest hourly flow swing is {d['insights']['strongest_hourly_flow_swing_m3h']:.1f} m³/h at flow:p235. Both DMA flow series peak around 19:00 and reach their minimum hourly mean around 04:00.")
    st.write(f"Pressure n1 and flow p227 have a Pearson correlation of {d['insights']['pressure_flow_correlation_n1_p227']:.2f}. This association mixes demand, operating changes and leak effects.")
    st.write('The 72-hour window and frequent alarms inflate event recall. Compare against the timing-shift control before drawing conclusions. The models are not deployment-ready.')
    with st.expander('Experiment and limitations'):
        st.markdown((ROOT / 'docs/methodology.md').read_text())

elif page == 'Operating patterns':
    st.title('Operating patterns')
    sensor = st.selectbox('Sensor', x.columns, index=list(x).index('flow:p227'))
    profiles = x[sensor].groupby(x.index.hour).agg(['mean','median','std']).reset_index(names='hour')
    chart(px.line(profiles, x='hour', y=['mean','median'], title='How does this sensor change through the day?'))
    a,b = st.columns(2)
    with a:
        weekly = x[sensor].resample('W').mean().reset_index()
        chart(px.line(weekly, x='timestamp', y=sensor, title='Weekly mean across both years'))
    with b:
        sample = x[[sensor]].copy()
        sample['day_type'] = sample.index.dayofweek.map(lambda day:'Weekend' if day>=5 else 'Weekday')
        # Hour-of-day averages avoid drawing hundreds of thousands of box points.
        sample['hour'] = sample.index.hour
        grouped=sample.groupby(['day_type','hour'])[sensor].mean().reset_index()
        chart(px.line(grouped, x='hour',y=sensor,color='day_type',title='Weekday versus weekend hourly means'))
    st.caption('Whole-record EDA is descriptive only. It is not used to fit the detector or select thresholds.')
    st.dataframe(pd.read_csv(ROOT/'results/sensor_statistics.csv').query('sensor == @sensor'), hide_index=True)

elif page == 'Sensor explorer':
    st.title('Sensor explorer')
    c1,c2,c3=st.columns([2,2,1])
    sensor=c1.selectbox('Sensor',x.columns)
    date_range=c2.date_input('Date range',value=(pd.Timestamp('2019-01-01').date(),pd.Timestamp('2019-01-15').date()),
                            min_value=x.index.min().date(),max_value=x.index.max().date())
    window=c3.selectbox('Trailing window (hours)',[1,6,24,168],index=1)
    if len(date_range)!=2:
        st.info('Select a start and end date.');st.stop()
    values=x[sensor].loc[str(date_range[0]):str(date_range[1])]
    if values.empty:
        st.info('No observations in this range.');st.stop()
    past=x[sensor].rolling(window*12,min_periods=window*12)
    mean=past.mean().reindex(values.index);std=past.std().reindex(values.index)
    fig=go.Figure([go.Scatter(x=values.index,y=values,name='Five-minute measurement',line=dict(width=1,color='#a3afb2')),
        go.Scatter(x=mean.index,y=mean,name='Trailing mean',line=dict(width=2,color='#087782')),
        go.Scatter(x=mean.index,y=mean+std,name='Mean + 1 std',line=dict(width=0),showlegend=False),
        go.Scatter(x=mean.index,y=mean-std,name='±1 trailing std',line=dict(width=0),fill='tonexty',fillcolor='rgba(8,119,130,.12)')])
    if sensor in d['sensor_z']:
        z=d['sensor_z'][sensor].reindex(values.index).dropna()
        abnormal=z[z.abs()>2.5]
        fig.add_trace(go.Scatter(x=abnormal.index,y=values.reindex(abnormal.index),name='Residual departure |z| > 2.5',
                                mode='markers',marker=dict(size=4,color='#a66a17')))
    chart(fig)
    c1,c2=st.columns(2)
    with c1:chart(px.histogram(values.to_frame(),x=sensor,nbins=50,title='Selected measurements'))
    with c2:
        change=values.diff().dropna()/5
        chart(go.Figure(go.Scatter(x=change.index,y=change,name='Rate of change per minute')), 'Sensor units / min')
    st.dataframe(values.describe(percentiles=[.01,.05,.5,.95,.99]).to_frame('value'))
    st.caption('Residual departures are per-sensor reference deviations, not confirmed leaks. 2018 overlays are retrospective fitting diagnostics; evaluation concerns 2019. Demands have no detector attribution in this experiment.')

elif page == 'Leak event explorer':
    st.title('Leak event explorer')
    test=events[events.start.dt.year==2019]
    c1,c2=st.columns(2)
    pipe=c1.selectbox('Test-year pipe',test['pipe'])
    method=c2.selectbox('Method',scores.columns,index=list(scores).index('PCA reconstruction'))
    event=test[test['pipe']==pipe].iloc[0]
    detection=d['detections'][(d['detections']['pipe']==pipe)&(d['detections'].method==method)].iloc[0]
    st.write(f"{event['type'].capitalize()} onset: {event.start} · reported end: {event.end}")
    st.metric('Alarm delay',f'{detection.delay_hours:.2f} hours' if pd.notna(detection.delay_hours) else 'Missed within 72 hours')
    if pd.notna(detection.detected_at):
        st.write(f'Confirmation: {detection.detected_at}')
        st.write(f'Sensor residual attribution: {detection.signed_residual_z}')
    a,b=st.columns(2)
    pressure=a.selectbox('Pressure sensor',[c for c in x if c.startswith('pressure:')])
    flow=b.selectbox('Flow sensor',[c for c in x if c.startswith('flow:')])
    start,end=event.start-pd.Timedelta(hours=24),event.start+pd.Timedelta(hours=96)
    window=d['measurements'].loc[start:end]
    for sensor,unit in [(pressure,'Pressure (m)'),(flow,'Flow (m³/h)'),(method,'Anomaly score')]:
        values=scores[method].reindex(window.index) if sensor==method else window[sensor]
        fig=go.Figure(go.Scatter(x=values.index,y=values,name=sensor))
        fig.add_vline(x=event.start.timestamp()*1000,line_color='#a66a17',line_dash='dot')
        if pd.notna(detection.detected_at):
            fig.add_vline(x=detection.detected_at.timestamp()*1000,line_color='#333b42',line_dash='dash')
        if sensor==method:
            fig.add_hline(y=d['experiment']['thresholds'][method]['threshold'],line_color='#69737b',line_dash='dash')
        chart(fig,unit)
    st.caption('Amber = known onset; dark dash = matched confirmation. Four consecutive exceedances and two abnormal sensors are required. Attributions are signed sensor residual z-scores, not ML feature importances.')

elif page == 'Model comparison':
    st.title('Model comparison')
    st.write('2019 test year · new-onset task · frozen thresholds')
    metrics_table(d['metrics'])
    curves = pd.read_csv(ROOT/'results/precision_recall_curves.csv')
    fig = px.line(curves, x='recall', y='precision', color='method', title='Precision–recall trade-off · raw scores')
    fig.add_hline(y=float(d['metrics'].positive_fraction.iloc[0]), line_dash='dash', line_color='#69737b')
    fig.update_xaxes(range=[0,1]); fig.update_yaxes(range=[0,1])
    chart(fig)
    a,b=st.columns(2)
    with a:chart(px.bar(d['metrics'],x='method',y='false_alarms',title='Unmatched new alarm starts'))
    with b:
        chart(px.bar(d['metrics'].melt(id_vars='method',value_vars=['event_recall','shift_control_mean_recall']),
                     x='method',y='value',color='variable',barmode='group',title='Recall and timing-shift control'))
    chart(px.box(d['detections'].dropna(subset=['delay_hours']),x='method',y='delay_hours',points='all',
                 title='Detection delay distribution · detected events only'))
    st.subheader('Every known test-year event')
    st.dataframe(d['detections'],hide_index=True,width='stretch')
    timeline_method = st.selectbox('Timeline method', scores.columns, index=list(scores).index('PCA reconstruction'))
    known = events[events.start.dt.year.eq(2019)]
    detected = d['detections'][d['detections'].method.eq(timeline_method)]
    matched = detected.dropna(subset=['detected_at'])
    missed = detected[detected.detected_at.isna()]
    fig = go.Figure([
        go.Scatter(x=known.start, y=known['pipe'], mode='markers', name='Known onset', marker=dict(symbol='line-ns',size=14,color='#a66a17')),
        go.Scatter(x=matched.detected_at,y=matched['pipe'],mode='markers',name='Matched confirmation',marker=dict(size=8,color='#087782')),
        go.Scatter(x=missed.start+pd.Timedelta(hours=72),y=missed['pipe'],mode='markers',name='Missed within 72h',marker=dict(symbol='x',size=8,color='#ac493b'))])
    fig.update_yaxes(categoryorder='array',categoryarray=list(reversed(known['pipe'].tolist())))
    chart(fig,height=600)
    st.caption('Protocol v2 follows a correctness review. The 2019 benchmark has been inspected; threshold selection remains entirely in 2018.')
    with st.expander('Fixed-threshold horizon sensitivity and validation candidates'):
        st.dataframe(pd.read_csv(ROOT/'results/horizon_sensitivity.csv'),hide_index=True)
        st.dataframe(pd.read_csv(ROOT/'results/validation_calibration.csv'),hide_index=True)

else:
    st.title('Network & sensor relationships')
    topology=d['topology'];nodes=topology['nodes'];xx=[];yy=[]
    for edge in topology['edges']:
        if edge['from'] in nodes and edge['to'] in nodes:
            xx.extend([nodes[edge['from']][0],nodes[edge['to']][0],None])
            yy.extend([nodes[edge['from']][1],nodes[edge['to']][1],None])
    pressure=[s.split(':')[1] for s in x if s.startswith('pressure:') and s.split(':')[1] in nodes]
    fig=go.Figure([go.Scatter(x=xx,y=yy,mode='lines',line=dict(width=1,color='#c3cbcf'),hoverinfo='skip',name='Nominal pipes'),
        go.Scatter(x=[nodes[s][0] for s in pressure],y=[nodes[s][1] for s in pressure],text=pressure,
                   mode='markers',marker=dict(size=7,color='#087782'),name='Pressure locations')])
    fig.update_yaxes(scaleanchor='x',scaleratio=1,visible=False);fig.update_xaxes(visible=False)
    chart(fig,height=600)
    st.caption('Nominal L-TOWN.inp coordinates. This is a schematic, not latitude and longitude. No hidden generation parameters or fabricated topology are used.')
    correlation=pd.read_csv(ROOT/'results/correlations.csv',index_col=0)
    chart(px.imshow(correlation,zmin=-1,zmax=1,color_continuous_scale='BrBG',title='Pressure, flow and level correlations'),height=700)

st.caption('Dataset: BattLeDIM (CC BY 4.0). Interface guided by /unslop, Damir Sokolovsky (CC BY 4.0).')
