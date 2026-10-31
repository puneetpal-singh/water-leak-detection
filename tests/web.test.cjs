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
    document:{getElementById:element,querySelectorAll:()=>[]}, window:{addEventListener(){}},
    Plotly:{react:(id,traces)=>{plots.push({id,traces});return Promise.resolve();},purge:id=>purged.push(id)},
    fetch:url=>url==='data.json'?new Promise(()=>{}):sensorResponse,
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
