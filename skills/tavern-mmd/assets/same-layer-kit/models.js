/* Original old-MMD model adapter. DOM selectors are observed integration facts,
   not a public SDK. No upstream implementation or backend endpoints are bundled. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore;
  const actions = Object.freeze(['openModelSettings', 'closeModelSettings', 'selectModelFilter', 'selectModel',
    'openModelConfiguration', 'setModelSetting', 'submitModelConfiguration', 'closeModelConfiguration']);
  const S = Object.freeze({ entry: '.mind-type', icon: '.icon-change', list: '.model-switch-scope',
    rows: '.model-list .model-item', filters: '.model-filter-tab', title: '.model-title', description: '.model-intro',
    cost: '.model-battery', permission: '.model-perm', success: '.model-success-rate .success-badge',
    settingsIcon: 'img[src*="ico_setting2_dark.png"]', config: '.model-setting-scope',
    tokenCard: '.mp-card', tokenChoice: '.mp-token-btn', presetCard: '.mp-preset-card', presetChoice: '.mp-preset-item',
    switches: '.mp-switch-row', switchButton: '.u-switch', switchOn: '.u-switch__node--on',
    configClose: '.mp-close', configSave: '.bottom > .btn', listClose: '.u-popup__content__close' });
  const emptyPanel = () => ({ open: false, title: '', revision: '', filters: [], models: [], loading: false });
  const emptyConfiguration = () => ({ open: false, title: '', modelName: '', energyLabel: '', revision: '', controls: [] });
  const empty = () => ({ enabled: false, busy: false, issue: '', current: { name: '', evidence: 'unknown' },
    modelPanel: emptyPanel(), modelConfiguration: emptyConfiguration() });
  function disabled() {
    return { snapshot: empty, capabilities: () => ({}), cancel() {}, destroy() {},
      async invoke() { C.fail('NOT_AVAILABLE', '本作品未启用模型模块'); } };
  }

  function dom(document, config = {}) {
    if (config.models === false) return disabled();
    const view = document.defaultView;
    const ids = new WeakMap(); let targets = new Map(), active = null, stopped = false;
    let previousList = '', previousConfig = '', listRevision = '', configRevision = '';
    let current = { name: '', evidence: 'unknown' };
    const text = el => (el?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 3000);
    function visible(el) {
      if (!el?.isConnected || !el.getClientRects().length) return false;
      const style = view.getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    }
    const enabled = el => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true' && view.getComputedStyle(el).pointerEvents !== 'none';
    const all = (root, selector) => [...(root?.querySelectorAll(selector) || [])].filter(visible);
    function one(root, selector) { const rows = all(root, selector); return rows.length === 1 ? rows[0] : null; }
    function entry() {
      const rows = all(document, S.entry).filter(el => el.querySelector(S.icon));
      return rows.length === 1 ? rows[0] : null;
    }
    function entryName() {
      const el = entry(); if (!el) return '';
      const copy = el.cloneNode(true); copy.querySelectorAll(S.icon).forEach(icon => icon.remove());
      return text(copy);
    }
    function mark(el, kind) {
      if (!ids.has(el)) ids.set(el, C.uuid());
      const id = ids.get(el); targets.set(id, { el, kind }); return id;
    }
    function closeList(panel) {
      return one(panel?.closest('.u-popup__content') || panel?.parentElement, S.listClose);
    }
    function capture() {
      targets = new Map();
      const panels = all(document, S.list), configurations = all(document, S.config);
      const panel = panels.length === 1 ? panels[0] : null;
      const setting = configurations.length === 1 ? configurations[0] : null;
      let issue = panels.length > 1 || configurations.length > 1 ? '原生面板存在多个候选，请返回 MMD 处理。' : '';
      const list = emptyPanel(), configuration = emptyConfiguration();
      const displayedName = entryName();
      if (displayedName) current = { name: displayedName, evidence: 'native-entry' };
      if (panel) {
        list.open = true; list.title = text(panel.querySelector('.title')) || '选择模型';
        list.filters = all(panel, S.filters).map(el => ({ id: mark(el, 'filter'), label: text(el), active: el.classList.contains('active'), available: enabled(el) }));
        list.models = all(panel, S.rows).map(el => ({ id: mark(el, 'model'), name: text(el.querySelector(S.title)),
          description: text(el.querySelector(S.description)), batteryLabel: text(el.querySelector(S.cost)),
          permission: text(el.querySelector(S.permission)), successRate: text(el.querySelector(S.success)),
          selected: el.classList.contains('model-item-active'), available: enabled(el),
          canConfigure: enabled(one(el, S.settingsIcon)) }));
        const counts = new Map();
        list.models.forEach(row => { const key = C.canonical([row.name, row.description, row.batteryLabel]); counts.set(key, (counts.get(key) || 0) + 1); });
        list.models.forEach(row => { if (!row.name || counts.get(C.canonical([row.name, row.description, row.batteryLabel])) > 1) {
          row.available = row.canConfigure = false; row.reason = '模型条目不唯一或缺少名称';
        } });
        list.loading = list.models.length === 0;
        const selected = list.models.filter(row => row.selected);
        if (selected.length === 1) current = { name: selected[0].name, evidence: 'native-list' };
      }
      if (setting) {
        configuration.open = true; configuration.title = text(setting.querySelector('.mp-title')) || '模型设置';
        configuration.modelName = text(setting.querySelector('.mp-model-name'));
        configuration.energyLabel = text(setting.querySelector('.mp-energy-pill'));
        const controls = [];
        const cards = new Set([...all(setting, S.tokenCard).filter(el => el.querySelector(S.tokenChoice)), ...all(setting, S.presetCard)]);
        for (const card of cards) {
          const preset = card.matches(S.presetCard), choices = all(card, preset ? S.presetChoice : S.tokenChoice);
          controls.push({ id: mark(card, 'choice-control'), type: 'choice', label: text(card.querySelector('.mp-card-title')),
            description: text(card.querySelector('.mp-card-hint')), value: null,
            choices: choices.map(el => ({ id: mark(el, 'choice'), label: text(el), selected: el.classList.contains('selected'), available: enabled(el) })) });
        }
        for (const row of all(setting, S.switches)) {
          const button = one(row, S.switchButton);
          if (!button) continue;
          controls.push({ id: mark(button, 'toggle'), type: 'toggle', label: text(row.querySelector('.mp-sw-title')),
            description: text(row.querySelector('.mp-sw-desc')), value: !!button.querySelector(S.switchOn),
            available: enabled(button), choices: [] });
        }
        configuration.controls = controls;
      }
      // Revision includes target identity and values, so a rerender invalidates an old click.
      const listKey = C.canonical(list), configKey = C.canonical(configuration);
      if (listKey !== previousList) { previousList = listKey; listRevision = C.uuid(); }
      if (configKey !== previousConfig) { previousConfig = configKey; configRevision = C.uuid(); }
      list.revision = listRevision; configuration.revision = configRevision;
      return { enabled: true, busy: !!active, issue, current: C.clone(current), modelPanel: list, modelConfiguration: configuration };
    }
    function capabilities() {
      const state = capture(), list = state.modelPanel, setting = state.modelConfiguration;
      const clear = !stopped && !active && !state.issue;
      const panel = one(document, S.list), cfg = one(document, S.config);
      const values = { openModelSettings: !setting.open && !!entry(),
        closeModelSettings: list.open && !setting.open && !!closeList(panel),
        selectModelFilter: list.open && !setting.open && list.filters.length > 0,
        selectModel: list.open && !setting.open && list.models.some(row => row.available),
        openModelConfiguration: list.open && !setting.open && list.models.some(row => row.canConfigure),
        setModelSetting: setting.open && setting.controls.length > 0,
        submitModelConfiguration: setting.open && !!one(cfg, S.configSave),
        closeModelConfiguration: setting.open && !!one(cfg, S.configClose) };
      return Object.fromEntries(actions.map(action => [action, { available: clear && !!values[action],
        reason: state.issue || (active ? '正在等待原生页面更新' : '需要对应原生模型入口或面板') }]));
    }
    function cancel() { active?.abort(); active = null; current = { name: '', evidence: 'unknown' };
      previousList = previousConfig = ''; listRevision = configRevision = C.uuid(); }
    async function invoke(action, payload = {}, options = {}) {
      if (!actions.includes(action) || !capabilities()[action]?.available) C.fail('NOT_AVAILABLE', '当前原生模型操作不可用');
      const controller = new AbortController(); active = controller;
      const deadline = Date.now() + (config.modelTimeoutMs || 8000);
      function check() {
        if (stopped || controller.signal.aborted) C.fail('CANCELLED', '模型操作已停止，请核对原生状态');
        options.check?.();
      }
      function click(el) { check(); if (!enabled(el)) C.fail('PLATFORM_CHANGED', '原生控件已变化');
        el.dispatchEvent(new view.MouseEvent('click', { bubbles: true, cancelable: true, composed: true })); }
      function wait(predicate, message) {
        return new Promise((resolve, reject) => {
          let timer;
          const finish = (error, value) => { clearTimeout(timer); controller.signal.removeEventListener('abort', abort); error ? reject(error) : resolve(value); };
          const abort = () => { const e = new Error('模型操作已停止'); e.code = 'CANCELLED'; finish(e); };
          function tick() {
            try { check(); const value = predicate(); if (value) return finish(null, value);
              if (Date.now() >= deadline) C.fail('TIMEOUT', message + '；请核对原生页面，不会自动重试');
              timer = setTimeout(tick, 50);
            } catch (error) { finish(error); }
          }
          controller.signal.addEventListener('abort', abort, { once: true }); tick();
        });
      }
      function listTarget(kind, id) {
        const state = capture();
        if (payload.revision !== state.modelPanel.revision) C.fail('STALE_TARGET', '模型列表已更新，请重新选择');
        const target = targets.get(id);
        if (!target || target.kind !== kind) C.fail('STALE_TARGET', '模型目标已失效');
        return { state, target: target.el };
      }
      let data;
      try {
        check();
        if (action === 'openModelSettings') {
          if (!one(document, S.list)) click(entry());
          await wait(() => capture().modelPanel.open, '模型列表未打开');
          await wait(() => capture().modelPanel.models.length > 0, '模型列表尚未加载');
          data = { phase: 'opened' };
        } else if (action === 'closeModelSettings') {
          if (payload.revision !== capture().modelPanel.revision) C.fail('STALE_TARGET', '模型列表已更新，请重新操作');
          click(closeList(one(document, S.list)));
          await wait(() => !capture().modelPanel.open, '模型列表未关闭');
          data = { phase: 'closed' };
        } else if (action === 'selectModelFilter') {
          const { state, target } = listTarget('filter', payload.filterId);
          const label = text(target);
          if (state.modelPanel.filters.filter(row => row.label === label).length !== 1) C.fail('STALE_TARGET', '模型分类不唯一');
          click(target);
          await wait(() => { const s = capture(); return s.modelPanel.filters.filter(row => row.label === label && row.active).length === 1; }, '模型分类未切换');
          data = { phase: 'filtered' };
        } else if (action === 'selectModel' || action === 'openModelConfiguration') {
          const { state, target } = listTarget('model', payload.modelId);
          const row = state.modelPanel.models.find(item => item.id === payload.modelId);
          if (!row?.available || (action === 'openModelConfiguration' && !row.canConfigure)) C.fail('NOT_AVAILABLE', '模型条目不可操作');
          if (action === 'openModelConfiguration') {
            const icon = one(target, S.settingsIcon); click(icon?.closest('uni-image') || icon);
            await wait(() => { const s = capture().modelConfiguration; return s.open && s.modelName === row.name; }, '匹配的模型设置未打开');
            data = { phase: 'configuration-opened' };
          } else {
            click(target);
            await wait(() => !capture().modelPanel.open, '模型选择面板未关闭');
            // A closed panel alone is not proof of a selected model.
            let verified = entryName() === row.name;
            if (!verified && entry()) {
              click(entry());
              await wait(() => capture().modelPanel.models.length > 0, '无法回读所选模型');
              const reread = capture().modelPanel.models;
              verified = reread.filter(item => item.selected).length === 1 && reread.some(item => item.selected && item.name === row.name && item.description === row.description && item.batteryLabel === row.batteryLabel);
              const close = closeList(one(document, S.list)); if (close) { click(close); await wait(() => !capture().modelPanel.open, '核对后模型面板未关闭'); }
            }
            current = verified ? { name: row.name, evidence: 'native-observed' } : { name: '', evidence: 'unknown' };
            data = { phase: verified ? 'selection-observed' : 'selection-unconfirmed', name: row.name };
          }
        } else {
          const state = capture(), cfg = state.modelConfiguration;
          if (payload.revision !== cfg.revision) C.fail('STALE_TARGET', '模型设置已更新，请重新操作');
          const panel = one(document, S.config);
          if (action === 'closeModelConfiguration' || action === 'submitModelConfiguration') {
            click(one(panel, action === 'closeModelConfiguration' ? S.configClose : S.configSave));
            await wait(() => !capture().modelConfiguration.open, '模型设置面板未关闭');
            data = { phase: action === 'closeModelConfiguration' ? 'configuration-closed' : 'configuration-submitted' };
          } else {
            const control = cfg.controls.find(row => row.id === payload.controlId), target = targets.get(payload.controlId);
            if (!control || !target) C.fail('STALE_TARGET', '设置项已变化');
            if (control.type === 'toggle') {
              if (typeof payload.value !== 'boolean') C.fail('INVALID_REQUEST', '开关需要明确的目标状态');
              if (control.value !== payload.value) click(target.el);
              await wait(() => capture().modelConfiguration.controls.some(row => row.id === control.id && row.value === payload.value), '开关状态未更新');
            } else {
              const choice = control.choices.find(row => row.id === payload.choiceId), option = targets.get(payload.choiceId);
              if (!choice?.available || option?.kind !== 'choice') C.fail('STALE_TARGET', '设置选项已变化');
              if (!choice.selected) click(option.el);
              await wait(() => capture().modelConfiguration.controls.some(row => row.id === control.id && row.choices.some(item => item.id === choice.id && item.selected)), '设置选项未更新');
            }
            data = { phase: 'setting-observed' };
          }
        }
        check(); return { ok: true, action, accepted: true, completed: 'unknown', persisted: 'unknown', data };
      } finally { if (active === controller) active = null; }
    }
    return { snapshot: capture, capabilities, cancel,
      destroy() { stopped = true; cancel(); },
      invoke };
  }

  function mock(config = {}) {
    if (config.models === false) return disabled();
    let state = empty(), sequence = 0;
    state.enabled = true; state.current = { name: '模拟·叙事', evidence: 'mock' };
    const revision = () => 'mock-models-' + (++sequence);
    const models = [
      { id: 'narration', name: '模拟·叙事', description: '本地演示模型，不连接真实服务', batteryLabel: '演示消耗 1', permission: '演示可用', successRate: '', selected: true, available: true, canConfigure: true, group: 'story' },
      { id: 'reasoning', name: '模拟·推理', description: '用于验证切换与设置的模拟选项', batteryLabel: '演示消耗 2', permission: '演示可用', successRate: '', selected: false, available: true, canConfigure: true, group: 'logic' }
    ];
    let filter = 'all', settingsFor = '', values = { narration: { tokens: 'short', memory: true }, reasoning: { tokens: 'long', memory: false } };
    function list() { return { open: true, title: '选择模型', revision: revision(), loading: false,
      filters: [{ id: 'all', label: '全部', active: filter === 'all' }, { id: 'story', label: '叙事', active: filter === 'story' }, { id: 'logic', label: '推理', active: filter === 'logic' }],
      models: models.filter(row => filter === 'all' || row.group === filter).map(({ group, ...row }) => row) }; }
    function configuration() { const value = values[settingsFor]; return { open: true, title: '模型设置', modelName: models.find(row => row.id === settingsFor).name,
      energyLabel: '本地设置演示', revision: revision(), controls: [
        { id: 'tokens', type: 'choice', label: '回复长度', description: '', value: null, choices: [{ id: 'short', label: '简短', selected: value.tokens === 'short', available: true }, { id: 'long', label: '详细', selected: value.tokens === 'long', available: true }] },
        { id: 'memory', type: 'toggle', label: '记忆辅助', description: '演示开关', value: value.memory, available: true, choices: [] }
      ] }; }
    function capabilities() {
      const l = state.modelPanel.open, c = state.modelConfiguration.open;
      const flags = [!c, l && !c, l && !c, l && !c, l && !c, c, c, c];
      return Object.fromEntries(actions.map((action, i) => [action, { available: flags[i], reason: '请先打开对应模型面板' }]));
    }
    return { snapshot: () => C.clone(state), capabilities,
      cancel() { state.modelPanel = emptyPanel(); state.modelConfiguration = emptyConfiguration(); }, destroy() {},
      async invoke(action, payload = {}, options = {}) {
        options.check?.();
        if (!capabilities()[action]?.available) C.fail('NOT_AVAILABLE');
        if (action !== 'openModelSettings' && payload.revision !== (state.modelConfiguration.open ? state.modelConfiguration.revision : state.modelPanel.revision)) C.fail('STALE_TARGET');
        let phase;
        if (action === 'openModelSettings') { state.modelPanel = list(); phase = 'opened'; }
        else if (action === 'closeModelSettings') { state.modelPanel = emptyPanel(); phase = 'closed'; }
        else if (action === 'selectModelFilter') { if (!['all', 'story', 'logic'].includes(payload.filterId)) C.fail('INVALID_REQUEST'); filter = payload.filterId; state.modelPanel = list(); phase = 'filtered'; }
        else if (action === 'selectModel' || action === 'openModelConfiguration') {
          const chosen = state.modelPanel.models.find(row => row.id === payload.modelId); if (!chosen) C.fail('STALE_TARGET');
          if (action === 'selectModel') { models.forEach(row => row.selected = row.id === chosen.id); state.current = { name: chosen.name, evidence: 'mock' }; state.modelPanel = emptyPanel(); phase = 'selection-observed'; }
          else { settingsFor = chosen.id; state.modelConfiguration = configuration(); phase = 'configuration-opened'; }
        } else if (action === 'setModelSetting') {
          if (payload.controlId === 'tokens' && ['short', 'long'].includes(payload.choiceId)) values[settingsFor].tokens = payload.choiceId;
          else if (payload.controlId === 'memory' && typeof payload.value === 'boolean') values[settingsFor].memory = payload.value;
          else C.fail('INVALID_REQUEST');
          state.modelConfiguration = configuration(); phase = 'setting-observed';
        } else { state.modelConfiguration = emptyConfiguration(); phase = action === 'submitModelConfiguration' ? 'configuration-submitted' : 'configuration-closed'; }
        return { ok: true, action, accepted: true, completed: 'unknown', persisted: 'unknown', data: { phase, name: state.current.name } };
      } };
  }
  G.MmdSameLayerModels = Object.freeze({ actions, dom, mock, disabled, empty });
})(globalThis);
