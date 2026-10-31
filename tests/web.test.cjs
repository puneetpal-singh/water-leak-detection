const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function fixture() {
  const elements = new Map(), plots = [], purged = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {value:'',style:{},handlers:{},cleared:false,
      addEventListener(event, callback) { this.handlers[event] = callback; },
      replaceChildren() { this.cleared = true; }});
    return elements.get(id);
  }
  let resolveSensor;
  const sensorResponse = new Promise(resolve => { resolveSensor = resolve; });
  const context = vm.createContext({
    URL,Response,DecompressionStream,atob,
    document:{currentScript:{src:'https://example.test/demos/water-network/app.js'},getElementById:element,querySelectorAll:()=>[]}, window:{addEventListener(){}},
    Plotly:{react:(id,traces)=>{plots.push({id,traces});return Promise.resolve();},purge:id=>purged.push(id)},
    fetch:url=>String(url).endsWith('/manifest.json')?new Promise(()=>{}):sensorResponse,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/web/dist/app.js'),'utf8'),context);
  vm.runInContext(`DATA={sensors:[{id:'pressure:n1',file:'sensors/0.json',unit:'m'}],events:[]}; routeVersion=1;`,context);
  element('sensor').value='pressure:n1'; element('from').value='2019-01-01';
  element('through').value='2019-01-02'; element('rolling').value='6 hours';
  const complete = () => resolveSensor({ok:true,json:async()=>({
    x:Array.from({length:24},(_,i)=>`2019-01-01T${String(i).padStart(2,'0')}:00:00`),
    y:Array.from({length:24},(_,i)=>30+i/10),abnormal:Array(24).fill(false)})});
  return {context,element,plots,purged,complete};
}

test('a sensor response cannot redraw a later route', async()=>{
  const f=fixture();
  const pending=vm.runInContext('sensors(1)',f.context);
  vm.runInContext('routeVersion=2',f.context);
  f.complete();await pending;
  assert.equal(f.plots.length,0);
});

test('compressed series reconstruct every timestamp and packed anomaly bit',async()=>{
  const f=fixture();const zlib=require('node:zlib');
  const flags=Buffer.from([0b10000101,0b00000001]).toString('base64');
  const source={time:{start:'2019-03-30T23:00:00',step_seconds:3600,count:10},y:[1,2,3,4,5,6,7,8,9,10],abnormal_bits:flags};
  f.context.fetch=async()=>new Response(zlib.gzipSync(JSON.stringify(source)));
  const result=await vm.runInContext("fetchJSON('sample.json.gz')",f.context);
  assert.equal(result.x[0],'2019-03-30T23:00:00');
  assert.equal(result.x[3],'2019-03-31T02:00:00'); // No invented DST conversion.
  assert.equal(result.x[9],'2019-03-31T08:00:00');
  assert.deepEqual(Array.from(result.abnormal),[true,false,true,false,false,false,false,true,true,false]);
  assert.deepEqual(Array.from(result.y),source.y);
});

test('in-flight requests are shared and memory cache is bounded',async()=>{
  const f=fixture();let requests=0;
  f.context.fetch=async()=>{requests++;return {ok:true,json:async()=>({answer:42})};};
  const pair=await vm.runInContext("Promise.all([fetchJSON('same.json'),fetchJSON('same.json')])",f.context);
  assert.equal(requests,1);assert.equal(pair[0],pair[1]);
  await vm.runInContext("Promise.all(Array.from({length:15},(_,i)=>fetchJSON('extra-'+i+'.json')))",f.context);
  assert.equal(vm.runInContext('cache.size',f.context),10);
});

test('valid sensor data draws all three charts',async()=>{
  const f=fixture();const pending=vm.runInContext('sensors(1)',f.context);
  f.complete();await pending;
  assert.deepEqual(f.plots.map(p=>p.id),['sensor-trace','sensor-hist','sensor-profile']);
  assert.match(f.element('sensor-stats').innerHTML,/24/);
});

test('invalid dates clear stale charts instead of retaining old data',async()=>{
  const f=fixture();const pending=vm.runInContext('sensors(1)',f.context);
  f.complete();await pending;
  f.element('from').value='2019-02-01';
  await f.element('update').handlers.click();
  assert.match(f.element('sensor-stats').innerHTML,/valid date range/);
  for(const id of ['sensor-trace','sensor-hist','sensor-profile']){
    assert.equal(f.element(id).cleared,true);assert.ok(f.purged.includes(id));
  }
  assert.equal(f.plots.length,3);
});
