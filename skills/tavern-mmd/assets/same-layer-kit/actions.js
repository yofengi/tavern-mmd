/* Original shared contracts for the additional old-MMD native actions. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore;
  const groups = Object.freeze({
    composer: ['setInputText'], navigation: ['exit', 'openComments', 'toggleFavorite', 'refreshConversation'],
    messages: ['copyMessage', 'regenerateMessage', 'openEditMessage', 'deleteMessage', 'rollbackMessage', 'startNewStoryFromMessage'],
    editPanel: ['setEditText', 'applyEditTransform', 'submitEditMessage', 'cancelEditMessage'],
    sharePanel: ['openSharePanel', 'copyShareLink', 'closeSharePanel'],
    moreMenu: ['openMoreMenu', 'closeMoreMenu', 'activateMoreMenuItem', 'openTutorial', 'openBackgroundPanel', 'openCustomInstructions'],
    conversationPanel: ['openConversationPanel', 'selectConversation', 'renameConversation', 'requestDeleteConversation', 'deleteConversation', 'createConversation', 'closeConversationPanel'],
    personaPanel: ['openPersona', 'setPersonaMode', 'setPersonaName', 'setPersonaGender', 'setPersonaIdentity', 'submitPersona', 'closePersona'],
    supplementPanel: ['openSupplement', 'setSupplementText', 'openSupplementPositionPicker', 'setSupplementPosition', 'confirmSupplementPosition', 'cancelSupplementPosition', 'submitSupplement', 'closeSupplement'],
    instructionSelector: ['openPromptSelector', 'closePromptSelector', 'applyInstruction'],
    chatSettings: ['openChatSettings', 'closeChatSettings', 'submitChatSettings']
  });
  const actions = Object.freeze(Object.values(groups).flat());
  const groupFor = Object.freeze(Object.fromEntries(Object.entries(groups).flatMap(([key, names]) => names.map(name => [name, key]))));
  const rootActions = new Set(['exit', 'openComments', 'refreshConversation', 'openSharePanel', 'openMoreMenu',
    'openTutorial', 'openBackgroundPanel', 'openCustomInstructions', 'openConversationPanel', 'openPersona',
    'openSupplement', 'openPromptSelector', 'openChatSettings']);
  const required = {
    setInputText: ['text'], copyMessage: ['messageId'], regenerateMessage: ['messageId'], openEditMessage: ['messageId'],
    deleteMessage: ['messageId'], rollbackMessage: ['messageId'], startNewStoryFromMessage: ['messageId'],
    setEditText: ['text'], applyEditTransform: ['transformId'], submitEditMessage: ['messageId', 'text'],
    activateMoreMenuItem: ['itemId'], selectConversation: ['conversationId', 'fingerprint', 'index'],
    renameConversation: ['conversationId', 'fingerprint', 'index', 'title'], requestDeleteConversation: ['conversationId', 'fingerprint', 'index'],
    deleteConversation: ['conversationId', 'fingerprint', 'index', 'confirmationToken'],
    setPersonaMode: ['modeId'], setPersonaName: ['name'], setPersonaGender: ['genderId'], setPersonaIdentity: ['identity'],
    submitPersona: ['name', 'identity'], setSupplementText: ['text'], setSupplementPosition: ['choiceId'], submitSupplement: ['text'],
    applyInstruction: ['instructionId', 'fingerprint', 'label', 'index']
  };
  function validate(action, payload) {
    if (!actions.includes(action)) C.fail('NOT_AVAILABLE');
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) C.fail('INVALID_ARGUMENT');
    const fields = new Set([...(required[action] || []), 'revision']);
    if (['deleteMessage', 'rollbackMessage'].includes(action)) fields.add('confirmationToken');
    for (const key of Object.keys(payload)) if (!fields.has(key)) C.fail('INVALID_ARGUMENT', '未知动作参数：' + key);
    for (const key of required[action] || []) {
      if (key === 'index') { if (!Number.isSafeInteger(payload[key]) || payload[key] < 0) C.fail('INVALID_ARGUMENT', '无效目标位置'); }
      else if (typeof payload[key] !== 'string' || payload[key].length > 100000 ||
        (!['text', 'name', 'identity'].includes(key) && !payload[key].trim())) C.fail('INVALID_ARGUMENT', '无效参数：' + key);
    }
    if (!rootActions.has(action) && (typeof payload.revision !== 'string' || !payload.revision)) C.fail('STALE_VIEW', '请读取最新功能快照');
    if ('confirmationToken' in payload && (typeof payload.confirmationToken !== 'string' || !payload.confirmationToken)) C.fail('INVALID_ARGUMENT');
  }
  // Projection schemas intentionally contain only author-facing data, never native HTML or owner objects.
  const str = value => typeof value === 'string' ? value.slice(0, 100000) : '';
  const bool = value => value === true;
  const num = value => Number.isFinite(value) ? value : 0;
  const option = { id: str, label: str, selected: bool, disabled: bool, available: bool };
  const messageCaps = { copy: bool, edit: bool, delete: bool, regenerate: bool, rollback: bool, startNewStory: bool };
  const schemas = {
    composer: { text: str, available: bool }, navigation: { favorite: bool },
    messages: { items: [{ id: str, role: str, text: str, index: num, fingerprint: str, capabilities: messageCaps }] },
    editPanel: { open: bool, messageId: str, text: str, transforms: [option] },
    sharePanel: { open: bool, title: str, subtitle: str, link: str },
    moreMenu: { open: bool, items: [{ id: str, label: str, kind: str, icon: str, available: bool, destructive: bool }] },
    conversationPanel: { open: bool, title: str, currentConversationId: str, conversations: [{ id: str, fingerprint: str, index: num,
      title: str, preview: str, current: bool, available: bool, capabilities: { rename: bool, delete: bool } }] },
    personaPanel: { open: bool, title: str, modes: [option], currentModeId: str, name: str, maxLength: num, nameDisabled: bool,
      genderChoices: [option], selectedGenderId: str, identity: str, identityMaxLength: num, identityDisabled: bool, restriction: str },
    supplementPanel: { open: bool, title: str, text: str, maxLength: num, positionLabel: str, positionId: str,
      picker: { open: bool, choices: [option], pendingChoiceId: str } },
    instructionSelector: { open: bool, empty: bool, instructions: [{ id: str, label: str, fingerprint: str, index: num }] },
    chatSettings: { open: bool, title: str, empty: bool, controls: [{ id: str, label: str, description: str,
      options: [option], selectedOptionId: str, collapsed: bool }] },
    backgroundPanel: { open: bool, title: str }, customInstructionsPanel: { open: bool, title: str }
  };
  function project(schema, raw) {
    if (typeof schema === 'function') return schema(raw);
    if (Array.isArray(schema)) return (Array.isArray(raw) ? raw : []).slice(0, 200).filter(v => v && typeof v === 'object').map(v => project(schema[0], v));
    return Object.fromEntries(Object.entries(schema).map(([key, shape]) => [key, project(shape, raw?.[key])]));
  }
  function revisions() {
    const values = new Map(); let epoch = 0;
    return {
      stamp(key, data, identity = '') {
        const signature = C.canonical([epoch, data, identity]);
        const old = values.get(key);
        if (!old || old.signature !== signature) values.set(key, { signature, revision: C.uuid() });
        return { ...data, revision: values.get(key).revision };
      }, clear() { values.clear(); epoch++; }
    };
  }
  function serial(adapter, allowedActions) {
    const allowed = allowedActions ? new Set(allowedActions) : null;
    let active = null, epoch = 0, stopped = false;
    const cancel = adapter.cancel?.bind(adapter), destroy = adapter.destroy?.bind(adapter), invoke = adapter.invoke.bind(adapter), snapshot = adapter.snapshot.bind(adapter);
    adapter.snapshot = () => { const result = snapshot(); for (const [action, cap] of Object.entries(result.capabilities || {})) if (active || stopped || (allowed && !allowed.has(action))) {
      cap.available = false; cap.reason = stopped ? '桥接已关闭' : '正在处理原生操作';
    } return result; };
    adapter.invoke = async (action, payload, options = {}) => {
      if (stopped || active || (allowed && !allowed.has(action))) C.fail('NOT_AVAILABLE', '请等待当前原生操作完成');
      const token = {}; const generation = epoch; active = token;
      const check = () => { if (stopped || generation !== epoch) C.fail('CONTEXT_CHANGED'); options.check?.(); };
      try { check(); const result = await invoke(action, payload, { ...options, check }); check(); return result; }
      finally { if (active === token) active = null; }
    };
    adapter.cancel = () => { epoch++; active = null; cancel?.(); };
    adapter.destroy = () => { stopped = true; epoch++; active = null; destroy?.(); };
    return adapter;
  }
  G.MmdSameLayerActions = Object.freeze({ groups, actions, groupFor, rootActions, required, validate, schemas, project, revisions, serial });
})(globalThis);
