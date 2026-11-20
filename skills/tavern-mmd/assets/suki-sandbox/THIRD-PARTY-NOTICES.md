# Third-party notices

Moonstage bundles the following third-party work. Each item keeps its own licence.

## clipboard.js

`src/components/firstui/fui-clipboard/clipboard.min.js` is clipboard.js by Zeno Rocha,
repackaged for uni-app. MIT License. Copyright (c) Zeno Rocha.

## traditional-or-simplified

`src/common/TradOrSimp.js` is derived from the `traditional-or-simplified` npm package by
Nick Drewe. MIT License. Copyright (c) Nick Drewe.

## FirstUI

`src/components/firstui/` (request helper, clipboard wrapper, theme variables) comes from
FirstUI (https://firstui.cn/). Licence terms are being confirmed with the upstream project
before the first release; until then treat these files as retained under their upstream
terms.

## Icons and fonts

- `src/static/icon/models/*.svg` are provider logos from `@lobehub/icons` (MIT). The
  logos themselves remain trademarks of their respective owners.
- `src/static/uni.ttf` is the uni-icons font from DCloud (Apache-2.0).
- `src/static/icon/fui-custom-icon.ttf` is an icon font generated with iconfont.cn from
  icons used by the HarperHarbor client.

## Dependencies

Runtime and build dependencies are listed in `package.json`; each carries its own licence
in `node_modules/<name>/LICENSE` after `npm install`.
