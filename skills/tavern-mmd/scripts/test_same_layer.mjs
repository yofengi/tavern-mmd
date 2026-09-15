import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';

if (!globalThis.crypto) globalThis.crypto = webcrypto;
vm.runInThisContext(await readFile(new URL('../assets/same-layer-kit/core.js', import.meta.url), 'utf8'));
const C = globalThis.MmdSameLayerCore;
const scope = { appId: 'test-game', accountKey: 'account-a', roleId: 'role-a', conversationKey: 'main' };
function memory() {
  const rows = new Map();
  return { rows, getItem: k => rows.has(k) ? rows.get(k) : null, setItem: (k, v) => rows.set(k, v) };
}
function mutex() {
  let tail = Promise.resolve();
  return (_, fn) => { const result = tail.then(fn); tail = result.catch(() => {}); return result; };
}
const make = (extra = {}) => new C.SaveStore({ scope, storage: memory(), lock: mutex(), ...extra });
const command = (id, revision = 0, type = 'explore') => ({ id, type, expectedRevision: revision });

test('engine is deterministic, idempotent and rejects stale commands', () => {
  const first = C.reduce(C.initial(), command('first'));
  assert.equal(first.state.energy, 4);
  assert.deepEqual(first, C.reduce(C.initial(), command('first')));
  assert.equal(C.reduce(first.state, command('first')).duplicate, true);
  assert.throws(() => C.reduce(first.state, command('second')), { code: 'STALE_REVISION' });
  assert.throws(() => C.reduce(first.state, command('first', 1, 'rest')), { code: 'COMMAND_REUSED' });
  assert.equal('rng' in C.publicState(first.state), false);
});

test('save acknowledgement precedes public progress and survives a new store', async () => {
  const storage = memory(); const a = make({ storage }); const start = await a.load();
  const committed = await a.action(command('one'), start.epoch);
  const b = make({ storage });
  assert.deepEqual(await b.load(), committed);
  storage.setItem = () => { throw Error('quota'); };
  await assert.rejects(a.action(command('two', 1), start.epoch), { code: 'SAVE_FAILED' });
  assert.equal((await b.load()).state.revision, 1);
});

test('account, role, conversation and app each partition save keys', () => {
  const base = make();
  for (const field of Object.keys(scope)) assert.notEqual(base.key, make({ scope: { ...scope, [field]: 'other' } }).key);
  assert.throws(() => make({ scope: { ...scope, conversationKey: '' } }), { code: 'SCOPE_UNAVAILABLE' });
});

test('corrupt data and mismatched scope are preserved, not reset', async () => {
  const storage = memory(); const a = make({ storage });
  const start = await a.load(); const raw = await a.export();
  storage.rows.set(a.key, '{broken');
  await assert.rejects(a.load(), { code: 'INVALID_SAVE' });
  assert.equal(storage.getItem(a.key), '{broken');
  storage.rows.set(a.key, raw);
  const altered = JSON.parse(raw); altered.state.coins += 1;
  await assert.rejects(a.import(JSON.stringify(altered), start.epoch), { code: 'CHECKSUM_MISMATCH' });
  const other = make({ scope: { ...scope, conversationKey: 'other' } }); const otherStart = await other.load();
  await assert.rejects(other.import(raw, otherStart.epoch), { code: 'INVALID_SAVE' });
  assert.equal((await a.load()).state.revision, 0);
});

test('schema 1 migration preserves original and validates before writing', async () => {
  const storage = memory(); const a = make({ storage }); const current = await a.load();
  const legacy = C.clone(current); legacy.schema = 1;
  legacy.state.gold = 9; delete legacy.state.coins;
  const raw = C.canonical(await C.seal(legacy)); storage.rows.set(a.key, raw);
  const migrated = await a.load();
  assert.equal(migrated.schema, 2); assert.equal(migrated.state.coins, 9);
  assert.equal([...storage.rows.values()].filter(v => v === raw).length, 1);
});

test('concurrent revision checks commit one command, never lose an update silently', async () => {
  const storage = memory(), lock = mutex(); const a = make({ storage, lock }), b = make({ storage, lock });
  const start = await a.load();
  const results = await Promise.allSettled([a.action(command('a'), start.epoch), b.action(command('b'), start.epoch)]);
  assert.equal(results.filter(r => r.status === 'fulfilled').length, 1);
  assert.equal((await a.load()).state.revision, 1);
});

test('scope change while waiting for a lock cannot write old progress', async () => {
  const storage = memory(); let current = true;
  let release;
  const a = make({ storage, isCurrent: () => current,
    lock: async (_, fn) => { await new Promise(r => { release = r; }); return fn(); } });
  const pending = a.load(); current = false; release();
  await assert.rejects(pending, { code: 'SCOPE_CHANGED' }); assert.equal(storage.rows.size, 0);
});

test('missing durable lock fails explicitly', async () => {
  const a = make({ lock: null }); await assert.rejects(a.load(), { code: 'LOCK_UNAVAILABLE' });
});

test('narration is reserved before sending; save import preserves unknown and invalidates late updates', async () => {
  const a = make(); const start = await a.load(); const before = await a.export();
  const turn = await a.action(command('turn'), start.epoch);
  const request = { id: 'request-1', receiptId: 'turn', epoch: turn.epoch, expectedRevision: 1 };
  const facts = await a.reserveNarration(request);
  assert.equal(facts.turn, 1); assert.equal('rng' in facts, false);
  assert.equal((await a.load()).ledger[0].status, 'unknown');
  await assert.rejects(a.reserveNarration({ ...request, id: 'request-2' }), { code: 'ALREADY_REQUESTED' });
  const imported = await a.import(before, start.epoch);
  assert.equal(imported.state.revision, 0); assert.equal(imported.ledger[0].status, 'unknown');
  assert.notEqual(imported.epoch, start.epoch);
  await assert.rejects(a.settleNarration('request-1', 'accepted', start.epoch), { code: 'STALE_EPOCH' });
  assert.equal((await a.load()).state.revision, 0);
});


test('provided bridge gates capabilities and preserves projected result phases', async () => {
  vm.runInThisContext(await readFile(new URL('../assets/same-layer-kit/native.js', import.meta.url), 'utf8'));
  let enabled = true, calls = 0, destroyed = 0;
  const bridge = {
    getSnapshot: () => ({ connection: {status:'connected'}, messages: [{id:'m1',role:'assistant',text:'hello',html:'<script>untrusted</script>'}] }),
    getCapabilities: () => ({sendMessage:{available:enabled}, deleteMessage:{available:true}, contractOnly:{available:true}}),
    getRegisteredActions: () => ['sendMessage', 'deleteMessage'],
    invoke: async action => { calls++; return {ok:true,action,data:{phase:'confirmation-required',messageId:'m1'}}; },
    destroy: () => destroyed++
  };
  const config = {appId:scope.appId, readScope:()=>({...scope, privateField:'excluded'}), allowedActions:['sendMessage','deleteMessage','contractOnly']};
  const a = globalThis.MmdSameLayerAdapters.provided(bridge, config);
  assert.deepEqual(a.scope(), scope);
  assert.equal('html' in a.snapshot().messages[0], false);
  assert.equal(a.snapshot().capabilities.deleteMessage.available, false);
  await assert.rejects(a.invoke('deleteMessage', {}), {code:'NOT_AVAILABLE'});
  enabled = false;
  await assert.rejects(a.invoke('sendMessage', {text:'test'}), {code:'NOT_AVAILABLE'});
  assert.equal(calls, 0);
  config.projectResult = (_, result) => result.data;
  assert.equal(a.snapshot().capabilities.contractOnly.available, false);
  assert.equal((await a.invoke('deleteMessage', {})).data.phase, 'confirmation-required');
  a.destroy(); assert.equal(destroyed, 0);
});
