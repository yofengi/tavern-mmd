# 配色维度库（palettes）

本文件是风格数据库的配色维度。每个风格一套色板，填进统一 token（token 名与 ../style-system.md 第1节一致）。标 L=仅亮色，D=仅暗色，L/D=双版。

### 1. 极简墨白 [明暗:L]
```
--bg:#FFFFFF; --surface:#F5F5F5; --border:#000000;
--text:#000000; --text-2:#525252; --text-3:#A3A3A3;
--accent:<单一强调，由用户定>; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 2. 瑞士极简 [明暗:L/D]
```
--bg:#FFFFFF; --surface:#F5F5F5; --border:#000000;
--text:#000000; --text-2:#808080; --text-3:#B3B3B3;
--accent:<单一鲜艳，由用户定>; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#111111; --surface:#1C1C1C; --border:#FFFFFF; --text:#FFFFFF; --text-2:#808080; --text-3:#B3B3B3; --accent:<单一鲜艳，由用户定>; --accent-2:—;`

### 3. 便签纸墨 [明暗:L]
```
--bg:#FDFBF7; --surface:#F5F5F5; --border:#E0E0E0;
--text:#1A1A1A; --text-2:#4A4A4A; --text-3:#8A8A8A;
--accent:#FFFF00; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 4. 大地陶土 [明暗:L]
```
--bg:#F5F0E1; --surface:#D4C4A8; --border:#9C8B7A;
--text:#3D332B; --text-2:#6B7B3C; --text-3:#9BAA6E;
--accent:#C67B5C; --accent-2:#B5651D;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 5. 复古胶片 [明暗:L]
```
--bg:#F5E6C8; --surface:#E8D8B8; --border:#D4A574;
--text:#4A4A4A; --text-2:#4A7B7C; --text-3:#7AABAC;
--accent:#D4A574; --accent-2:#E8B4B8;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 6. 杂志编排 [明暗:L/D]
```
--bg:#FFFFFF; --surface:#F5F5F5; --border:#000000;
--text:#000000; --text-2:#525252; --text-3:#A3A3A3;
--accent:<品牌色，由用户定>; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#111111; --surface:#1C1C1C; --border:#FFFFFF; --text:#FFFFFF; --text-2:#A3A3A3; --text-3:#D0D0D0; --accent:<品牌色，由用户定>; --accent-2:—;`

### 7. 手绘速写 [明暗:L]
```
--bg:#FDFBF7; --surface:#E5E0D8; --border:#2D2D2D;
--text:#2D2D2D; --text-2:#6B7280; --text-3:#A3A8B0;
--accent:#FF4D4D; --accent-2:#2D5DA1;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 8. 黏土软糖 [明暗:L]
```
--bg:#F4F1FA; --surface:rgba(255,255,255,.7); --border:无;
--text:#332F3A; --text-2:#635F69; --text-3:#9C99A2;
--accent:#7C3AED; --accent-2:#DB2777;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 9. 新拟物 [明暗:L]
```
--bg:#E0E5EC; --surface:#E0E5EC; --border:无;
--text:#3D4852; --text-2:#6B7280; --text-3:#A3A8B0;
--accent:#6C63FF; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 10. 软UI进化 [明暗:L/D]
```
--bg:#F5F5F7; --surface:#FFFFFF; --border:#E5E7EB;
--text:#1a1a1a; --text-2:#525252; --text-3:#A3A3A3;
--accent:#87CEEB; --accent-2:#FFB6C1;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#1A1A1F; --surface:#2C2C30; --border:#3A3A40; --text:#F5F5F7; --text-2:#A3A3A3; --text-3:#6E6E74; --accent:#87CEEB; --accent-2:#FFB6C1;`

### 11. 有机生物 [明暗:L/D]
```
--bg:#F5F5DC; --surface:#FFFFFF; --border:#C8D6B0;
--text:#2D3A1F; --text-2:#6B7B3C; --text-3:#9BAA6E;
--accent:#228B22; --accent-2:#8B4513;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#1A1F14; --surface:#252B1C; --border:#3D4A2C; --text:#D8E8C0; --text-2:#6B7B3C; --text-3:#9BAA6E; --accent:#228B22; --accent-2:#8B4513;`

### 12. 便当格 [明暗:L/D]
```
--bg:#F5F5F7; --surface:#FFFFFF; --border:#E5E5E5;
--text:#1D1D1F; --text-2:#525252; --text-3:#A3A3A3;
--accent:<品牌色，由用户定>; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#1A1A1C; --surface:#2C2C2E; --border:#3A3A3C; --text:#F5F5F7; --text-2:#A3A3A3; --text-3:#6E6E74; --accent:<品牌色，由用户定>; --accent-2:—;`

### 13. 暗夜霓虹 [明暗:D]
```
--bg:#0D0D0D; --surface:#161b22; --border:#30363d;
--text:#e6edf3; --text-2:#8b949e; --text-3:#6e7681;
--accent:#00FF00; --accent-2:#FF00FF;
--success:#3fb950; --warning:#d29922; --danger:#f85149;
```
dark: 同上（本风格为暗色系）

### 14. 全息HUD [明暗:D]
```
--bg:rgba(0,10,20,.9); --surface:rgba(0,20,40,.6); --border:#333333;
--text:#00FFFF; --text-2:#0080FF; --text-3:#004FBF;
--accent:#00FFFF; --accent-2:#FF0000;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 15. 终端CLI [明暗:D]
```
--bg:#050505; --surface:#0A0A0A; --border:#33FF00;
--text:#33FF00; --text-2:#1A3D1A; --text-3:#0F220F;
--accent:#33FF00; --accent-2:#FFB000;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 16. 影院暗调 [明暗:D]
```
--bg:#050506; --surface:#0a0a0c; --border:rgba(255,255,255,.08);
--text:#EDEDEF; --text-2:#8A8F98; --text-3:#6B7077;
--accent:#5E6AD2; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 17. 赛博HUD [明暗:D]
```
--bg:#0A0A0F; --surface:#12121A; --border:#2A2A3A;
--text:#E0E0E0; --text-2:#8A8F98; --text-3:#6B7077;
--accent:#00FF88; --accent-2:#FF00FF;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 18. OLED纯黑 [明暗:D]
```
--bg:#000000; --surface:#121212; --border:#222222;
--text:#FFFFFF; --text-2:#888888; --text-3:#555555;
--accent:#39FF14; --accent-2:#BF00FF;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 19. 学院典籍 [明暗:D]
```
--bg:#1C1714; --surface:#251E19; --border:#4A3F35;
--text:#E8DFD4; --text-2:#9C8B7A; --text-3:#7A6A5A;
--accent:#C9A962; --accent-2:#8B2635;
--success:#16A34A; --warning:#CA8A04; --danger:#8B2635;
```
dark: 同上（本风格为暗色系）

### 20. 金橙账本 [明暗:D]
```
--bg:#030304; --surface:#0F1115; --border:rgba(30,41,59,.2);
--text:#FFFFFF; --text-2:#94A3B8; --text-3:#6B7A90;
--accent:#F7931A; --accent-2:#FFD600;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 21. 粗体海报 [明暗:D]
```
--bg:#0A0A0A; --surface:#1A1A1A; --border:#262626;
--text:#FAFAFA; --text-2:#737373; --text-3:#525252;
--accent:#FF3D00; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 22. 动势野兽 [明暗:D]
```
--bg:#09090B; --surface:#27272A; --border:#3F3F46;
--text:#FAFAFA; --text-2:#A1A1AA; --text-3:#71717A;
--accent:#DFE104; --accent-2:—;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 23. 毛玻璃 [明暗:L/D]
```
--bg:<鲜艳底，由用户定>; --surface:rgba(255,255,255,.15); --border:rgba(255,255,255,.2);
--text:<据底定>; --text-2:据底定; --text-3:据底定;
--accent:#0080FF; --accent-2:#8B00FF;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:<暗色鲜艳底，由用户定>; --surface:rgba(0,0,0,.3); --border:rgba(255,255,255,.15); --text:#FFFFFF; --text-2:据底定; --text-3:据底定; --accent:#0080FF; --accent-2:#8B00FF;`

### 24. 新野兽派 [明暗:L]
```
--bg:#FFFDF5; --surface:#FFFFFF; --border:#000000;
--text:#000000; --text-2:#525252; --text-3:#A3A3A3;
--accent:#FFEB3B; --accent-2:#FF5252;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 25. 包豪斯 [明暗:L]
```
--bg:#F0F0F0; --surface:#E0E0E0; --border:#121212;
--text:#121212; --text-2:#525252; --text-3:#A3A3A3;
--accent:#D02020; --accent-2:#1040C0;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 不适用（仅亮色，按 section 反色）

### 26. Y2K千禧 [明暗:L/D]
```
--bg:#1A1A2E; --surface:#C0C0C0; --border:#9400D3;
--text:#FFFFFF; --text-2:#C0C0C0; --text-3:#8F8F8F;
--accent:#FF69B4; --accent-2:#00FFFF;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#0D0D1A; --surface:#1A1A2E; --border:#6600A0; --text:#FFFFFF; --text-2:#C0C0C0; --text-3:#8F8F8F; --accent:#FF69B4; --accent-2:#00FFFF;`

### 27. 孟菲斯 [明暗:L/D]
```
--bg:#FFFFFF; --surface:#F5F5F5; --border:#000000;
--text:#1A1A1A; --text-2:#525252; --text-3:#A3A3A3;
--accent:#FF71CE; --accent-2:#86CCCA;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#111111; --surface:#1C1C1C; --border:#FFFFFF; --text:#FAFAFA; --text-2:#A3A3A3; --text-3:#6E6E74; --accent:#FF71CE; --accent-2:#86CCCA;`

### 28. 晨昏极光 [明暗:L/D]
```
--bg:#0F0A1E; --surface:rgba(255,255,255,.05); --border:rgba(255,255,255,.1);
--text:#FFFFFF; --text-2:#B0A8C0; --text-3:#7E748E;
--accent:#0080FF; --accent-2:#FF1493;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#07051A; --surface:rgba(255,255,255,.04); --border:rgba(255,255,255,.08); --text:#FFFFFF; --text-2:#B0A8C0; --text-3:#7E748E; --accent:#0080FF; --accent-2:#FF1493;`

### 29. 蒸汽波 [明暗:D]
```
--bg:#1A1A2E; --surface:#2A1A3E; --border:rgba(255,255,255,.1);
--text:#FFFFFF; --text-2:#B967FF; --text-3:#8033CC;
--accent:#FF71CE; --accent-2:#01CDFE;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: 同上（本风格为暗色系）

### 30. 渐变网格 [明暗:L/D]
```
--bg:#0A0A1A; --surface:rgba(255,255,255,.05); --border:rgba(255,255,255,.1);
--text:#FFFFFF; --text-2:#B0B0C0; --text-3:#7E7E90;
--accent:#00FFFF; --accent-2:#FF00FF;
--success:#16A34A; --warning:#CA8A04; --danger:#DC2626;
```
dark: `--bg:#050510; --surface:rgba(255,255,255,.04); --border:rgba(255,255,255,.08); --text:#FFFFFF; --text-2:#B0B0C0; --text-3:#7E7E90; --accent:#00FFFF; --accent-2:#FF00FF;`
