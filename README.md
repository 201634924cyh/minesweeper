# 扫雷 Minesweeper（pygame）

经典 Windows 风格扫雷，纯 pygame 实现，**零外部素材**——所有图形（斜角按钮、数码管、笑脸、地雷、旗子）均由代码绘制。

![Language](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Dependency](https://img.shields.io/badge/dependency-pygame-2C8E4E)
![License](https://img.shields.io/badge/license-MIT-green)
![Selftest](https://img.shields.io/badge/selftest-53%20passed-brightgreen)

## 预览

| 难度菜单 | 对局中 |
| :---: | :---: |
| ![菜单](preview/01_menu.png) | ![对局](preview/02_play.png) |

| 胜利结算 | 失败结算 |
| :---: | :---: |
| ![胜利](preview/03_won.png) | ![失败](preview/04_lost.png) |

## 特性

- 三档难度：初级 9×9 / 10 雷、中级 16×16 / 40 雷、高级 30×16 / 99 雷
- 首次点击必安全，且**必开出一片空白区**：布雷时排除了首点格及其周围一圈，
  首点数字必为 0，洪水扩散随即展开，不会出现「第一下只翻一格」的憋屈开局
- 左键翻开 / 右键插旗 / 中键（或左右键同按）在数字格上快速翻开周围
- 剩余雷数计数、计时器、笑脸按钮（按住变惊讶脸，胜利戴墨镜，失败变 X 眼）
- 失败时展示全部地雷、标错的旗打红叉；胜利时自动补满旗并弹出结算面板
- 空白格自动洪水扩散；数字按经典配色（1 蓝 2 绿 3 红 …）
- 中文字体自动匹配 Windows / macOS / Linux 常见字体，匹配不到还会遍历系统字体兜底，
  不会出现方框乱码

## 快速开始

```bash
git clone https://github.com/201634924cyh/minesweeper.git
cd minesweeper
```

然后选一种方式启动：

| 平台 | 命令 |
| --- | --- |
| Windows | 双击 `run.bat` |
| macOS / Linux | `sh run.sh` |
| 任意平台手动 | `pip install -r requirements.txt` 然后 `python minesweeper.py` |

启动脚本会自己找 Python、缺 pygame 就自动装（走清华镜像），首次运行不会卡住。

> 没有官方 pygame wheel 的 Python 版本（如 3.14）会自动改装 `pygame-ce` —— 社区分支，API 兼容，装完同样是 `import pygame`。

## 操作

| 按键 | 功能 |
| --- | --- |
| 左键 | 翻开格子 |
| 右键 | 插旗 / 取消旗 |
| 中键（或左右键同按） | 数字格上快速翻开周围 |
| F2 / 点击笑脸 | 重新开始 |
| 1 / 2 / 3 | 切换 初级 / 中级 / 高级 |
| M | 返回难度菜单 |
| ESC | 退出 |

## 项目结构

```
minesweeper/
├── minesweeper.py     # 游戏本体：配置、工具、棋盘逻辑、渲染、主循环（单文件）
├── selftest.py        # 无窗口自检，53 条断言
├── run.bat            # Windows 启动脚本
├── run.sh             # macOS / Linux 启动脚本
├── requirements.txt   # 依赖（仅 pygame）
├── preview/           # README 用的截图（由 selftest 自动重新生成）
├── LICENSE
├── .gitignore
└── .gitattributes
```

`minesweeper.py` 分四层，跳读方便：

| 层 | 内容 |
| --- | --- |
| 配置常量 | 格子尺寸、数码管与笑脸尺寸、菜单布局、配色表、数字配色 |
| 工具函数 | 中文字体匹配与回退、3D 斜角边框、凹陷面板 |
| `Board` | 纯逻辑：布雷（首点安全）、翻格、洪水扩散、标旗、和弦、胜负判定、计时 |
| `Renderer` | 绘制：斜角边框、数码管、笑脸（微笑/惊讶/墨镜/X 眼）、地雷与旗子 |
| `Game` | 主循环：事件分发、坐标换算、难度切换、菜单与结算面板 |

菜单有**独立的窗口尺寸**（`menu_size()`）：初级盘窗口只有 370px 高，
装不下三张难度卡片加底部提示，所以进出菜单时会自动调整窗口大小。

## 自测

```bash
python selftest.py            # 或 python minesweeper.py --test
```

以 `SDL_VIDEODRIVER=dummy` 起虚拟显示，跑 **53 条断言**，覆盖：

- **布雷与首点安全**：三档难度各 60 局，验证首点格及其周围一圈必无雷、雷数恒等于配置，
  且首点必开出一片空白区。
- **三档难度必胜路径**：各 40 局翻开全部非雷格，必须精确进入 `WIN`，
  且 `opened == cols × rows − mines`、旗数自动补满。
- **失败态**：踩雷进入 `LOST`、踩中的那颗被标记、全部雷可见、标错的旗打红叉、
  失败后翻格与插旗均失效。
- **胜利后输入**：翻格 / 插旗 / 和弦都不再改变棋盘。
- **标旗与计数**：旗数增减准确、已翻开格不能插旗、剩余雷数可为负。
- **一致性**：重复 `reveal` 不重复计数、`opened` 与实际翻开格数始终相等、
  `arm()` 幂等（重复调用不会叠加布雷）。
- **和弦**：旗数不匹配时不动作，匹配时正确翻开周围。
- **计时器**：未开局不走、开局后走、结束后停、上限 999。
- **随机对局压力**：40 局高级盘随机操作，校验状态合法且计数守恒。
- **中文渲染**：定位到的字体必须真的带中文字形（`metrics()` 非 None），
  防止退化成豆腐块 —— 这是字体回退的回归测试。
- **渲染与像素扫描**：四种状态各截一张图，再扫描像素确认菜单标题确实画了文字、
  卡片之间是纯背景色、对局出现数字配色、数码管是红色、结算面板盖在画面中央。
- **菜单布局**：三张卡片都在窗口内且互不重叠、窗口宽度容得下底部提示文字。

自检会顺带把 README 用的截图重新生成到 `preview/`。

## 想改造的话，改这几个地方

| 想改什么 | 改哪里 |
| --- | --- |
| 难度配置（尺寸、雷数） | `DIFFICULTIES` |
| 格子大小 / 信息栏高度 | `CELL` / `HUD_H` / `PAD` |
| 菜单尺寸与卡片布局 | `MENU_W` / `MENU_TOP` / `MENU_CARD_*` 与 `menu_size()` |
| 配色（含数字颜色） | 顶部 `C_*` 常量与 `NUM_COLORS` |
| 笑脸表情 | `Renderer.face()` 的 `face_state` 分支 |
| 中文字体 | `_FONT_FAMILIES` 字体族候选列表 |
| 胜负结算面板 | `Game.draw_overlay()` |
| 加新玩法（如无猜模式、标问号） | `Board` 的翻格与标旗逻辑 |

## 已知取舍

- **插旗数可以超过雷数**，剩余雷数会显示成负数（数码管按 `-XX` 显示），
  这是刻意保留的经典行为。
- **没有问号标记（?）与键盘操作格子的功能**，只保留鼠标操作。
- **没有最高分记录与回放**。
- 窗口尺寸随着难度变化，切换难度/进出菜单时窗口会重新调整大小。
- **和弦只在旗数恰好等于该格数字时才生效**（经典规则），不区分「旗插多了」的情况。

## 许可

[MIT](LICENSE)
