import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
for (const name of ['core.js','models.js','provided-models.js','native.js']) vm.runInThisContext(await readFile(new URL('../assets/same-layer-kit/'+name,import.meta.url),'utf8'));
const M=globalThis.MmdSameLayerModels,P=globalThis.MmdSameLayerProvidedModels,C=globalThis.MmdSameLayerCore;

function fixture() {
  let selected='a', memory=false, destroyed=0;
  const calls=[];
  const snapshot={connection:{status:'connected'},messages:[],privateToken:'never-project',
    modelPanel:{open:false,title:'models',filters:[],models:[]},
    modelConfiguration:{open:false,title:'settings',modelName:'Alpha',energyLabel:'native cost',controls:[]}};
  function list(){snapshot.modelPanel.models=['a','b'].map(id=>({id,name:id==='a'?'Alpha':'Beta',description:'description',batteryLabel:'cost label',permission:'available',successRate:'',selected:id===selected,html:'<script>untrusted</script>'}));}
  function setting(){snapshot.modelConfiguration.controls=[{id:'toggle',type:'toggle',label:'memory',description:'',value:memory,choices:[]}];}
  const raw={getSnapshot:()=>snapshot,getCapabilities:()=>Object.fromEntries(M.actions.map(action=>[action,{available:true}])),
    getRegisteredActions:()=>M.actions,refresh(){},destroy(){destroyed++;},
    async invoke(action,payload){calls.push({action,payload});
      if(action==='openModelSettings'){snapshot.modelPanel.open=true;list();}
      if(action==='closeModelSettings')snapshot.modelPanel.open=false;
      if(action==='selectModel'){selected=payload.modelId;snapshot.modelPanel.open=false;}
      if(action==='openModelConfiguration'){snapshot.modelConfiguration.open=true;setting();}
      if(action==='closeModelConfiguration'||action==='submitModelConfiguration')snapshot.modelConfiguration.open=false;
      if(action==='setModelSetting'){memory=!memory;setting();}
      return {ok:true,action,data:{privateToken:'excluded',phase:'selected'}};}};
  return {raw,calls,snapshot,setMemory(value){memory=value;setting();},get destroyed(){return destroyed;}};
}

test('provided model bridge projects only model data and rereads actual selection',async()=>{
  const f=fixture(),adapter=P.create(f.raw);
  await adapter.invoke('openModelSettings');const before=adapter.snapshot();
  assert.equal('privateToken' in before,false);assert.equal('html' in before.modelPanel.models[0],false);
  const result=await adapter.invoke('selectModel',{revision:before.modelPanel.revision,modelId:'b'});
  assert.equal(result.data.phase,'selection-observed');assert.equal(adapter.snapshot().current.name,'Beta');
  assert.equal(result.persisted,'unknown');assert.equal(f.calls.filter(row=>row.action==='selectModel').length,1);
  assert.equal(f.calls.filter(row=>row.action==='openModelSettings').length,2);
  adapter.destroy();assert.equal(f.destroyed,0);
});

test('provided toggles use desired values and reject a stale settings snapshot',async()=>{
  const f=fixture(),adapter=P.create(f.raw);await adapter.invoke('openModelSettings');
  await adapter.invoke('openModelConfiguration',{revision:adapter.snapshot().modelPanel.revision,modelId:'a'});
  const cfg=adapter.snapshot().modelConfiguration;
  await adapter.invoke('setModelSetting',{revision:cfg.revision,controlId:'toggle',value:false});
  assert.equal(f.calls.some(row=>row.action==='setModelSetting'),false);
  await adapter.invoke('setModelSetting',{revision:cfg.revision,controlId:'toggle',value:true});
  assert.equal(f.calls.filter(row=>row.action==='setModelSetting').length,1);
  await assert.rejects(adapter.invoke('setModelSetting',{revision:cfg.revision,controlId:'toggle',value:false}),{code:'STALE_TARGET'});
});

test('provided cancellation invalidates a late result without destroying the external owner',async()=>{
  const f=fixture();let release;
  f.raw.invoke=()=>new Promise(resolve=>release=resolve);
  const adapter=P.create(f.raw),pending=adapter.invoke('openModelSettings');
  adapter.cancel();release({ok:true,action:'openModelSettings'});
  await assert.rejects(pending,{code:'CANCELLED'});
  assert.equal(adapter.snapshot().busy,false);adapter.destroy();assert.equal(f.destroyed,0);
});

test('the provided native wrapper exposes the reusable model UI contract without an extra callback',async()=>{
  const f=fixture(),adapter=globalThis.MmdSameLayerAdapters.provided(f.raw,{appId:'test'});
  assert.equal(adapter.snapshot().capabilities.openModelSettings.available,true);
  await adapter.invoke('openModelSettings');assert.equal(adapter.snapshot().models.modelPanel.models.length,2);
  const restricted=globalThis.MmdSameLayerAdapters.provided(f.raw,{appId:'test',allowedActions:['sendMessage']});
  assert.equal(restricted.snapshot().capabilities.selectModel.available,false);
  await assert.rejects(restricted.invoke('selectModel',{}),{code:'NOT_AVAILABLE'});
});

test('Mock model settings and flags honor the same command shape',async()=>{
  const adapter=M.mock();await adapter.invoke('openModelSettings');
  await adapter.invoke('openModelConfiguration',{revision:adapter.snapshot().modelPanel.revision,modelId:'narration'});
  await adapter.invoke('setModelSetting',{revision:adapter.snapshot().modelConfiguration.revision,controlId:'tokens',choiceId:'long'});
  assert.equal(adapter.snapshot().modelConfiguration.controls[0].choices.find(row=>row.id==='long').selected,true);
  assert.equal(M.mock({models:false}).snapshot().enabled,false);
  assert.equal(C.canonical(adapter.snapshot()).includes('undefined'),false);
});
