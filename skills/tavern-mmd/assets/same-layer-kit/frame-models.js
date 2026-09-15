/* Reusable Frame-only model controls. All content is text, never native HTML. */
(function (G) {
  'use strict';
  function mount({ call, act, say }) {
    const element = (tag, name, value) => { const el = document.createElement(tag); if (name) el.className = name; if (value) el.textContent = value; return el; };
    const toolbar = element('div', 'sl-model-toolbar'), trigger = element('button', 'secondary', '模型');
    trigger.id = 'models-open'; trigger.type = 'button'; trigger.disabled = true;
    toolbar.append(trigger); (document.getElementById('models-slot') || document.querySelector('header') || document.body).append(toolbar);
    const dialog = element('dialog', 'sl-model-dialog'); dialog.id = 'models-dialog';
    const heading = element('h2', '', '模型'), info = element('p', 'muted'), content = element('div', 'sl-model-content');
    info.id = 'models-notice'; info.setAttribute('role', 'status');
    const footer = element('div', 'sl-model-actions'), refresh = element('button', 'secondary', '重新读取列表');
    refresh.id = 'models-refresh';
    const close = element('button', 'secondary', '关闭'), native = element('button', 'secondary', '返回 MMD');
    close.id = 'models-close'; native.id = 'models-native';
    footer.append(refresh, close, native); dialog.append(heading, info, content, footer); document.body.append(dialog);
    const style = element('style');
    style.textContent = '.sl-model-toolbar{margin:10px 0 4px}.sl-model-dialog{width:min(680px,92vw);max-height:88vh;padding:20px;overflow:auto}.sl-model-dialog h2{margin:0 0 12px}.sl-model-dialog button{white-space:normal}.sl-model-actions,.sl-model-filters,.sl-model-choices{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.sl-model-card{border:1px solid #d5dfd7;border-radius:12px;padding:14px;margin:12px 0}.sl-model-card h3{font-size:16px;margin:0 0 8px}.sl-model-card p{margin:6px 0;overflow-wrap:anywhere}.sl-model-card[aria-current=true]{border:2px solid #216165}.sl-model-dialog [aria-pressed=true]{outline:2px solid #216165;outline-offset:2px}.sl-model-switch{display:flex;align-items:center;gap:8px}.sl-model-switch input{width:22px;height:22px}.sl-model-selected{font-weight:bold;color:#216165}.sl-model-dialog #models-notice{min-height:24px}.sl-model-description{line-height:1.5;font-size:13px;color:#5b7167}@media(max-width:500px){.sl-model-dialog{padding:16px}.sl-model-card{padding:12px}}';
    document.head.append(style);
    let state = null, capabilities = {}, busy = false, signature = '';
    const available = action => !busy && capabilities[action]?.available === true;
    const message = text => { info.textContent = text; say(text); };
    async function invoke(action, payload = {}) {
      const result = await call('native.invoke', { action, payload });
      const labels = { opened: '模型列表已读取。', closed: '模型列表已关闭。', filtered: '已切换分类。',
        'selection-observed': '已在原生页面确认模型选择。', 'selection-unconfirmed': '切换结果尚未确认，请重新读取列表或返回 MMD 核对。',
        'configuration-opened': '模型设置已读取。', 'setting-observed': '设置项已更新，可点击“提交设置”。',
        'configuration-submitted': '已提交原生设置操作。', 'configuration-closed': '已关闭模型设置。' };
      message(labels[result.data?.phase] || '原生操作已返回，请核对显示状态。');
      return result;
    }
    function operate(action, payload, after) {
      act(async () => { try { const result = await invoke(action, payload); after?.(result); }
        catch (error) { info.textContent = error.message; throw error; } });
    }
    function button(label, action, payload, after, id) {
      const b = element('button', 'secondary', label); b.type = 'button'; if (id) b.id = id;
      b.disabled = !available(action); b.onclick = () => operate(action, payload, after); return b;
    }
    function render(nativeState, isBusy) {
      state = nativeState.models || null; capabilities = nativeState.capabilities || {}; busy = isBusy;
      toolbar.hidden = !state?.enabled;
      if (!state?.enabled) { if (dialog.open) dialog.close(); return; }
      trigger.textContent = '模型 · ' + (state.current?.name || '选择模型');
      trigger.disabled = !available('openModelSettings');
      refresh.disabled = !available('openModelSettings'); close.disabled = busy;
      const key = JSON.stringify([state, capabilities, busy]);
      if (signature === key) return; signature = key;
      const scroll = dialog.scrollTop; content.replaceChildren();
      const cfg = state.modelConfiguration, panel = state.modelPanel;
      heading.textContent = cfg.open ? (cfg.modelName || '模型设置') : '选择模型';
      if (state.issue) content.append(element('p', 'sl-model-description', state.issue));
      if (cfg.open) {
        content.append(element('p', 'muted', cfg.energyLabel));
        for (const control of cfg.controls) {
          const card = element('section', 'sl-model-card');
          card.append(element('h3', '', control.label || '设置项'), element('p', 'sl-model-description', control.description));
          if (control.type === 'toggle') {
            const label = element('label', 'sl-model-switch'), input = element('input'); input.type = 'checkbox';
            input.checked = control.value === true; input.disabled = !available('setModelSetting') || control.available === false;
            input.setAttribute('aria-label', control.label); input.dataset.modelControl = control.id;
            input.onchange = () => operate('setModelSetting', { revision: cfg.revision, controlId: control.id, value: input.checked });
            label.append(input, element('span', '', control.value ? '已开启' : '已关闭')); card.append(label);
          } else {
            const options = element('div', 'sl-model-choices');
            for (const choice of control.choices) {
              const b = button(choice.label, 'setModelSetting', { revision: cfg.revision, controlId: control.id, choiceId: choice.id });
              b.disabled ||= choice.available === false; b.setAttribute('aria-pressed', String(choice.selected)); b.dataset.modelChoice = choice.id; options.append(b);
            }
            card.append(options);
          }
          content.append(card);
        }
        const row = element('div', 'sl-model-actions');
        row.append(button('提交设置', 'submitModelConfiguration', { revision: cfg.revision }, null, 'models-save-settings'),
          button('关闭设置', 'closeModelConfiguration', { revision: cfg.revision }, null, 'models-close-settings'));
        content.append(row);
      } else if (panel.open) {
        const filters = element('div', 'sl-model-filters');
        for (const filter of panel.filters) {
          const b = button(filter.label, 'selectModelFilter', { revision: panel.revision, filterId: filter.id });
          b.disabled ||= filter.available === false; b.setAttribute('aria-pressed', String(filter.active)); b.dataset.modelFilter = filter.id; filters.append(b);
        }
        content.append(filters);
        if (panel.loading || !panel.models.length) content.append(element('p', 'muted', '模型列表尚未加载，可稍后重新读取。'));
        for (const model of panel.models) {
          const card = element('article', 'sl-model-card'); card.dataset.modelId = model.id; card.setAttribute('aria-current', String(model.selected));
          card.append(element('h3', '', model.name), element('p', 'sl-model-description', model.description));
          card.append(element('p', 'muted', [model.batteryLabel, model.permission, model.successRate].filter(Boolean).join(' · ')));
          if (model.selected) card.append(element('p', 'sl-model-selected', '当前选择'));
          if (model.reason) card.append(element('p', 'muted', model.reason));
          const row = element('div', 'sl-model-actions');
          const select = button('使用此模型', 'selectModel', { revision: panel.revision, modelId: model.id }, result => { if (result.data?.phase === 'selection-observed') dialog.close(); });
          select.disabled ||= model.available === false; select.dataset.modelSelect = model.id;
          const settings = button('模型设置', 'openModelConfiguration', { revision: panel.revision, modelId: model.id });
          settings.disabled ||= !model.canConfigure; settings.dataset.modelSettings = model.id;
          row.append(select, settings); card.append(row); content.append(card);
        }
      } else content.append(element('p', 'muted', busy ? '正在等待原生模型页面……' : '模型列表已关闭，可重新读取。'));
      dialog.scrollTop = scroll;
    }
    trigger.onclick = () => { if (!dialog.open) dialog.showModal(); info.textContent = '正在读取模型列表……'; operate('openModelSettings'); };
    refresh.onclick = () => operate('openModelSettings');
    function closeDialog() {
      if (busy) return;
      act(async () => {
        try {
          if (state?.modelConfiguration.open && capabilities.closeModelConfiguration?.available)
            await invoke('closeModelConfiguration', { revision: state.modelConfiguration.revision });
          if (state?.modelPanel.open && capabilities.closeModelSettings?.available)
            await invoke('closeModelSettings', { revision: state.modelPanel.revision });
          dialog.close();
        } catch (error) { info.textContent = error.message; throw error; }
      });
    }
    close.onclick = closeDialog; dialog.addEventListener('cancel', e => { e.preventDefault(); closeDialog(); });
    native.onclick = () => { call('ui.native').catch(error => message(error.message)); };
    return { render, dispose() { dialog.remove(); toolbar.remove(); style.remove(); } };
  }
  G.MmdSameLayerModelUI = Object.freeze({ mount });
})(globalThis);
