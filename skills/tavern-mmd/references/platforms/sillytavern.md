# 本地酒馆（SillyTavern）平台规范

> 本地酒馆无MMD的JS/CSP限制。本文档列出可用能力全集与世界书配置参考。

## 能力全集

- `<script>`、ES6+、外部库：均可用（前端在消息内渲染HTML）
- 正则：json导入（regex_scripts，无条数硬限制）
- 世界书：完整字段支持（递归、@D深度、sticky/cooldown/delay、向量化等）
- 扩展生态：酒馆助手、MVU变量框架、STScript 可用（本skill不展开MVU，需要时提示用户改用 tavern-cards skill）

## 世界书 position 参考

| 值 | 标签 | 说明 |
|---|---|---|
| 0 | ↑Char | 角色定义之前——世界观总纲、背景设定 |
| 1 | ↓Char | 角色定义之后——角色详情、NPC、场景/事件/物品 |
| 2 | ↑AT | Author's Note之前——写作规范/文风指导 |
| 3 | ↓AT | Author's Note之后 |
| 4 | @D | 指定深度——仅 depth=0 用于行为纠正（role=system），禁止 D1+ |
| 5 | ↑EM | 示例消息之前 |
| 6 | ↓EM | 示例消息之后 |

## 配置要点

- 蓝灯=constant:true（常驻）；绿灯=constant:false+keys触发
- 所有条目默认 preventRecursion:true、excludeRecursion:true，确有递归需求再开
- 绿灯条目 keys 用英文逗号分隔全名/昵称/外号；scanDepth 默认即可，特殊需要再设
- order 决定同位置内顺序：总纲1 → 速览4 → 角色10-35 → 性格35-45 → 物品/场景50-98 → 补充99 → NPC100

## 正则脚本字段（json导入）

placement: 1=用户输入, 2=AI输出（常用[2]）；markdownOnly=仅渲染层（美化用）；promptOnly=仅提示词层（隐藏不发AI用）；runOnEdit、minDepth/maxDepth 按需。
完整json结构见 ../output/regex-output.md。

## 美化方式

1. 消息内HTML+CSS+script（角色卡自带，正则注入）——与MMD方案同构，最通用
2. 酒馆主题/自定义CSS（用户侧全局，非卡内交付物）——仅建议用户自行配置时提及
