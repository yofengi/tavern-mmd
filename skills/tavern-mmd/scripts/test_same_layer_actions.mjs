import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
for(const name of ['core.js','actions.js','provided-actions.js','models.js','provided-models.js','native.js'])
  vm.runInThisContext(await readFile(new URL('../assets/same-layer-kit/'+name,import.meta.url),'utf8'));
const A=globalThis.MmdSameLayerActions,P=globalThis.MmdSameLayerProvidedActions;
function fixture(){
  const calls=[];let destroyed=0;
  const raw={connection:{status:'connected'},privateToken:'do-not-project',messages:[{id:'m1',role:'assistant',text:'answer',html:'<script>private</script>',index:0,nativeIndex:0,targetFingerprint:'fp1',capabilities:{copy:true,edit:true,delete:true,rollback:true,startNewStory:true,regenerate:true}}],
    editPanel:{open:true,messageId:'m1',text:'draft',transforms:[{id:'t1',label:'clean'}]},
    conversationPanel:{open:true,conversations:[{id:'c1',fingerprint:'cf1',index:0,title:'first',preview:'summary',current:false,capabilities:{rename:true,delete:true}}]},
    personaPanel:{open:true,modes:[{id:'mode1',label:'custom',selected:true,disabled:false}],genderChoices:[{id:'g1',label:'woman',selected:true,disabled:false}]},
    supplementPanel:{open:true,picker:{open:true,choices:[{id:'pos1',label:'begin',selected:true}]}},
    instructionSelector:{open:true,revision:'native-revision',instructions:[{id:'i1',fingerprint:'if1',index:0,label:'inspect'}]},
    moreMenu:{open:true,items:[{id:'more1',kind:'background',label:'background',available:true,destructive:false}]}};
  const bridge={getSnapshot:()=>raw,getCapabilities:()=>Object.fromEntries(A.actions.map(a=>[a,{available:true}])),getRegisteredActions:()=>A.actions,refresh(){},destroy(){destroyed++;},
    async invoke(action,payload){calls.push({action,payload});
      if(action==='deleteMessage'&&!payload.confirmationToken)return {ok:true,action,data:{phase:'confirmation-required',confirmation:{messageId:payload.messageId,confirmationToken:'native-message-token',prompt:'delete?'}}};
      if(action==='requestDeleteConversation')return {ok:true,action,data:{phase:'confirmation-required',confirmation:{...payload,confirmationToken:'native-conversation-token',prompt:'delete?'}}};
      return {ok:true,action,data:{phase:'observed',text:'public',html:'private',privateToken:'private'}};}};
  return {raw,bridge,calls,get destroyed(){return destroyed;}};
}
function payload(action,state){
  const values={text:'text',messageId:'m1',transformId:'t1',itemId:'more1',conversationId:'c1',fingerprint:action==='applyInstruction'?'if1':'cf1',index:0,title:'renamed',
    modeId:'mode1',name:'name',genderId:'g1',identity:'identity',choiceId:'pos1',instructionId:'i1',label:'inspect'};
  return {...Object.fromEntries((A.required[action]||[]).map(k=>[k,values[k]])),revision:state[A.groupFor[action]].revision};
}
test('all 52 external feature handlers receive validated, projected requests and results',async()=>{
  const f=fixture(),adapter=P.create(f.bridge);const completed=new Set();
  for(const action of A.actions){
    if(action==='deleteConversation')continue;
    const p=payload(action,adapter.snapshot());const result=await adapter.invoke(action,p);completed.add(action);
    assert.equal(result.ok,true);assert.equal(result.persisted,'unknown');assert.equal('html' in result.data,false);assert.equal('privateToken' in result.data,false);
    if(['deleteMessage','rollbackMessage'].includes(action)){
      assert.equal(result.accepted,false);await adapter.invoke(action,{...p,revision:adapter.snapshot()[A.groupFor[action]].revision,confirmationToken:result.data.confirmation.confirmationToken});
    }
    if(action==='requestDeleteConversation'){
      const confirm={...payload('deleteConversation',adapter.snapshot()),confirmationToken:result.data.confirmation.confirmationToken};
      await adapter.invoke('deleteConversation',confirm);completed.add('deleteConversation');
    }
  }
  assert.equal(completed.size,52);assert.deepEqual(new Set(f.calls.map(c=>c.action)),completed);
  const instruction=f.calls.find(x=>x.action==='applyInstruction');assert.equal(instruction.payload.revision,'native-revision');
  assert.equal('revision' in f.calls.find(x=>x.action==='setPersonaName').payload,false);
  const publicState=adapter.snapshot();assert.equal('privateToken' in publicState,false);assert.equal('html' in publicState.messages.items[0],false);
  adapter.destroy();assert.equal(f.destroyed,0);
});
test('provided confirmations bind the original target, expire on cancel and never replay',async()=>{
  const f=fixture(),a=P.create(f.bridge);let p=payload('deleteMessage',a.snapshot());let first=await a.invoke('deleteMessage',p);
  f.raw.messages[0].text='changed';
  await assert.rejects(a.invoke('deleteMessage',{...p,revision:a.snapshot().messages.revision,confirmationToken:first.data.confirmation.confirmationToken}),{code:'CONFIRMATION_EXPIRED'});
  assert.equal(f.calls.length,1);
  p=payload('rollbackMessage',a.snapshot());first=await a.invoke('rollbackMessage',p);a.cancel();
  await assert.rejects(a.invoke('rollbackMessage',{...p,revision:a.snapshot().messages.revision,confirmationToken:first.data.confirmation.confirmationToken}),{code:'CONFIRMATION_EXPIRED'});
  assert.equal(f.calls.length,1);a.destroy();
});
test('external targets, stale revisions, unregistered handlers and arbitrary payload fields are rejected',async()=>{
  const f=fixture(),a=P.create(f.bridge);const p=payload('applyInstruction',a.snapshot());f.raw.instructionSelector.instructions[0].label='changed';
  await assert.rejects(a.invoke('applyInstruction',p),{code:'STALE_VIEW'});
  await assert.rejects(a.invoke('setInputText',{...payload('setInputText',a.snapshot()),selector:'body'}),{code:'INVALID_ARGUMENT'});
  f.bridge.getRegisteredActions=()=>[];await assert.rejects(a.invoke('openComments',{}),{code:'NOT_AVAILABLE'});
  assert.equal(f.calls.length,0);a.destroy();
});
test('provided lifecycle cancellation ignores late results and preserves the caller-owned bridge',async()=>{
  const f=fixture();let release;f.bridge.invoke=()=>new Promise(resolve=>{release=resolve;});
  const a=P.create(f.bridge);const promise=a.invoke('openComments',{});a.cancel();release({ok:true,data:{phase:'observed'}});
  await assert.rejects(promise,{code:'CONTEXT_CHANGED'});a.destroy();assert.equal(f.destroyed,0);
});
test('adapter exposes full built-in feature capabilities without projectResult and honors the allowlist',async()=>{
  const f=fixture(),a=globalThis.MmdSameLayerAdapters.provided(f.bridge,{allowedActions:['openComments','setInputText']});
  assert.equal(a.snapshot().capabilities.openComments.available,true);assert.equal(a.snapshot().capabilities.openPersona.available,false);
  await a.invoke('openComments',{});assert.equal(f.calls[0].action,'openComments');
  await assert.rejects(a.invoke('openPersona',{}),{code:'NOT_AVAILABLE'});a.destroy();assert.equal(f.destroyed,0);
});
test('one concurrency gate prevents a second operation across feature groups',async()=>{
  let resolve;const calls=[];const a=A.serial({snapshot:()=>({capabilities:{first:{available:true},second:{available:true}}}),
    invoke(action){calls.push(action);return new Promise(r=>{resolve=r;});},cancel(){},destroy(){}});
  const p=a.invoke('first',{});assert.equal(a.snapshot().capabilities.second.available,false);
  await assert.rejects(a.invoke('second',{}),{code:'NOT_AVAILABLE'});resolve({ok:true});await p;assert.deepEqual(calls,['first']);a.destroy();
});
