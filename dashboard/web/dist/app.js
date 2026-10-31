'use strict';
let DATA, routeVersion = 0;
const cache = new Map();
const $ = id => document.getElementById(id);
const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n, digits = 1) => n == null || !Number.isFinite(Number(n)) ? '—' : Number(n).toLocaleString('en-GB', {maximumFractionDigits:digits, minimumFractionDigits:digits});
const pct = n => `${fmt(n * 100)}%`;
const colours = ['#087782','#a66a17','#69737b','#ac493b','#4e6582'];
async function fetchJSON(path) {
  if (!cache.has(path)) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
    cache.set(path, await response.json());
  }
  return cache.get(path);
}
function plot(id, traces, options = {}) {
  return Plotly.react(id, traces, {
    margin:{l:56,r:16,t:24,b:48}, paper_bgcolor:'#ffffff', plot_bgcolor:'#ffffff',
    font:{family:'Segoe UI, Arial, sans-serif',size:12,color:'#515b63'},
    colorway:colours, hovermode:'x unified', autosize:true,
    xaxis:{gridcolor:'#edf0f1',zeroline:false,showline:true,linecolor:'#dfe3e5'},
    yaxis:{gridcolor:'#edf0f1',zeroline:false},
    legend:{orientation:'h',y:1.12,x:0}, ...options
  }, {responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']});
}
function line(x,y,name,extra={}) { return {x,y,name,mode:'lines',type:'scatter',line:{width:1.5},...extra}; }
function onsetShape(time) { return {type:'line',xref:'x',yref:'paper',x0:time,x1:time,y0:0,y1:1,line:{color:'#a66a17',width:1.5,dash:'dot'}}; }
function intro(title,copy,eyebrow='BattLeDIM engineering study') { return `<div class="intro"><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${copy}</p></div>`; }
function metric(label,value,note) { return `<div class="metric ${String(value).length>8?'long':''}"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`; }
function panel(title,copy,chart,id,cls='') { return `<div class="panel"><h2>${title}</h2><p>${copy}</p>${chart ? `<div id="${id}" class="chart ${cls}"></div>`:''}</div>`; }
function options(values,chosen) { return values.map(v=>`<option ${v===chosen?'selected':''} value="${esc(v)}">${esc(v)}</option>`).join(''); }
function sensorOptions(prefix,chosen) { return options(DATA.sensors.filter(s=>!prefix || s.id.startsWith(prefix)).map(s=>s.id),chosen); }
function bind(id,event,callback) { $(id).addEventListener(event,()=>Promise.resolve(callback()).catch(showError)); }
function showError(error) { $('status').style.display='block'; $('status').textContent=`Unable to display this view: ${error.message}`; }
function modelRows() { return DATA.metrics.map(m=>`<tr><td>${esc(m.method)}</td><td class="num">${fmt(m.precision,3)}</td><td class="num">${fmt(m.recall,3)}</td><td class="num">${fmt(m.f1,3)}</td><td class="num">${fmt(m.pr_auc_ap,3)}</td><td class="num">${m.leaks_detected}/${m.leaks_total}</td><td class="num">${m.false_alarms}</td><td class="num">${fmt(m.mean_delay_hours)} h</td></tr>`).join(''); }
const comparisonTable = () => `<div class="table-scroll"><table><thead><tr><th>Method</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th><th class="num">AP</th><th class="num">Events</th><th class="num">False alarms</th><th class="num">Mean delay</th></tr></thead><tbody>${modelRows()}</tbody></table></div>`;

async function overview(version) {
  const i=DATA.insights, m=DATA.metrics.find(m=>m.method==='PCA reconstruction');
  $('content').innerHTML=intro('Water network leak detection','Two years of pressure, flow and demand measurements. Explore operating patterns, inspect new-leak alarms, and see where the detectors fall short.')+
    `<div class="metrics">${metric('Measured channels','119','33 pressure · 3 flow · 1 level · 82 demand')}${metric('Source timestamps',fmt(i.rows,0),'1 Jan 2018 – 31 Dec 2019')}${metric('New test-year leaks','19','33 known onsets across both years')}${metric('Missing source values','0','Regular five-minute sampling')}</div>`+
    `<div class="notice">This study detects <strong>new onsets within 72 hours</strong>. Existing leaks continue throughout 2019. A high detection rate can coexist with poor alarm reliability.</div>`+
    `<div class="layout"><div>${panel('Pressure around a known onset','Pipe p523 · abrupt leak · 15 January 2019 at 23:00',true,'overview-chart')}<div class="panel"><h2>What the comparison shows</h2><p>PCA is shown here as one example, not a deployment recommendation. Its alarms need substantial improvement.</p><div class="metrics">${metric('PCA event recall',`${m.leaks_detected}/19`,'New alarm starts within 72 hours')}${metric('False onset alarms',fmt(m.false_alarms,0),`${fmt(m.false_alarms_per_week)} per week`)}${metric('Point average precision',fmt(m.pr_auc_ap,3),`No-skill reference ${fmt(m.positive_fraction,3)}`)}${metric('Mean confirmation delay',`${fmt(m.mean_delay_hours)} h`,'Detected events only')}</div><a href="#models">Inspect all five methods →</a></div></div>
    <div class="panel"><h2>Engineering observations</h2><div class="insight"><b>Demand has a daily rhythm</b><p>Both DMA flow series peak around 19:00 and reach their lowest hourly mean around 04:00, across the two-year record.</p></div><div class="insight"><b>Pressure and flow move together</b><p>Pressure n1 and flow p227 have a Pearson correlation of ${fmt(i.pressure_flow_correlation_n1_p227,2)}. This is an association, not a hydraulic diagnosis.</p></div><div class="insight"><b>Gradual leaks are difficult</b><p>The trailing daily reference adapts to persistent changes. It can absorb a slow leak along with seasonal variation.</p></div><div class="insight"><b>Alarm volume matters</b><p>Timing-shift controls reveal how many onsets frequent alarms could match by coincidence.</p></div><a class="page-link" href="#methods">Read assumptions & limits →</a></div></div>`;
  const event=DATA.events.find(e=>e.pipe==='p523'), window=await fetchJSON(event.file);
  if(version!==routeVersion) return;
  plot('overview-chart',[line(window.x,window.measurements['pressure:n1'],'Pressure n1')],{yaxis:{title:{text:'Pressure (m)'},gridcolor:'#edf0f1'},shapes:[onsetShape(event.start)],annotations:[{x:event.start,y:1.04,yref:'paper',text:'Known onset',showarrow:false,font:{color:'#a66a17',size:11}}]});
}

async function sensors() {
  $('content').innerHTML=intro('Sensor explorer','Inspect hourly averages from all 119 measurement channels. The local Streamlit app also exposes the original five-minute measurements.')+
    `<div class="controls"><label>Sensor<select id="sensor">${sensorOptions('', 'pressure:n1')}</select></label><label>From<input id="from" type="date" value="2019-01-01" min="2018-01-01" max="2019-12-31"></label><label>Through<input id="through" type="date" value="2019-02-01" min="2018-01-01" max="2019-12-31"></label><label>Rolling window<select id="rolling">${options(['6 hours','24 hours','168 hours'],'24 hours')}</select></label><button id="update">Update view</button></div><div id="sensor-stats" class="metrics"></div>`+
    panel('Measurements and trailing mean','Hourly means retain diurnal structure; peaks within an hour are smoothed.',true,'sensor-trace')+
    `<div class="split">${panel('Distribution','Selected date range',true,'sensor-hist','short')}${panel('Hour-of-day pattern','Selected range · source wall-clock hour',true,'sensor-profile','short')}</div>`;
  let request=0;
  async function update() {
    const own=++request, sensor=DATA.sensors.find(s=>s.id===$('sensor').value), file=await fetchJSON(sensor.file);
    if(own!==request || !$('sensor-trace')) return;
    const start=$('from').value, end=$('through').value;
    if(!start || !end || start>end) { $('sensor-stats').innerHTML='<p>Choose a valid date range with From before Through.</p>'; return; }
    const pairs=file.x.map((x,j)=>[x,file.y[j],file.abnormal?.[j]]).filter(([x,y])=>x.slice(0,10)>=start&&x.slice(0,10)<=end&&y!=null);
    if(!pairs.length) { $('sensor-stats').innerHTML='<p>No observations in the selected period.</p>'; return; }
    const x=pairs.map(p=>p[0]), y=pairs.map(p=>p[1]), count=parseInt($('rolling').value), rolling=[];
    let sum=0; y.forEach((v,j)=>{sum+=v;if(j>=count)sum-=y[j-count];rolling.push(j>=count-1?sum/count:null);});
    const mean=y.reduce((a,b)=>a+b,0)/y.length;
    $('sensor-stats').innerHTML=metric('Mean',fmt(mean,2),sensor.unit)+metric('Minimum',fmt(Math.min(...y),2),sensor.unit)+metric('Maximum',fmt(Math.max(...y),2),sensor.unit)+metric('Hourly observations',fmt(y.length,0),'Selected range');
    const markers=DATA.events.filter(e=>e.start.slice(0,10)>=start&&e.start.slice(0,10)<=end).map(e=>onsetShape(e.start));
    const departures=pairs.filter(p=>p[2]);
    plot('sensor-trace',[line(x,y,'Hourly measurement',{line:{color:'#9aa8ac',width:1}}),line(x,rolling,`Trailing ${count}h mean`,{line:{color:colours[0],width:2}}),{x:departures.map(p=>p[0]),y:departures.map(p=>p[1]),name:'Hour containing |residual z| > 2.5',type:'scatter',mode:'markers',marker:{size:4,color:colours[1]}}],{yaxis:{title:{text:sensor.unit},gridcolor:'#edf0f1'},shapes:markers});
    plot('sensor-hist',[{x:y,type:'histogram',nbinsx:40,marker:{color:colours[0]},name:'Hourly samples'}],{hovermode:'closest',xaxis:{title:{text:sensor.unit}},yaxis:{title:{text:'Count'},gridcolor:'#edf0f1'},showlegend:false});
    const groups=Array.from({length:24},()=>[]);pairs.forEach(([x,y])=>groups[Number(x.slice(11,13))].push(y));
    plot('sensor-profile',[line([...Array(24).keys()],groups.map(g=>g.length?g.reduce((a,b)=>a+b,0)/g.length:null),'Hourly mean')],{xaxis:{title:{text:'Hour of day'},dtick:4},yaxis:{title:{text:sensor.unit},gridcolor:'#edf0f1'}});
  }
  bind('update','click',update);bind('sensor','change',update);bind('rolling','change',update);await update();
}

async function events() {
  const testEvents=DATA.events.filter(e=>e.year===2019);
  $('content').innerHTML=intro('Leak event explorer','Compare a known onset with pressure, flow and model scores. Amber marks retrospective ground truth; a dark marker shows the alarm confirmation time.')+
    `<div class="controls"><label>Test-year event<select id="event">${testEvents.map(e=>`<option value="${e.pipe}">${e.pipe} · ${e.start.slice(0,10)} · ${e.type}</option>`).join('')}</select></label><label>Method<select id="method">${options(DATA.metrics.map(m=>m.method),'PCA reconstruction')}</select></label><label>Pressure sensor<select id="event-pressure">${sensorOptions('pressure:','pressure:n1')}</select></label><label>Flow sensor<select id="event-flow">${sensorOptions('flow:','flow:p227')}</select></label></div><div id="event-summary"></div><div class="layout"><div>${panel('Pressure response','Completed 15-minute bin means',true,'event-pressure-chart')}${panel('Flow response','Read alongside pressure and the demand cycle',true,'event-flow-chart')}${panel('Anomaly score and threshold','Threshold fixed using 2018 validation; score alone does not emit an alarm',true,'event-score-chart')}</div><div><div class="panel"><h2>At alarm confirmation</h2><div id="contributors"></div><p class="caption">Signed sensor residual robust-z, ranked by magnitude. These explain departures from the trailing reference, not a causal pipe location or ML feature importance.</p></div><div class="panel"><h2>Read the event carefully</h2><p>A new alarm must start after this onset and within 72 hours. A pre-existing alarm receives no credit.</p><p>The episode also needs four consecutive threshold exceedances and at least two abnormal sensors. Gradual leaks may not produce a sharp signature.</p><p class="caption">Windows show 24 hours before and 96 hours after onset. Concurrent leaks and diurnal demand can affect the response.</p></div></div></div>`;
  let request=0;
  async function update() {
    const own=++request, event=DATA.events.find(e=>e.pipe===$('event').value), method=$('method').value;
    const w=await fetchJSON(event.file); if(own!==request||!$('event-summary'))return;
    const result=event.detections.find(d=>d.method===method), threshold=DATA.thresholds[method].threshold;
    const detected=result?.detected_at, valid=detected&&typeof detected==='string';
    $('event-summary').innerHTML=`<div class="metrics">${metric('Known onset',event.start.slice(11,16),event.start.slice(0,10))}${metric('Leak type',esc(event.type),`Pipe ${event.pipe}`)}${metric('Confirmation delay',valid?`${fmt(result.delay_hours)} h`:'Missed',valid?'Matched new alarm within 72h':'No matched new alarm within 72h')}${metric('Reported end',event.end.slice(0,10),event.end.startsWith('2019-12-31')?'Right-censored at record end':event.end.slice(11,16))}</div>`;
    const shapes=[onsetShape(event.start)];
    if(valid)shapes.push({...onsetShape(detected),line:{color:'#353c43',width:1.5,dash:'dash'}});
    plot('event-pressure-chart',[line(w.x,w.measurements[$('event-pressure').value],$('event-pressure').value)],{yaxis:{title:{text:'Pressure (m)'},gridcolor:'#edf0f1'},shapes});
    plot('event-flow-chart',[line(w.x,w.measurements[$('event-flow').value],$('event-flow').value)],{yaxis:{title:{text:'Flow (m³/h)'},gridcolor:'#edf0f1'},shapes});
    plot('event-score-chart',[line(w.x,w.scores[method],method),line([w.x[0],w.x.at(-1)],[threshold,threshold],'Threshold',{line:{color:'#69737b',dash:'dash',width:1}})],{yaxis:{title:{text:'Anomaly score'},gridcolor:'#edf0f1'},shapes});
    $('contributors').innerHTML=valid?`<p class="tag">${esc(detected)}</p>`+result.signed_residual_z.split(', ').map(item=>{const [s,z]=item.split('=');return `<div class="insight"><b>${esc(s)}</b><div class="big">${esc(z)}</div><p>${Number(z)<0?'Below':'Above'} the past daily reference</p></div>`;}).join(''):'<p>No matched alarm. Sensor contributions at a detection time are unavailable.</p>';
  }
  for(const id of ['event','method','event-pressure','event-flow'])bind(id,'change',update);await update();
}

function patterns() {
  $('content').innerHTML=intro('Operating patterns','Understand the demand cycle before interpreting anomalies. These descriptive summaries use both years; they do not fit models or choose thresholds.')+
    `<div class="controls"><label>Pressure or flow sensor<select id="pattern-sensor">${options(DATA.sensors.filter(s=>s.id.startsWith('pressure:')||s.id.startsWith('flow:')).map(s=>s.id),'flow:p227')}</select></label></div>`+
    panel('What is the daily operating rhythm?','Mean measurement by source wall-clock hour · 2018 and 2019',true,'pattern-hour')+
    `<div class="split">${panel('How does the weekly mean change?','Seasonal changes and leak effects are mixed',true,'pattern-week','short')}${panel('Does the day of week matter?','Mean by weekday · no causal attribution',true,'pattern-day','short')}</div><div class="panel"><h2>Whole-record sensor statistics</h2><div id="pattern-stats"></div><p class="caption">Pressure is in m; flow is in m³/h. Whole-record statistics are descriptive and separate from the training transforms.</p></div>`;
  function update(){
    const id=$('pattern-sensor').value, sensor=DATA.sensors.find(s=>s.id===id), stats=sensor.stats;
    plot('pattern-hour',[line(DATA.profiles.hour,DATA.profiles[id],id)],{xaxis:{title:{text:'Hour of day'},dtick:2},yaxis:{title:{text:sensor.unit},gridcolor:'#edf0f1'}});
    plot('pattern-week',[line(DATA.weekly.x,DATA.weekly.series[id],id)],{yaxis:{title:{text:sensor.unit},gridcolor:'#edf0f1'}});
    plot('pattern-day',[{x:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],y:DATA.weekday_profiles[id],type:'bar',marker:{color:colours[0]}}],{hovermode:'closest',yaxis:{title:{text:sensor.unit},gridcolor:'#edf0f1'}});
    $('pattern-stats').innerHTML=`<div class="table-scroll"><table><thead><tr>${['Mean','Median','Std','Min','5th percentile','95th percentile','Max'].map(v=>`<th>${v}</th>`).join('')}</tr></thead><tbody><tr>${['mean','50%','std','min','5%','95%','max'].map(k=>`<td>${fmt(stats[k],2)}</td>`).join('')}</tr></tbody></table></div>`;
  }
  bind('pattern-sensor','change',update);update();
}

function models() {
  const methods=DATA.metrics.map(m=>m.method), m=DATA.metrics;
  $('content').innerHTML=intro('Model comparison','Frozen thresholds, a common persistence policy, and an untouched 2019 holdout. All point metrics describe the new-onset task, not ongoing leak presence.')+
    `<div class="notice">High recall is not enough. Frequent alarms can match a 72-hour onset window by chance. Compare event recall with the timing-shift control and false alarms.</div><div class="panel"><h2>2019 test results</h2>${comparisonTable()}<p class="caption">AP = average precision of the raw score. No-skill AP reference: ${fmt(m[0].positive_fraction,3)}. Delay includes detected events only; misses are excluded.</p></div>`+
    `<div class="split">${panel('Alarm reliability','Each bar counts unmatched new alarm starts in the test year',true,'false-alarms')}${panel('Event recall versus shifted alarms','200 circular timing shifts preserve alarm count and relative spacing',true,'shift-control')}</div>`+
    `<div class="panel"><h2>Why the methods differ</h2><p>Robust and IQR baselines expose large departures directly. PCA can highlight departures from learned sensor relationships. Isolation Forest and novelty LOF use multivariate feature patterns. All methods face seasonal drift and ongoing background leaks.</p><p>A threshold selected on only two validation onsets is uncertain. The repository includes every validation candidate and fixed-threshold sensitivity at 24, 72 and 168 hours.</p><p>The timing-shift control is descriptive, not a significance test. It does not account for seasonal nonstationarity. An unmatched alarm may still reflect a genuine hydraulic change.</p></div>`;
  plot('false-alarms',[{x:methods,y:m.map(r=>r.false_alarms),type:'bar',marker:{color:colours[2]},hovertemplate:'%{x}<br>%{y} false onset alarms<extra></extra>'}],{hovermode:'closest',margin:{l:56,r:16,t:16,b:96},yaxis:{title:{text:'Unmatched alarms'},gridcolor:'#edf0f1'},xaxis:{tickangle:-20}});
  plot('shift-control',[{x:methods,y:m.map(r=>r.event_recall),name:'Observed',type:'bar',marker:{color:colours[0]}},{x:methods,y:m.map(r=>r.shift_control_mean_recall),name:'Shifted mean',type:'bar',marker:{color:'#bdc5c8'},error_y:{type:'data',symmetric:false,array:m.map(r=>r.shift_control_p95_recall-r.shift_control_mean_recall),arrayminus:m.map(r=>r.shift_control_mean_recall-r.shift_control_p05_recall),color:'#69737b'}}],{hovermode:'closest',barmode:'group',margin:{l:56,r:16,t:32,b:96},yaxis:{title:{text:'Event recall'},tickformat:'.0%',range:[0,1.1],gridcolor:'#edf0f1'},xaxis:{tickangle:-20}});
}

function network() {
  $('content').innerHTML=intro('Network & sensor relationships','Nominal EPANET geometry and observed correlations. The drawing uses source coordinates, not a geographic basemap or inferred pipe locations.')+
    `<div class="layout">${panel('L-Town nominal network','Pressure sensors are teal; flow meters are placed at their metered link midpoint',true,'network-map','tall')}<div class="panel"><h2>Instrumentation</h2><div class="insight"><b>33 pressure locations</b><p>Pressure in metres of water head</p></div><div class="insight"><b>3 metered links</b><p>p227, p235 and PUMP_1 · m³/h</p></div><div class="insight"><b>82 AMR nodes</b><p>Demand in L/h, available in the sensor explorer</p></div><div class="insight"><b>1 tank level</b><p>T1 · metres</p></div><p class="caption">Geometry comes from L-TOWN.inp. Hidden simulation parameters from L-TOWN_Real.inp are not used.</p></div></div>`+
    panel('Which sensors move together?','Pearson correlation · all pressure, flow and level channels · both years',true,'correlation','tall')+
    `<p>Correlations mix demand cycles, seasonality and leak responses. Similar behaviour does not establish that sensors are adjacent or that one causes the other.</p>`;
  const nodes=DATA.topology.nodes, edges=DATA.topology.edges, x=[],y=[];
  edges.forEach(e=>{if(nodes[e.from]&&nodes[e.to]){x.push(nodes[e.from][0],nodes[e.to][0],null);y.push(nodes[e.from][1],nodes[e.to][1],null);}});
  const pressure=DATA.sensors.filter(s=>s.id.startsWith('pressure:')).map(s=>s.id.split(':')[1]).filter(id=>nodes[id]);
  const flow=DATA.sensors.filter(s=>s.id.startsWith('flow:')).map(s=>edges.find(e=>e.id===s.id.split(':')[1])).filter(e=>e&&nodes[e.from]&&nodes[e.to]);
  plot('network-map',[line(x,y,'Nominal pipes',{line:{width:1,color:'#c3cbcf'},hoverinfo:'skip'}),{x:pressure.map(id=>nodes[id][0]),y:pressure.map(id=>nodes[id][1]),text:pressure,type:'scatter',mode:'markers',name:'Pressure sensor',marker:{size:7,color:colours[0]},hovertemplate:'%{text}<extra>Pressure sensor</extra>'},{x:flow.map(e=>(nodes[e.from][0]+nodes[e.to][0])/2),y:flow.map(e=>(nodes[e.from][1]+nodes[e.to][1])/2),text:flow.map(e=>e.id),type:'scatter',mode:'markers',name:'Flow meter',marker:{symbol:'diamond',size:10,color:colours[1]},hovertemplate:'%{text}<extra>Flow meter</extra>'}],{hovermode:'closest',xaxis:{visible:false},yaxis:{visible:false,scaleanchor:'x',scaleratio:1},margin:{l:8,r:8,t:24,b:8},legend:{orientation:'h',y:1.04}});
  const c=DATA.correlation;
  plot('correlation',[{z:c.z,x:c.labels,y:c.labels,type:'heatmap',zmin:-1,zmax:1,colorscale:[[0,'#a96c38'],[.5,'#f5f5f3'],[1,'#087782']],colorbar:{title:{text:'r'}},hovertemplate:'%{x}<br>%{y}<br>r = %{z:.2f}<extra></extra>'}],{hovermode:'closest',margin:{l:120,r:40,t:16,b:120},xaxis:{tickangle:-60,tickfont:{size:9}},yaxis:{tickfont:{size:9}}});
}

function methods() {
  const e=DATA.experiment;
  $('content').innerHTML=intro('Data & methodology','The analysis is reproducible from official downloads. Ground-truth leak histories are kept separate from features available at detection time.')+
    `<div class="split"><div class="panel"><h2>Source and quality</h2><p>BattLeDIM simulates realistic sensor measurements for L-Town. It is not a field deployment. The CSVs cover two complete years at five-minute intervals, with semicolon separators and decimal commas.</p><div class="data-list"><span>Measurement cells</span><strong>${fmt(DATA.insights.measurement_cells,0)}</strong><span>Missing values</span><strong>0</strong><span>Duplicate timestamps</span><strong>0</strong><span>Sampling</span><strong>Regular, 5 minutes</strong><span>Timezone</span><strong>Unspecified in source</strong></div><p class="caption">Downloads are verified against Zenodo checksums. No imputation was needed.</p></div><div class="panel"><h2>Chronological experiment</h2><div class="data-list"><span>Fit period</span><strong>Jan–Sep 2018</strong><span>Validation</span><strong>Oct–Dec 2018</strong><span>Test</span><strong>Jan–Dec 2019</strong><span>Eligible fit rows</span><strong>${fmt(e.training_rows,0)}</strong><span>ML fit sample</span><strong>${fmt(e.sample_rows,0)}</strong><span>Features</span><strong>${e.feature_count}</strong></div><p class="caption">Historical transition windows are excluded from fitting. Stable-operation rows may contain existing background leaks.</p></div></div>`+
    `<div class="panel"><h2>From measurements to alarms</h2><ol><li>Aggregate completed 15-minute bins; retain original measurements separately.</li><li>Build causal daily residuals, hourly statistics, lags and weekly differences from pressure, flow and level.</li><li>Fit scales and five small detectors on eligible 2018 rows only.</li><li>Choose a training-score percentile by validation event F1; freeze it before testing.</li><li>Require four consecutive exceedances and at least two abnormal sensors; clear after four non-exceedances.</li><li>Match new alarm starts one-to-one to onsets within 72 hours. Timestamp confirmation without backdating.</li></ol></div>`+
    `<div class="notice">Only two new onsets occur in validation. Persistent leaks, annual drift and an adapting reference limit how confidently these results generalise.</div>`+
    `<div class="panel"><h2>What to do next</h2><p>Reduce false alarms before seeking higher recall: compare sensor-group models, explicit demand adjustment and pump-state conditioning. Assess additional networks and longer validation histories. Evaluate localization separately, using a hydraulic model and a spatial scoring rule.</p><p>Read the full cleaning policy, feature definitions, matching rules and limitations in the repository.</p><a href="https://github.com/puneetpal-singh/water-leak-detection/blob/main/docs/methodology.md">Full methodology ↗</a></div>`;
}

async function route() {
  if(!DATA)return;const version=++routeVersion, page=location.hash.slice(1)||'overview';
  document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.dataset.page===page));
  $('status').style.display='none';
  const pages={overview,patterns,sensors,events,models,network,methods};
  if(!pages[page]){location.hash='overview';return;}
  await pages[page](version);
}
window.addEventListener('hashchange',()=>route().catch(showError));
fetchJSON('data.json').then(data=>{DATA=data;return route();}).catch(showError);
