/* Original projection for caller-owned NativeBridge feature actions. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore, A = G.MmdSameLayerActions;
  function create(bridge, config = {}) {
    const revisions = A.revisions(); let epoch = 0, active = false, stopped = false;
    let raw = {}, state = {}; const pending = new Map();
    const allowed = new Set(config.allowedActions || A.actions);
    function capture() {
      raw = bridge.getSnapshot() || {};
      const source = { ...raw, messages: { items: (raw.messages || []).map(m => ({ ...m, fingerprint: m.targetFingerprint || '' })) },
        composer: { text: '', available: bridge.getCapabilities()?.setInputText?.available === true }, navigation: {} };
      state = Object.fromEntries(Object.entries(A.schemas).map(([key, shape]) => {
        const value = A.project(shape, source[key]);
        if (key === 'composer') { value.text = null; value.readable = false; }
        if (key === 'navigation') { value.favorite = null; value.evidence = 'unknown'; }
        if (key === 'conversationPanel') for (const item of value.conversations) item.available = true;
        const identity = key === 'messages' ? (raw.messages || []).map(m => [m.id, m.targetFingerprint, m.nativeIndex]) :
          key === 'instructionSelector' ? raw.instructionSelector?.revision : '';
        return [key, revisions.stamp(key, value, identity || '')];
      })); return state;
    }
    function supported(action) {
      return allowed.has(action) && bridge.getCapabilities()?.[action]?.available === true &&
        (!bridge.getRegisteredActions || bridge.getRegisteredActions().includes(action));
    }
    function validTarget(action, p, s) {
      if (p.messageId) {
        const rows = s.messages.items.filter(m => m.id === p.messageId); if (rows.length !== 1) C.fail('STALE_TARGET');
        const row = rows[0];
        const kind = { openEditMessage: 'edit', regenerateMessage: 'regenerate', startNewStoryFromMessage: 'startNewStory' }[action];
        if (kind && !row.capabilities[kind]) C.fail('NOT_AVAILABLE');
        if (action === 'submitEditMessage' && s.editPanel.messageId !== p.messageId) C.fail('STALE_TARGET');
        return C.canonical([row.id, row.text, row.fingerprint, row.index]);
      }
      if (p.conversationId) {
        const rows = s.conversationPanel.conversations.filter(x => x.id === p.conversationId && x.fingerprint === p.fingerprint && x.index === p.index);
        if (rows.length !== 1 || s.conversationPanel.conversations.filter(x => x.fingerprint === p.fingerprint).length !== 1) C.fail('STALE_TARGET');
        if (['requestDeleteConversation', 'deleteConversation'].includes(action) && (!rows[0].capabilities.delete || rows[0].current)) C.fail('NOT_AVAILABLE');
        return C.canonical(rows[0]);
      }
      const lookups = { applyEditTransform: [s.editPanel.transforms, p.transformId], activateMoreMenuItem: [s.moreMenu.items, p.itemId],
        setPersonaMode: [s.personaPanel.modes, p.modeId], setPersonaGender: [s.personaPanel.genderChoices, p.genderId],
        setSupplementPosition: [s.supplementPanel.picker.choices, p.choiceId], applyInstruction: [s.instructionSelector.instructions, p.instructionId] };
      if (lookups[action]) {
        const [rows, id] = lookups[action], match = rows.filter(x => x.id === id);
        if (match.length !== 1 || match[0].disabled || match[0].destructive) C.fail('STALE_TARGET');
        if (action === 'activateMoreMenuItem' && (!match[0].available || !['newChat','background','customInstructions','persona','supplement','chatSettings','tutorial'].includes(match[0].kind))) C.fail('NOT_AVAILABLE');
        if (action === 'applyInstruction' && (match[0].fingerprint !== p.fingerprint || match[0].index !== p.index || match[0].label !== p.label)) C.fail('STALE_TARGET');
      }
      return '';
    }
    function resultData(action, result) {
      const data = result?.data && typeof result.data === 'object' ? result.data : {};
      const safe = { phase: typeof data.phase === 'string' ? data.phase.slice(0, 100) : 'dispatched' };
      for (const key of ['messageId', 'conversationId', 'text', 'name', 'identity', 'title', 'link', 'itemId', 'kind', 'instructionId', 'label'])
        if (typeof data[key] === 'string') safe[key] = data[key].slice(0, 100000);
      if (data.confirmation) safe.confirmation = A.project({ messageId: v => typeof v === 'string' ? v : '',
        conversationId: v => typeof v === 'string' ? v : '', fingerprint: v => typeof v === 'string' ? v : '',
        index: v => Number.isSafeInteger(v) ? v : 0, confirmationToken: v => typeof v === 'string' ? v : '',
        prompt: v => typeof v === 'string' ? v.slice(0, 6000) : '' }, data.confirmation);
      return safe;
    }
    return {
      snapshot: () => ({ enabled: true, ...capture() }),
      capabilities() { return Object.fromEntries(A.actions.map(action => [action, { available: !active && !stopped && supported(action), reason: '需已注册的外部原生处理器、有效目标和最新快照' }])); },
      async invoke(action, p = {}, options = {}) {
        A.validate(action, p); if (active || stopped || !supported(action)) C.fail('NOT_AVAILABLE');
        options.check?.(); const s = capture(), group = A.groupFor[action];
        if (!A.rootActions.has(action) && p.revision !== s[group].revision) C.fail('STALE_VIEW');
        const signature = validTarget(action, p, s), generation = epoch;
        const check = () => { if (generation !== epoch || stopped) C.fail('CONTEXT_CHANGED'); options.check?.(); };
        const request = C.clone(p); delete request.revision;
        if (action === 'applyInstruction') request.revision = raw.instructionSelector.revision;
        if (action === 'rollbackMessage' && !p.confirmationToken) {
          const token = C.uuid(); pending.set(action, { signature, token, expires: Date.now() + 30000 });
          return { ok: true, action, accepted: false, completed: 'unknown', persisted: 'unknown', data: { phase: 'confirmation-required',
            confirmation: { messageId: p.messageId, confirmationToken: token, prompt: '回溯会删除目标消息下方的消息，确认继续？' } } };
        }
        if (p.confirmationToken) {
          const key = action === 'deleteConversation' ? 'requestDeleteConversation' : action;
          const saved = pending.get(key); pending.delete(key);
          if (!saved || saved.token !== p.confirmationToken || saved.signature !== signature || saved.expires < Date.now()) C.fail('CONFIRMATION_EXPIRED');
          if (action === 'rollbackMessage') delete request.confirmationToken;
        }
        active = true;
        try {
          check(); const result = await bridge.invoke(action, request); check();
          if (!result?.ok) C.fail(result?.error?.code || 'NATIVE_FAILED', result?.error?.message || '原生操作未成功');
          const data = resultData(action, result);
          if (data.phase === 'confirmation-required') {
            if (!['deleteMessage', 'requestDeleteConversation'].includes(action) || !data.confirmation?.confirmationToken ||
              (p.messageId && data.confirmation.messageId !== p.messageId) ||
              (p.conversationId && (data.confirmation.conversationId !== p.conversationId || data.confirmation.fingerprint !== p.fingerprint || data.confirmation.index !== p.index))) C.fail('INVALID_RESULT');
            pending.set(action, { signature, token: data.confirmation.confirmationToken, expires: Date.now() + 30000 });
          }
          if (bridge.refresh) await bridge.refresh(); check();
          return { ok: true, action, accepted: data.phase !== 'confirmation-required', completed: 'unknown', persisted: 'unknown', data };
        } finally { if (generation === epoch) active = false; }
      },
      cancel() { epoch++; active = false; revisions.clear(); pending.clear(); },
      destroy() { stopped = true; this.cancel(); }
    };
  }
  G.MmdSameLayerProvidedActions = Object.freeze({ create });
})(globalThis);
