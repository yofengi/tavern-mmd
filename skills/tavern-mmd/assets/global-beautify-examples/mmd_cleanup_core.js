/**
 * MMD 清污引擎核心模块 (mmd_cleanup_core.js)
 *
 * 用途：自动移除 MMD 原生日夜模式残留样式污染，保证自定义全局美化主题纯净显示。
 *
 * 工作原理：
 *   1. 用 MutationObserver 监听 body DOM/属性变化
 *   2. 检测到变化后，按白名单清理 MMD 原生样式（黑底/白字/粉蓝橙高亮/暗色类名/私有 CSS 变量）
 *   3. 幂等清理：可反复执行，不会越清越多
 *   4. 页面切换到非聊天页自动卸载，避免常驻内存
 *
 * 钩子接口：
 *   window._mmd_process(callback) - 注册自定义清理任务（如引号修复）
 *   window._mmd_off()              - 手动卸载引擎
 *   window._mmd_obs                - MutationObserver 实例（调试用）
 *
 * 集成方式：
 *   方案 A（推荐）：在全局美化 CSS 规则之后、其他脚本之前导入此模块
 *     查找：<代码1>  或  <cleanup>
 *     替换：<script>(此文件内容)</script>
 *
 *   方案 B：与其他脚本合并（如引号修复），在其末尾调 window._mmd_process(yourTask)
 *
 * 清理白名单：
 *   - 颜色值：黑底系列 (#0d0e0f, #101113, #141414, #1c1c1e...)、白色 (#fff)、
 *            MMD 高亮色（橙 #dc8333、粉 #ff6d97、蓝 #409eff/#1989fa）
 *   - CSS 属性：box-shadow、filter、text-shadow
 *   - 类名：theme-dark、vditor--dark、textarea-dark、input-dark 等暗色类
 *   - CSS 变量：--background-color、--input-font-color、--model-setting 等 MMD 私有变量
 *
 * 注意：
 *   - 仅在 MMD 聊天页（location.hash 含 'chat/chat'）启用
 *   - 输入框需特殊处理（.role-setting / .depth-input 的 input/textarea 强制继承自定义颜色）
 *   - 变量名缩写（W/D/O/X/K 等）保持原案例风格，已验证可用
 */

(function(){
  var W = window,
      D = document,
      O,  // MutationObserver 实例
      A = 1,  // 活跃标志（0=已卸载）
      T = 0,  // 防抖定时器 ID
      B = 0,  // 运行中标志（防重入）
      P = 0,  // 待执行标志
      Q = [],  // 任务队列（钩子注册的 callback）

      // 需清理的 CSS 属性白名单
      K = 'background,background-color,color,border-color,box-shadow,text-shadow,-webkit-text-fill-color,filter,--background-color,--primary-font-color,--input-font-color,--card-background-color,--input-background-color,--model-setting,--share-item-bg-color,--vig-native-ph-color'.split(','),

      // 污染样式匹配正则（MMD 原生日夜模式特征）
      X = /#(0d0e0f|101113|101014|141414|17181a|1a1a1a|1c1c1e|1e1f24|212226|25262a|2a2b30|33353b|fff|ffffff|dc8333|ff6d97|409eff|3c9cff|1989fa)|rgb\((255,\s*255,\s*255|13,\s*14,\s*15|16,\s*17,\s*19|23,\s*24,\s*26|30,\s*31,\s*36|220,\s*131,\s*51|255,\s*109,\s*151|64,\s*158,\s*255|25,\s*137,\s*250)\)|--(background-color|primary-font-color|input-font-color|card-background-color|input-background-color|model-setting|share-item-bg-color|vig-native)|box-shadow|filter|textarea-dark|input-dark|vditor|--lo/i;

  // 判断当前页面是否为聊天页
  function ok() {
    return /chat\/chat/.test(location.hash);
  }

  // 清理已有实例（重新加载时）
  try {
    W._mmd_off && W._mmd_off();
  } catch(e) {}

  // 非聊天页直接退出
  if (!ok()) return;

  // 事件监听器批量操作（m='addEventListener' 或 'removeEventListener'）
  function ev(m) {
    W[m]('hashchange', ck);
    W[m]('popstate', ck);
    W[m]('pagehide', off);
    W[m]('beforeunload', off);
    W[m]('focus', wk);
    W[m]('pageshow', wk);
    D[m]('visibilitychange', wk);
  }

  // 卸载引擎
  function off() {
    A = 0;
    clearTimeout(T);
    O && O.disconnect();
    ev('removeEventListener');
    delete W._mmd_obs;
    delete W._mmd_process;
    delete W._mmd_off;
  }

  // 页面切换检查
  function ck() {
    ok() || off();
  }

  // 清理单个元素
  function one(x) {
    var s = (x.getAttribute('style') || '') + (x.getAttribute('color') || '');

    // 移除暗色类名
    x.classList.remove('theme-dark', 'doc-markdown-body--dark', 'vditor--dark', 'active-dark');

    // 匹配白名单正则，移除污染属性
    if (s && X.test(s)) {
      for (var i = 0; i < K.length; i++)
        x.style.removeProperty(K[i]);
      x.getAttribute('style') || x.removeAttribute('style');
      x.removeAttribute('color');
    }
  }

  // 输入框特殊处理（强制继承自定义主题颜色）
  function inp() {
    D.querySelectorAll('.role-setting :is(uni-input,uni-textarea,input,textarea,.input-placeholder),.depth-input :is(input,.input-placeholder),.vig-native-input__el,.vig-native-textarea__el').forEach(x => {
      var p = x.classList.contains('input-placeholder'),
          c = p ? 'var(--p)' : 'var(--f)';  // placeholder 用半透明，正文用主色
      x.removeAttribute('color');
      ['color', '-webkit-text-fill-color'].map(y => x.style.setProperty(y, c, 'important'));
      p || x.style.setProperty('background', 'transparent', 'important');
    });
  }

  // 执行清理（遍历 body 及其子元素）
  function cl() {
    var b = D.body;
    one(b);
    var a = b.querySelectorAll('[style],[color],.theme-dark,.doc-markdown-body--dark,.vditor--dark,.active-dark');
    for (var i = 0; i < a.length; i++)
      one(a[i]);
    inp();
  }

  // 主运行函数（清理 + 钩子任务）
  function run() {
    if (!A || !D.body) return;
    if (B) return P = 1;  // 防重入：已在运行，标记待执行
    B = 1;
    O && O.disconnect();

    try {
      cl();  // 执行清理
      // 执行钩子队列（如引号修复）
      for (var i = 0; i < Q.length; i++)
        try { Q[i](); } catch(e) {}
    } finally {
      B = 0;
      // 重新监听
      A && O.observe(D.body, {
        childList: 1,
        subtree: 1,
        characterData: 1,
        attributes: 1,
        attributeFilter: ['style', 'class', 'color']
      });
      P && (P = 0, wk(50));  // 有待执行任务，延迟再跑
    }
  }

  // 防抖唤醒（避免高频触发）
  function wk(d) {
    if (!A || T) return;
    T = setTimeout(() => {
      T = 0;
      run();
    }, d || 60);
  }

  // 暴露钩子接口：注册自定义清理任务
  W._mmd_process = f => {
    f && Q.indexOf(f) < 0 && Q.push(f);
    wk(1);
  };

  // 暴露卸载接口
  W._mmd_off = off;

  // 创建 MutationObserver
  O = new MutationObserver(() => wk(60));
  W._mmd_obs = O;

  // 绑定事件监听器
  ev('addEventListener');

  // 首次运行
  run();
})();
