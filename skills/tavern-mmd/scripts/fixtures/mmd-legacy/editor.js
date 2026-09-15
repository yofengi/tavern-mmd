/* Old MMD message editor: observed DOM, pinned offline Vditor, local state only. */
(function (G) {
  'use strict';
  let closeCurrent=null;
  G.MmdLegacyEditor = {
    close(){closeCurrent?.();},
    open({row,content,box,record}) {
      closeCurrent?.();
      const p=box('sim-editor-loading'),input=box('modify-input-box'),mount=box('');mount.id='vditor';input.append(mount);
      const options=box('option-box'),saveBox=box('modify-btn-box');p.append(input,options,saveBox);
      // The native overlay is a direct page-body child, outside the chat's stacking context.
      document.querySelector('uni-page-body').append(p);
      let ready=false;
      const control=(label,cls,fn)=>{const b=box(cls,label);b.setAttribute('role','button');b.tabIndex=0;
        b.onclick=e=>{e.stopPropagation();if(ready&&b.getAttribute('aria-disabled')!=='true')fn();};
        b.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();b.click();}};return b;};
      const close=()=>{p.remove();if(ready)editor.destroy();closeCurrent=null;};
      closeCurrent=close;
      p.onclick=e=>{if(e.target===p)close();};
      for(const el of [input,options,saveBox])el.addEventListener('click',e=>e.stopPropagation());
      const converters=[G.OpenCC.Converter({from:'cn',to:'t'}),G.OpenCC.Converter({from:'t',to:'cn'})];
      ['简转繁','繁转简','去除异常符号','去除异常文字'].forEach((label,i)=>{
        const b=control(label,'option-item',()=>{editor.setValue(converters[i](editor.getValue()));record('edit-transform-'+i);});
        if(i>=2){b.setAttribute('aria-disabled','true');b.title='实机清理规则尚未核实；本地预览仅保留入口';}
        options.append(b);
      });
      const save=control('保存','modify-btn',()=>{
        if(!content.isConnected)return close();
        row.text=editor.getValue().replace(/\n$/,'');content.innerText=row.text;record('editMessage');close();
      });saveBox.append(save);
      const editor=new G.Vditor(mount,{
        cdn:new URL('vendor/vditor',location.href).href,mode:'ir',lang:'zh_CN',theme:'classic',
        height:'40vh',width:'100%',
        toolbarConfig:{hide:true},cache:{enable:false},value:row.text,placeholder:'',
        preview:{theme:{current:'light',path:new URL('vendor/vditor/dist/css/content-theme',location.href).href},hljs:{enable:false},math:{engine:'KaTeX'},markdown:{sanitize:true}},
        after(){if(!p.isConnected){editor.destroy();return;}ready=true;p.className='msg-modify-scope';}
      });
    }
  };
})(window);
