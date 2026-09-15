(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  let boot;
  try { boot = JSON.parse(window.name); } catch (_) { $('notice').textContent = '缺少宿主，请从卡片或本地预览入口打开。'; return; }
  let port = null, contextId = '', snapshot = null, busy = false, importCandidate = null, disposed = false;
  const pending = new Map(), blobs = new Set();
  function say(text) { $('notice').textContent = text; }
  function transmit(value) { port.postMessage({ protocol: 'mmd-sl/1', buildId: boot.buildId, nonce: boot.nonce, contextId, ...value }); }
  function call(method, params = {}) {
    if (!port || !contextId || disposed) return Promise.reject(new Error('尚未连接宿主'));
    const id = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id); reject(new Error('结果尚未确认，请查看原生记录或重新读取进度；不会自动重试。'));
      }, 16000);
      pending.set(id, { resolve, reject, timer }); transmit({ type: 'request', id, method, params });
    });
  }
  function rejectPending(message) { pending.forEach(p => { clearTimeout(p.timer); p.reject(new Error(message)); }); pending.clear(); }
  function render() {
    if (!snapshot) return;
    modelUI?.render(snapshot.native, busy);
    featureUI?.render(snapshot.native, busy);
    $('mode').textContent = snapshot.localPreview ? '本地演示' : 'MMD';
    $('send').disabled = busy || snapshot.native.capabilities.sendMessage?.available !== true;
    const game = snapshot.game;
    $('game-panel').hidden = !snapshot.engine || globalThis.MmdSameLayerUIConfig?.modules?.game === false;
    $('game-error').textContent = snapshot.gameError || '';
    for (const field of ['turn', 'energy', 'coins']) $(field).textContent = game ? game[field] : '—';
    for (const name of ['explore', 'rest', 'export', 'import']) $(name).disabled = busy || !game;
    $('explore').disabled = busy || !game || game.energy < 1;
    const latest = game?.receipts.at(-1);
    $('narrate').disabled = busy || !latest || !snapshot.native.capabilities.sendMessage?.available ||
      game.ledger.some(r => r.receiptId === latest.id);
    $('ledger').textContent = game?.ledger.some(r => r.status === 'unknown') ? '有一次叙述提交尚未确认，请查看原生聊天记录。' : '';
    $('receipts').replaceChildren(...(game?.receipts || []).map(r => {
      const li = document.createElement('li');
      li.textContent = '第 ' + r.revision + ' 回合：' + (r.action === 'rest' ? '休息，恢复体力' : '探索，获得 ' + r.gain + ' 枚金币'); return li;
    }));

  }
  async function act(fn) {
    if (busy) return; busy = true; render();
    try { await fn(); } catch (e) { say(e.message); }
    finally { busy = false; render(); }
  }
  function connect(event) {
    const m = event.data;
    if (port || event.source !== window.parent || event.origin !== boot.parentOrigin ||
        !m || m.protocol !== 'mmd-sl/1' || m.type !== 'connect' || m.buildId !== boot.buildId ||
        m.nonce !== boot.nonce || event.ports.length !== 1) return;
    port = event.ports[0]; window.removeEventListener('message', connect);
    port.onmessage = e => {
      const value = e.data;
      if (!value || value.protocol !== 'mmd-sl/1') return;
      if (value.type === 'snapshot') {
        if (contextId && contextId !== value.contextId) { rejectPending('会话已切换'); featureUI?.reset(); importCandidate = null; $('confirm').close(); }
        contextId = value.contextId; snapshot = value.snapshot; render();
        if ($('notice').textContent.includes('等待宿主')) say(snapshot.localPreview ? '本地模拟已连接，所有模型回复均为模拟内容。' : '已连接。原生功能可从顶部返回。');
      } else if (value.contextId === contextId && value.type === 'notice') say(value.text);
      else if (value.contextId === contextId && value.type === 'result') {
        const entry = pending.get(value.id); if (!entry) return;
        clearTimeout(entry.timer); pending.delete(value.id);
        value.ok ? entry.resolve(value.result) : entry.reject(new Error(value.error));
      }
    };
    port.start(); transmit({ type: 'ready' });
  }
  const modelUI = globalThis.MmdSameLayerUIConfig?.modules?.models === false ? null : globalThis.MmdSameLayerModelUI?.mount({ call, act, say });
  const featureUI = globalThis.MmdSameLayerFeatureUI?.mount({ call, act, say });
  window.addEventListener('message', connect);
  $('send').onclick = () => act(async () => {
    const text = $('text').value;
    try { await call('native.invoke', { action: 'sendMessage', payload: { text } }); }
    catch (error) { await call('snapshot').catch(() => {}); throw error; }
    $('text').value = ''; say('已提交发送操作，正在等待 MMD 更新。');
  });
  for (const type of ['explore', 'rest']) $(type).onclick = () => act(async () => {
    const game = snapshot.game;
    await call('game.action', { epoch: game.epoch, command: { id: crypto.randomUUID(), type, expectedRevision: game.revision } });
    say('游戏结果已保存。');
  });
  $('narrate').onclick = () => act(() => {
    const game = snapshot.game;
    return call('game.narrate', { id: crypto.randomUUID(), receiptId: game.receipts.at(-1).id,
      expectedRevision: game.revision, epoch: game.epoch });
  });
  $('export').onclick = () => act(async () => {
    const raw = await call('game.export'); const url = URL.createObjectURL(new Blob([raw], { type: 'application/json' }));
    blobs.add(url); const a = document.createElement('a'); a.href = url; a.download = '雾港进度.json'; a.click();
    setTimeout(() => { URL.revokeObjectURL(url); blobs.delete(url); }, 1000); say('进度文件已准备下载。');
  });
  $('import').onclick = () => { $('file').value = ''; $('file').click(); };
  $('file').onchange = async () => {
    const file = $('file').files[0]; if (!file || !snapshot.game) return;
    if (file.size > 1000000) { say('文件超过示例存档上限。'); return; }
    const token = contextId, epoch = snapshot.game.epoch;
    const raw = await file.text(); if (token !== contextId || disposed) return;
    importCandidate = { raw, epoch, token }; $('confirm').showModal();
  };
  $('cancel-import').onclick = () => { importCandidate = null; $('confirm').close(); };
  $('confirm-import').onclick = () => {
    const candidate = importCandidate; importCandidate = null; $('confirm').close();
    if (!candidate || candidate.token !== contextId) return;
    act(async () => { await call('game.import', candidate); say('进度已恢复，恢复前的本地备份已保留。'); });
  };
  window.addEventListener('pagehide', () => {
    disposed = true; featureUI?.dispose(); modelUI?.dispose(); rejectPending('页面已关闭'); port?.close();
    blobs.forEach(URL.revokeObjectURL); blobs.clear(); window.removeEventListener('message', connect);
  }, { once: true });
})();
