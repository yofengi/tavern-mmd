/* Original minimal engine and scoped save store. No platform endpoints. */
(function (G) {
  'use strict';
  const MAX_RECORDS = 1000;
  function fail(code, message) { const e = new Error(message || code); e.code = code; throw e; }
  function plain(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function canonical(v) {
    if (v === null || typeof v === 'boolean' || typeof v === 'string') return JSON.stringify(v);
    if (typeof v === 'number' && Number.isFinite(v)) return JSON.stringify(v);
    if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']';
    if (plain(v)) return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canonical(v[k])).join(',') + '}';
    fail('INVALID_DATA', '数据必须是普通 JSON 值');
  }
  const clone = v => JSON.parse(canonical(v));
  const id = v => typeof v === 'string' && /^[A-Za-z0-9_.:-]{1,120}$/.test(v);
  const integer = (v, lo, hi) => Number.isSafeInteger(v) && v >= lo && v <= hi;
  function scopeKey(scope) {
    if (!plain(scope) || !['appId', 'accountKey', 'roleId', 'conversationKey'].every(k => id(scope[k]))) {
      fail('SCOPE_UNAVAILABLE', '尚未确认当前账号、角色和会话，不能保存游戏');
    }
    return canonical(Object.fromEntries(['appId', 'accountKey', 'roleId', 'conversationKey'].map(k => [k, scope[k]])));
  }
  function initial() { return { revision: 0, turn: 0, energy: 5, coins: 0, rng: 123456789, receipts: [] }; }
  function validateState(s) {
    if (!plain(s) || !integer(s.revision, 0, MAX_RECORDS) || s.turn !== s.revision ||
        !integer(s.energy, 0, 5) || !integer(s.coins, 0, 100000) || !integer(s.rng, 1, 4294967295) ||
        !Array.isArray(s.receipts) || s.receipts.length !== s.revision) fail('INVALID_SAVE', '游戏状态格式无效');
    const seen = new Set();
    s.receipts.forEach((r, i) => {
      if (!plain(r) || !id(r.id) || seen.has(r.id) || r.revision !== i + 1 ||
          !['explore', 'rest'].includes(r.action) || !integer(r.gain, 0, 3)) fail('INVALID_SAVE', '行动回执无效');
      seen.add(r.id);
    });
    return s;
  }
  function reduce(state, command) {
    validateState(state);
    if (!plain(command) || !id(command.id) || !['explore', 'rest'].includes(command.type)) fail('INVALID_COMMAND');
    const old = state.receipts.find(r => r.id === command.id);
    if (old) {
      if (old.action !== command.type) fail('COMMAND_REUSED', '同一命令编号不能改变动作');
      return { state: clone(state), receipt: clone(old), duplicate: true };
    }
    if (command.expectedRevision !== state.revision) fail('STALE_REVISION', '进度已变化，请刷新后再操作');
    if (state.revision >= MAX_RECORDS) fail('DEMO_LIMIT', '示例已达回合上限，请导出存档');
    if (command.type === 'explore' && state.energy === 0) fail('NO_ENERGY', '先休息恢复体力');
    const next = clone(state);
    let gain = 0;
    if (command.type === 'explore') {
      let x = next.rng;
      x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
      next.rng = x >>> 0;
      gain = 1 + next.rng % 3;
      next.energy -= 1;
      next.coins += gain;
    } else next.energy = Math.min(5, next.energy + 2);
    next.turn += 1; next.revision += 1;
    const receipt = { id: command.id, action: command.type, revision: next.revision, gain };
    next.receipts.push(receipt);
    return { state: next, receipt, duplicate: false };
  }
  function publicState(s) {
    validateState(s);
    return { revision: s.revision, turn: s.turn, energy: s.energy, coins: s.coins,
      receipts: clone(s.receipts.slice(-5)) };
  }
  function facts(s, receipt) {
    return { turn: receipt.revision, action: receipt.action, gainedCoins: receipt.gain,
      energy: s.energy, coins: s.coins };
  }
  async function sha(value) {
    if (!G.crypto?.subtle) fail('CRYPTO_UNAVAILABLE', '当前环境不能校验存档');
    const bytes = await G.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
    return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
  }
  function uuid() { if (!G.crypto?.randomUUID) fail('CRYPTO_UNAVAILABLE'); return G.crypto.randomUUID(); }
  function validateLedger(rows) {
    if (!Array.isArray(rows) || rows.length > MAX_RECORDS) fail('INVALID_SAVE', '请求台账过大');
    const seen = new Set();
    rows.forEach(r => {
      if (!plain(r) || !id(r.id) || !id(r.receiptId) || !id(r.epoch) || seen.has(r.id) ||
          !integer(r.revision, 1, MAX_RECORDS) || !['unknown', 'accepted', 'not-sent'].includes(r.status)) fail('INVALID_SAVE', '请求台账无效');
      seen.add(r.id);
    });
  }
  async function seal(record) {
    const body = clone(record); delete body.checksum;
    return { ...body, checksum: await sha(canonical(body)) };
  }
  async function decode(raw, scope) {
    if (typeof raw !== 'string' || raw.length > 1000000) fail('INVALID_SAVE', '存档过大或格式无效');
    let record;
    try { record = JSON.parse(raw); } catch (_) { fail('INVALID_SAVE', '存档无法解析，已保留原件'); }
    if (!plain(record) || record.format !== 'mmd-same-layer-save' || ![1, 2].includes(record.schema) ||
        record.scope !== scope || !id(record.epoch) || !integer(record.version, 0, 10000)) fail('INVALID_SAVE', '存档版本或所属会话不匹配');
    const expected = await seal(record);
    if (record.checksum !== expected.checksum) fail('CHECKSUM_MISMATCH', '存档校验失败，已保留原件');
    const migrated = clone(record);
    if (record.schema === 1) {
      if (!plain(migrated.state) || 'coins' in migrated.state) fail('INVALID_SAVE');
      migrated.state.coins = migrated.state.gold; delete migrated.state.gold;
      migrated.schema = 2;
    }
    validateState(migrated.state); validateLedger(migrated.ledger);
    return { record: migrated, migrated: record.schema !== 2 };
  }
  class SaveStore {
    constructor({ scope, storage, lock, isCurrent = () => true }) {
      this.scope = scopeKey(scope); this.key = 'MMD_SL_SAVE:' + encodeURIComponent(this.scope);
      this.storage = storage; this.lock = lock; this.isCurrent = isCurrent;
    }
    check() { if (!this.isCurrent()) fail('SCOPE_CHANGED', '会话已切换，旧操作已停止'); }
    async exclusive(fn) {
      this.check();
      if (typeof this.lock !== 'function') fail('LOCK_UNAVAILABLE', '当前环境缺少安全写入锁，不能保存游戏');
      return this.lock(this.key, async () => { this.check(); return fn(); });
    }
    async write(record) {
      this.check();
      if (!integer(record.version, 0, 10000)) fail('SAVE_LIMIT', '示例存档已达操作上限，请导出进度');
      const signed = await seal(record); this.check();
      const raw = canonical(signed);
      if (raw.length > 1000000) fail('SAVE_LIMIT', '存档已达示例容量上限');
      try {
        this.storage.setItem(this.key, raw);
        if (this.storage.getItem(this.key) !== raw) fail('SAVE_UNCONFIRMED');
      } catch (e) { fail('SAVE_FAILED', '保存未得到确认：' + e.message); }
      return signed;
    }
    async readInside() {
      this.check();
      let raw;
      try { raw = this.storage.getItem(this.key); } catch (_) { fail('SAVE_UNAVAILABLE', '宿主存储不可用'); }
      if (raw === null) return this.write({ format: 'mmd-same-layer-save', schema: 2, scope: this.scope,
        epoch: uuid(), version: 0, state: initial(), ledger: [] });
      const parsed = await decode(raw, this.scope); this.check();
      if (parsed.migrated) {
        const backup = this.key + ':schema1:' + (await sha(raw)).slice(0, 16);
        this.check();
        this.storage.setItem(backup, raw);
        if (this.storage.getItem(backup) !== raw) fail('BACKUP_FAILED');
        return this.write(parsed.record);
      }
      return parsed.record;
    }
    load() { return this.exclusive(() => this.readInside()); }
    action(command, epoch) {
      return this.exclusive(async () => {
        const current = await this.readInside();
        if (current.epoch !== epoch) fail('STALE_EPOCH', '已读档，请刷新页面中的进度');
        const result = reduce(current.state, command);
        if (result.duplicate) return current;
        return this.write({ ...current, state: result.state, version: current.version + 1 });
      });
    }
    async export() { return canonical(await this.load()); }
    import(raw, epoch) {
      return this.exclusive(async () => {
        const current = await this.readInside();
        if (current.epoch !== epoch) fail('STALE_EPOCH');
        const parsed = await decode(raw, this.scope); this.check();
        // Preserve the current generation ledger even when loading an older save.
        const rows = new Map(parsed.record.ledger.map(r => [r.id, r]));
        current.ledger.forEach(r => rows.set(r.id, r));
        const ledger = [...rows.values()]; validateLedger(ledger);
        const backup = this.key + ':before-import:' + current.epoch + ':' + current.version;
        const backupRaw = canonical(current);
        this.storage.setItem(backup, backupRaw);
        if (this.storage.getItem(backup) !== backupRaw) fail('BACKUP_FAILED');
        return this.write({ ...parsed.record, schema: 2, epoch: uuid(), ledger, version: current.version + 1 });
      });
    }
    reserveNarration({ id: requestId, receiptId, epoch, expectedRevision }) {
      return this.exclusive(async () => {
        const current = await this.readInside();
        if (current.epoch !== epoch || current.state.revision !== expectedRevision) fail('STALE_REVISION');
        if (!id(requestId)) fail('INVALID_REQUEST');
        const receipt = current.state.receipts.at(-1);
        if (!receipt || receipt.id !== receiptId) fail('STALE_RECEIPT');
        if (current.ledger.some(r => r.id === requestId || r.receiptId === receiptId)) fail('ALREADY_REQUESTED', '这次行动已提交过叙述请求，请查看原生记录');
        if (current.ledger.length >= MAX_RECORDS) fail('LEDGER_LIMIT');
        const entry = { id: requestId, receiptId, epoch, revision: expectedRevision, status: 'unknown' };
        await this.write({ ...current, version: current.version + 1, ledger: [...current.ledger, entry] });
        return facts(current.state, receipt);
      });
    }
    settleNarration(requestId, status, epoch) {
      if (!['accepted', 'not-sent', 'unknown'].includes(status)) fail('INVALID_REQUEST');
      return this.exclusive(async () => {
        const current = await this.readInside();
        if (current.epoch !== epoch) fail('STALE_EPOCH');
        const row = current.ledger.find(r => r.id === requestId);
        if (!row) fail('UNKNOWN_REQUEST');
        row.status = status;
        return this.write({ ...current, version: current.version + 1 });
      });
    }
  }
  G.MmdSameLayerCore = Object.freeze({ fail, canonical, clone, scopeKey, initial, reduce, validateState,
    publicState, sha, seal, decode, SaveStore, uuid });
})(globalThis);
