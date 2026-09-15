/* Model projection for a caller-owned NativeBridge instance. Original adapter. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore, M = G.MmdSameLayerModels;
  function create(bridge, config = {}) {
    if (config.models === false) return M.disabled();
    const allowed = new Set(config.allowedActions || M.actions);
    let active = false, epoch = 0, listKey = '', cfgKey = '', listRevision = '', cfgRevision = '';
    let current = { name: '', evidence: 'unknown' };
    const str = (value, max = 3000) => typeof value === 'string' ? value.slice(0,max) : '';
    const rows = value => Array.isArray(value) ? value.filter(row => row && typeof row === 'object').slice(0,200) : [];
    function can(action) {
      return allowed.has(action) && bridge.getCapabilities()[action]?.available === true &&
        (!bridge.getRegisteredActions || bridge.getRegisteredActions().includes(action));
    }
    function snapshot() {
      const raw = bridge.getSnapshot(), state = M.empty(); state.enabled = true; state.busy = active;
      const panel = raw.modelPanel || {}, cfg = raw.modelConfiguration || {};
      state.modelPanel = { open: panel.open === true, title: str(panel.title), revision: '',
        filters: rows(panel.filters).map(row => ({ id:str(row.id,160),label:str(row.label),active:row.active===true })),
        models: rows(panel.models).map(row => ({ id:str(row.id,160),name:str(row.name),description:str(row.description),
          batteryLabel:str(row.batteryLabel),permission:str(row.permission),successRate:str(row.successRate),
          selected:row.selected===true,available:!!row.id,canConfigure:!!row.id && can('openModelConfiguration') })),
        loading: panel.open === true && !rows(panel.models).length };
      state.modelConfiguration = { open:cfg.open===true,title:str(cfg.title),modelName:str(cfg.modelName),energyLabel:str(cfg.energyLabel),revision:'',
        controls:rows(cfg.controls).filter(row=>['choice','toggle'].includes(row.type)).map(row=>({id:str(row.id,160),type:row.type,label:str(row.label),
          description:str(row.description),value:row.type==='toggle'?row.value===true:null,available:true,
          choices:rows(row.choices).map(choice=>({id:str(choice.id,160),label:str(choice.label),selected:choice.selected===true,available:true}))})) };
      for (const row of state.modelPanel.models) if (!row.name || state.modelPanel.models.filter(item=>item.id===row.id).length!==1) row.available=row.canConfigure=false;
      const l=C.canonical(state.modelPanel), c=C.canonical(state.modelConfiguration);
      if (l!==listKey) {listKey=l;listRevision=C.uuid();} if(c!==cfgKey){cfgKey=c;cfgRevision=C.uuid();}
      state.modelPanel.revision=listRevision;state.modelConfiguration.revision=cfgRevision;
      const selected=state.modelPanel.models.filter(row=>row.selected);
      if(state.modelPanel.open&&selected.length===1)current={name:selected[0].name,evidence:'provided-snapshot'};
      state.current=C.clone(current);return state;
    }
    function capabilities() {return Object.fromEntries(M.actions.map(action=>[action,{available:!active&&can(action),reason:active?'正在等待外部桥接返回':str(bridge.getCapabilities()[action]?.reason)||'外部桥接未提供这项能力'}]));}
    function cancel(){epoch++;active=false;current={name:'',evidence:'unknown'};listKey=cfgKey='';}
    async function invoke(action,payload={},options={}) {
      if(!M.actions.includes(action)||!capabilities()[action]?.available)C.fail('NOT_AVAILABLE');
      const before=snapshot(), serial=epoch;
      if(action!=='openModelSettings'&&payload.revision!==(before.modelConfiguration.open?before.modelConfiguration.revision:before.modelPanel.revision))C.fail('STALE_TARGET','模型页面已更新，请重新操作');
      active=true;
      const check=()=>{if(serial!==epoch)C.fail('CANCELLED','模型操作已停止');options.check?.();};
      async function run(name,args){check();if(!can(name))C.fail('NOT_AVAILABLE');const result=await bridge.invoke(name,args);check();
        if(!result?.ok)C.fail(result?.error?.code||'NATIVE_FAILED',result?.error?.message||'外部桥接操作失败');
        await bridge.refresh?.();check();return result;}
      try{
        check();let args, phase;
        if(action==='selectModelFilter'){
          if(before.modelPanel.filters.filter(row=>row.id===payload.filterId).length!==1)C.fail('STALE_TARGET');
          args={filterId:payload.filterId};phase='filtered';
        }else if(action==='selectModel'||action==='openModelConfiguration'){
          const chosen=before.modelPanel.models.find(row=>row.id===payload.modelId);
          if(!chosen?.available)C.fail('STALE_TARGET');args={modelId:chosen.id};
          if(action==='selectModel'){
            await run(action,args);
            let after=snapshot();
            if(!after.modelPanel.open&&can('openModelSettings')){await run('openModelSettings');after=snapshot();}
            const selected=after.modelPanel.models.filter(row=>row.selected);
            const observed=after.modelPanel.open&&selected.length===1&&selected[0].id===chosen.id;
            if(after.modelPanel.open&&can('closeModelSettings'))await run('closeModelSettings');
            current=observed?{name:chosen.name,evidence:'provided-snapshot'}:{name:'',evidence:'unknown'};
            return {ok:true,action,accepted:true,completed:'unknown',persisted:'unknown',data:{phase:observed?'selection-observed':'selection-unconfirmed',name:chosen.name}};
          }
          phase='configuration-opened';
        }else if(action==='setModelSetting'){
          const matches=before.modelConfiguration.controls.filter(row=>row.id===payload.controlId),control=matches[0];
          if(matches.length!==1)C.fail('STALE_TARGET');args={controlId:control.id};phase='setting-observed';
          if(control.type==='toggle'){
            if(typeof payload.value!=='boolean')C.fail('INVALID_REQUEST');
            if(control.value===payload.value)return {ok:true,action,accepted:true,completed:'unknown',persisted:'unknown',data:{phase}};
          }else{
            if(control.choices.filter(row=>row.id===payload.choiceId).length!==1)C.fail('STALE_TARGET');args.choiceId=payload.choiceId;
          }
        }else phase={openModelSettings:'opened',closeModelSettings:'closed',submitModelConfiguration:'configuration-submitted',closeModelConfiguration:'configuration-closed'}[action];
        await run(action,args);
        if(action==='setModelSetting'){
          const control=snapshot().modelConfiguration.controls.find(row=>row.id===payload.controlId);
          if(!control||(control.type==='toggle'?control.value!==payload.value:!control.choices.some(row=>row.id===payload.choiceId&&row.selected)))C.fail('UNCONFIRMED','设置结果尚未确认，请重新读取');
        }
        return {ok:true,action,accepted:true,completed:'unknown',persisted:'unknown',data:{phase}};
      }finally{if(serial===epoch)active=false;}
    }
    return {snapshot,capabilities,invoke,cancel,destroy:cancel};
  }
  G.MmdSameLayerProvidedModels=Object.freeze({create});
})(globalThis);
