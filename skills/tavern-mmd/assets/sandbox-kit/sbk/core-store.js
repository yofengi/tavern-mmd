(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim || !SBK.state || !SBK.sdk || !SBK._coreKit) {
    (W.console && W.console.warn) && W.console.warn('[SBK] core-store.js loaded before core.js');
    return;
  }
  if (!SBK.claim('core-store')) return;

  var S = SBK.sdk;
  var S_save = S.save || null;
  var S_cache = S.cache || null;
  var deep = SBK._coreKit.deep;
  var has = Object.prototype.hasOwnProperty;
  var KEY = 'sbk-state';
  var mem = {};
  var dirty = {}, revision = 0;       // 本地已更新、远端尚未确认的 key → load 优先读本地
  var deadSave = false;
  var bucket = [];
  var LIMIT = 18, WIN = 60000;
  var pendingFull = null, pendingPatch = null, pendingKey = null, timer = null;
  var KEEP = /^_sbk/;

  function warn(msg, extra) { SBK.warn(msg, extra); }
  function own(o, k) { return has.call(o, k); }
  function okKey(k) { return typeof k === 'string' && k.length > 0 && k.length <= 64 && k.indexOf(':') < 0; }
  function allow() {
    var now = Date.now();
    while (bucket.length && now - bucket[0] > WIN) bucket.shift();
    if (bucket.length >= LIMIT) return false;
    bucket.push(now);
    return true;
  }
  function readRaw(key) {
    if (own(dirty, key)) {
      if (own(mem, key)) return mem[key];
      if (S_cache && typeof S_cache.get === 'function') {
        try { var local = S_cache.get(key); if (local !== undefined && local !== null) return local; } catch (e) {}
      }
      return null;                              // 本地 clear 的 tombstone，远端 remove 完成前不读旧档
    }
    if (!deadSave && S_save && typeof S_save.get === 'function') {
      try {
        var v = S_save.get(key);
        if (v !== undefined && v !== null) return v;
        return null;
      } catch (e) {
        deadSave = true;
        warn('save.get unavailable, fallback to cache', e && e.code);
      }
    }
    if (S_cache && typeof S_cache.get === 'function') {
      try {
        var c = S_cache.get(key);
        if (c !== undefined && c !== null) return c;
      } catch (e) {}
    }
    return own(mem, key) ? mem[key] : null;
  }
  function readMergeRaw(key) {
    if (own(mem, key)) return mem[key];
    if (S_cache && typeof S_cache.get === 'function') {
      try {
        var c = S_cache.get(key);
        if (c !== undefined && c !== null) return c;
      } catch (e) {}
    }
    return readRaw(key);
  }
  function writeRaw(key, str) {
    var rev = ++revision;
    dirty[key] = rev;
    mem[key] = str;
    if (S_cache && typeof S_cache.set === 'function') {
      try { S_cache.set(key, str); } catch (e) { warn('cache.set failed', e && e.code); }
    }
    if (deadSave || !S_save || typeof S_save.set !== 'function') return;
    if (!allow()) { warn('save.set throttled locally, kept in cache'); return; }
    try {
      var p = S_save.set(key, str);
      if (p && typeof p.then === 'function') {
        p.then(function () {
          // 只确认自己对应的版本；期间若又有新写，旧 promise 不能把新 dirty 清掉。
          if (dirty[key] === rev) delete dirty[key];
        }).catch(function (e) {
          var code = e && e.code;
          if (code === 'NOT_SUPPORTED' || code === 'HOST_DENIED') deadSave = true;
          warn('save.set rejected: ' + (code || 'unknown'));
        });
      }
    } catch (e) { warn('save.set threw', e && e.code); }
  }
  function docOf(raw) {
    var v = raw;
    if (typeof raw === 'string') {
      try { v = JSON.parse(raw); } catch (e) { return null; }
    }
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null;
  }
  function copyTop(src) {
    var out = Object.create ? Object.create(null) : {}, k;
    if (src) for (k in src) if (own(src, k)) out[k] = src[k];
    return out;
  }
  function flushStore() {
    if (timer) { try { W.clearTimeout(timer); } catch (e) {} }
    timer = null;
    var key = pendingKey || KEY, full = pendingFull, patch = pendingPatch;
    pendingKey = null;
    pendingFull = null;
    pendingPatch = null;
    if (full === null && !patch) return;

    var priorRaw = readMergeRaw(key), prior = docOf(priorRaw), parsed, doc, k;
    if (full !== null) {
      try { parsed = JSON.parse(full); } catch (e) { warn('store.save queued JSON became invalid'); return; }
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        if (patch) warn('store.merge skipped: pending store.save value is not an object');
        writeRaw(key, full);
        return;
      }
      doc = copyTop(parsed);
      if (prior) for (k in prior) if (own(prior, k) && KEEP.test(k) && !own(doc, k)) doc[k] = prior[k];
    } else {
      if (priorRaw !== null && !prior) {
        warn('store.merge skipped: existing document is not a JSON object');
        return;
      }
      doc = copyTop(prior);
    }
    if (patch) for (k in patch) if (own(patch, k)) doc[k] = patch[k];
    try { writeRaw(key, JSON.stringify(doc)); } catch (e) { warn('store flush stringify failed'); }
  }
  function armStore(key) {
    if (pendingKey && pendingKey !== key) flushStore();
    pendingKey = key;
    if (!timer) timer = W.setTimeout(flushStore, 800);
  }

  SBK.store = {
    key: function (k) {
      if (okKey(k)) {
        if (k !== KEY && (pendingFull !== null || pendingPatch)) flushStore();
        KEY = k;
      } else warn('bad save key ignored (need 1..64, no ":")', k);
      return KEY;
    },
    load: function () {
      try {
        var raw = readRaw(KEY);
        if (typeof raw !== 'string') return raw && typeof raw === 'object' ? deep(raw) : null;
        return JSON.parse(raw);
      } catch (e) {
        warn('store.load failed, returning null', e && (e.code || e.message));
        return null;
      }
    },
    save: function (obj) {
      var data = obj === undefined ? SBK.state.get() : obj;
      try { pendingFull = JSON.stringify(data); } catch (e) { warn('store.save stringify failed'); return; }
      armStore(KEY);
    },
    merge: function (partial) {
      var text, p, k;
      if (!partial || typeof partial !== 'object' || Array.isArray(partial)) {
        warn('store.merge needs a JSON object');
        return;
      }
      try { text = JSON.stringify(partial); p = JSON.parse(text); }
      catch (e) { warn('store.merge stringify failed'); return; }
      if (!pendingPatch) pendingPatch = Object.create ? Object.create(null) : {};
      for (k in p) if (own(p, k)) pendingPatch[k] = p[k];
      armStore(KEY);
    },
    clear: function () {
      if (timer) { try { W.clearTimeout(timer); } catch (e) {} }
      timer = null;
      pendingKey = null;
      pendingFull = null;
      pendingPatch = null;
      var key = KEY, rev = ++revision;
      dirty[key] = rev;
      delete mem[key];
      if (S_cache && typeof S_cache.remove === 'function') { try { S_cache.remove(key); } catch (e) {} }
      if (!deadSave && S_save && typeof S_save.remove === 'function') {
        try {
          var p = S_save.remove(key);
          if (p && p.then) p.then(function () { if (dirty[key] === rev) delete dirty[key]; })
            .catch(function (e) { warn('save.remove rejected', e && e.code); });
        } catch (e) { warn('save.remove threw', e && e.code); }
      }
    }
  };
  SBK.log('core-store ready');
})(typeof window !== 'undefined' ? window : globalThis);
