# -*- coding: utf-8 -*-
"""
minesweeper.py 的无窗口自检。

用法：
    python selftest.py              # 或 python minesweeper.py --test

覆盖：布雷与首点安全 / 三档难度必胜路径 / 状态机全分支 / 标旗与剩余雷数 /
和弦翻开 / 计时器 / 随机对局压力 / 中文字形可用性 / 各状态截图 + 像素扫描。
"""

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  必须在环境变量之后导入

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minesweeper as M  # noqa: E402

SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [ok]   {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")
        print(f"  [FAIL] {name}   {detail}")


def section(title):
    print(f"\n=== {title} ===")


def new_game(diff=0, menu=False):
    g = M.Game()
    g.set_difficulty(diff)
    if menu:
        g.open_menu()          # 菜单有自己的窗口尺寸，必须走这个入口
    return g


def closed_cells(b):
    return [(c, r) for r in range(b.rows) for c in range(b.cols)
            if not b.cell(c, r).open]


def mine_cells(b):
    return [(c, r) for r in range(b.rows) for c in range(b.cols) if b.cell(c, r).mine]


def count_mines(b):
    return len(mine_cells(b))


# ==============================================================
section("1. 布雷与首点安全")
# ==============================================================
random.seed(20260920)

for idx, d in enumerate(M.DIFFICULTIES):
    bad = 0
    flooded = 0
    for _ in range(60):
        b = M.Board(d["cols"], d["rows"], d["mines"])
        c = random.randrange(b.cols)
        r = random.randrange(b.rows)
        b.reveal(c, r)
        # 首点格及其周围一圈都不该有雷
        if b.cell(c, r).mine or any(b.cell(nc, nr).mine for nc, nr in b.neighbors(c, r)):
            bad += 1
        # 也正因如此，首点数字必为 0 -> 必然洪水扩散出一片空白区
        if b.cell(c, r).adj == 0 and b.opened > 1:
            flooded += 1
    check(f"首点必安全 · {d['name']}（60 局）", bad == 0, f"违规 {bad}")
    check(f"首点必开出一片空白区 · {d['name']}（60 局）", flooded == 60, f"仅 {flooded}/60")

for idx, d in enumerate(M.DIFFICULTIES):
    bad = 0
    for _ in range(30):
        b = M.Board(d["cols"], d["rows"], d["mines"])
        b.reveal(0, 0)
        if count_mines(b) != d["mines"]:
            bad += 1
    check(f"雷数恒等于配置 · {d['name']}", bad == 0, f"不符 {bad}")

b = M.Board(9, 9, 10)
b.arm(4, 4)
b.arm(4, 4)
check("arm() 幂等，重复调用不叠加布雷", count_mines(b) == 10, f"mine={count_mines(b)}")

# ==============================================================
section("2. 三档难度必胜路径")
# ==============================================================
# 翻开全部非雷格，必须精确进入 WIN，且计数与旗数完全对齐。
for idx, d in enumerate(M.DIFFICULTIES):
    bad = 0
    need = d["cols"] * d["rows"] - d["mines"]
    for _ in range(40):
        b = M.Board(d["cols"], d["rows"], d["mines"])
        b.reveal(0, 0)
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.cell(c, r).mine:
                    b.reveal(c, r)
        if b.state != M.ST_WON or b.opened != need or b.flags != d["mines"]:
            bad += 1
    check(f"必胜路径可达 WIN · {d['name']}（40 局）", bad == 0, f"失败 {bad}")
    if bad == 0:
        print(f"         opened={b.opened}/{need} flags={b.flags}/{d['mines']}")

# ==============================================================
section("3. 踩雷与失败态")
# ==============================================================
b = M.Board(9, 9, 10)
b.reveal(4, 4)
hit = mine_cells(b)[0]
b.reveal(*hit)
check("踩雷进入 LOST", b.state == M.ST_LOST, f"state={b.state}")
check("踩中的那颗雷被标记 boom", b.cell(*hit).boom)

visible = sum(1 for (c, r) in mine_cells(b) if b.cell(c, r).open)
check("失败后全部雷可见", visible == 10, f"visible={visible}")

# 标错的旗打红叉
b2 = M.Board(9, 9, 10)
b2.reveal(4, 4)
wrong = [p for p in closed_cells(b2) if not b2.cell(*p).mine]
b2.toggle_flag(*wrong[0])
b2.reveal(*mine_cells(b2)[0])
check("标错的旗被标记 wrong", b2.cell(*wrong[0]).wrong)

check("失败后翻格无效", not b.reveal(0, 0))
snap = (b.opened, b.flags, b.state)
b.toggle_flag(0, 0)
check("失败后插旗无效", (b.opened, b.flags, b.state) == snap)

# ==============================================================
section("4. 胜利后的输入不应改变棋盘")
# ==============================================================
b = M.Board(9, 9, 10)
b.reveal(0, 0)
for r in range(9):
    for c in range(9):
        if not b.cell(c, r).mine:
            b.reveal(c, r)
snap = (b.opened, b.flags, b.state)
b.reveal(0, 0)
b.toggle_flag(*closed_cells(b)[0] if closed_cells(b) else (0, 0))
b.chord(0, 0)
check("胜利后输入不改变棋盘", (b.opened, b.flags, b.state) == snap, f"{snap} -> {(b.opened, b.flags, b.state)}")
check("胜利时全部雷被插旗", all(b.cell(c, r).flag for (c, r) in mine_cells(b)))

# ==============================================================
section("5. 标旗与剩余雷数")
# ==============================================================
b = M.Board(9, 9, 10)
b.reveal(4, 4)
n = 0
for p in closed_cells(b):
    b.toggle_flag(*p)
    n += 1
check("旗数计数准确", b.flags == n, f"flags={b.flags} 实际={n}")
check("剩余雷数可为负（插旗超过雷数）", b.total_mines - b.flags < 0)

b.toggle_flag(*closed_cells(b)[0])
check("取消旗后计数回落", b.flags == n - 1, f"flags={b.flags}")

opened_cell = [(c, r) for r in range(9) for c in range(9) if b.cell(c, r).open][0]
b.toggle_flag(*opened_cell)
check("已翻开格不能插旗", not b.cell(*opened_cell).flag)

# ==============================================================
section("6. 重复操作与计数一致性")
# ==============================================================
b = M.Board(9, 9, 10)
b.reveal(4, 4)
o1 = b.opened
for _ in range(20):
    b.reveal(4, 4)
check("重复 reveal 不重复计数", b.opened == o1, f"{o1} -> {b.opened}")

actual = sum(1 for r in range(9) for c in range(9) if b.cell(c, r).open)
check("opened 与实际翻开格数一致", actual == b.opened, f"{actual} != {b.opened}")

# ==============================================================
section("7. 和弦（快速翻开）")
# ==============================================================
# 构造一个确实能产生变化的场景：找一个 adj>0 的已翻开格，
# 它至少有一个「未翻开且非雷」的邻居可供 chord 翻开。
b = M.Board(16, 16, 40)
b.reveal(8, 8)
target = None
for r in range(b.rows):
    for c in range(b.cols):
        cell = b.cell(c, r)
        if not (cell.open and cell.adj > 0):
            continue
        nbs = [(nc, nr) for nc, nr in b.neighbors(c, r) if not b.cell(nc, nr).open]
        if any(not b.cell(nc, nr).mine for nc, nr in nbs):
            target = (c, r, nbs)
            break
    if target:
        break

c, r, nbs = target
before = b.opened
check("旗数不匹配时 chord 不动作", not b.chord(c, r) and b.opened == before,
      f"opened {before} -> {b.opened}")

for nc, nr in nbs:
    if b.cell(nc, nr).mine:
        b.toggle_flag(nc, nr)
after = b.opened
boom = b.chord(c, r)
check("旗数匹配时 chord 正常翻开", b.opened > after and not boom,
      f"opened {after} -> {b.opened} boom={boom}")
check("已翻开格上 chord 无效", not b.chord(c, r))

# ==============================================================
section("8. 计时器")
# ==============================================================
b = M.Board(9, 9, 10)
b.tick()
check("未开局计时器不走", b.time == 0, f"time={b.time}")
b.reveal(4, 4)
b.tick()
check("开局后计时器走", b.time == 1, f"time={b.time}")
b.win()
b.tick()
check("结束后计时器停", b.time == 1, f"time={b.time}")

b = M.Board(9, 9, 10)
b.reveal(4, 4)
b.time = 999
b.tick()
check("计时器上限 999", b.time == 999, f"time={b.time}")

# ==============================================================
section("9. 随机对局压力测试")
# ==============================================================
random.seed(7)
states = {}
violations = 0
for _ in range(40):
    g = M.Game()
    g.set_difficulty(2)
    g.menu = False
    frames = 0
    while g.board.state == M.ST_PLAY and frames < 4000:
        pool = closed_cells(g.board)
        if not pool:
            break
        c, r = random.choice(pool)
        if random.random() < 0.25:
            g.board.toggle_flag(c, r)
        else:
            g.board.reveal(c, r)
        g.update()
        g.draw()
        frames += 1
    states[g.board.state] = states.get(g.board.state, 0) + 1
    if count_mines(g.board) != 99:
        violations += 1
    # 注意 opened 只统计「已翻开的非雷格」：失败时会把未标记的雷也翻开，
    # 那些不计入 opened，所以这里必须把雷排除掉再比。
    actual = sum(1 for rr in range(g.board.rows) for cc in range(g.board.cols)
                 if g.board.cell(cc, rr).open and not g.board.cell(cc, rr).mine)
    if actual != g.board.opened:
        violations += 1
check("40 局随机对局无异常且计数守恒", violations == 0,
      f"违规 {violations} 状态分布={states}")

# ==============================================================
section("10. 中文渲染（字体回退回归测试）")
# ==============================================================
pygame.init()
pygame.display.set_mode((360, 370))

font = M.get_font(20)
path = M._resolve_font_path(False)
print(f"  字体路径：{path or '（未命中，退回默认位图字体）'}")
check("能定位到带中文字形的字体文件", path is not None)
check("中文字形存在（无豆腐块）", all(v is not None for v in font.metrics("扫雷")),
      f"metrics={font.metrics('扫雷')}")
check("中文与英文都能渲染出非空表面",
      font.render("扫雷", True, (0, 0, 0)).get_width() > 0
      and font.render("Minesweeper", True, (0, 0, 0)).get_width() > 0)

bold_font = M.get_font(22, bold=True)
check("粗体中文字形存在", all(v is not None for v in bold_font.metrics("扫雷")))

# ==============================================================
section("11. 渲染截图 + 像素扫描")
# ==============================================================
os.makedirs(SHOT_DIR, exist_ok=True)


def save(surf, name):
    p = os.path.join(SHOT_DIR, name)
    pygame.image.save(surf, p)
    print(f"  [shot] {name}: {surf.get_width()}x{surf.get_height()}")
    return p


random.seed(11)

# 菜单
g = new_game(0, menu=True)
g.draw()
menu_game = g                      # 后面 g 会被复用到别的局面，这里留住菜单这一份
save(g.screen, "01_menu.png")

# 菜单布局：窗口必须装得下三张卡片 + 底部提示，否则第三张会被切掉
cards_h = len(M.DIFFICULTIES) * M.MENU_CARD_H + (len(M.DIFFICULTIES) - 1) * M.MENU_CARD_GAP
mw, mh = g.menu_size()
check("菜单窗口高度容得下三张卡片", mh >= M.MENU_TOP + cards_h,
      f"mh={mh} need={M.MENU_TOP + cards_h}")
check("菜单窗口还为底部提示留了空间", mh >= M.MENU_TOP + cards_h + 20, f"mh={mh}")
tip_w = g.ren.f_small.render(M.MENU_TIP, True, (0, 0, 0)).get_width()
check("菜单窗口宽度容得下底部提示文字", mw >= tip_w + 24, f"mw={mw} tip_w={tip_w}")
check("菜单窗口宽度容得下难度卡片", mw >= M.MENU_CARD_W, f"mw={mw}")
check("菜单卡片全部落在窗口内",
      all(0 <= r.top and r.bottom <= mh and 0 <= r.left and r.right <= mw for r in g._menu_rects),
      f"rects={[(r.top, r.bottom) for r in g._menu_rects]} win={mw}x{mh}")
check("菜单卡片互不重叠",
      all(g._menu_rects[i].bottom <= g._menu_rects[i + 1].top
          for i in range(len(g._menu_rects) - 1)))
# 初级盘窗口只有 370px 高，若菜单沿用棋盘窗口就会溢出——这里锁死回归
check("初级盘的棋盘窗口确实放不下菜单（所以菜单必须独立尺寸）",
      M.Game().size_for(0)[1] < M.MENU_TOP + cards_h)

# 对局中（中级，翻开一片 + 插几面旗）
g = new_game(1)
b = g.board
b.reveal(b.cols // 2, b.rows // 2)
for _ in range(12):
    pool = [(c, r) for (c, r) in closed_cells(b) if not b.cell(c, r).mine]
    if not pool:
        break
    b.reveal(*random.choice(pool))
for _ in range(5):
    pool = closed_cells(b)
    if pool:
        b.toggle_flag(*random.choice(pool))
g.update()
g.draw()
play_surf = g.screen
save(play_surf, "02_play.png")

# 胜利结算
g = new_game(1)
b = g.board
b.reveal(b.cols // 2, b.rows // 2)
for r in range(b.rows):
    for c in range(b.cols):
        if not b.cell(c, r).mine:
            b.reveal(c, r)
b.time = 63
g.update()
g.draw()
save(g.screen, "03_won.png")
check("胜利后表情为墨镜", g.face_state == "cool", f"face={g.face_state}")

# 失败结算
g = new_game(1)
b = g.board
b.reveal(b.cols // 2, b.rows // 2)
for _ in range(4):
    pool = [(c, r) for (c, r) in closed_cells(b) if not b.cell(c, r).mine]
    if pool:
        b.reveal(*random.choice(pool))
b.reveal(*mine_cells(b)[0])
g.update()
g.draw()
save(g.screen, "04_lost.png")
check("失败后表情为 X 眼", g.face_state == "dead", f"face={g.face_state}")

# 像素扫描
play = pygame.image.load(os.path.join(SHOT_DIR, "02_play.png"))


def px(surf, x, y):
    return surf.get_at((x, y))[:3]


# 菜单：标题区域应该有深色文字像素（说明中文真的画出来了，而不是一片空白）
menu = pygame.image.load(os.path.join(SHOT_DIR, "01_menu.png"))
title_dark = sum(1 for y in range(56, 96, 2) for x in range(100, 260, 2)
                 if sum(px(menu, x, y)) < 300)
check("菜单标题区域绘制了文字像素", title_dark > 40, f"count={title_dark}")

# 菜单：难度按钮之间的背景色应该统一（说明三张卡片没画歪、也没被切掉）
gaps = [px(menu, menu.get_width() // 2,
           (menu_game._menu_rects[i].bottom + menu_game._menu_rects[i + 1].top) // 2)
        for i in range(len(menu_game._menu_rects) - 1)]
check("菜单按钮之间是纯背景色", all(abs(sum(c) - 3 * 232) < 12 for c in gaps), f"gaps={gaps}")

# 对局：棋盘内应有数字颜色（蓝/绿/红）
num_px = 0
for y in range(M.HUD_H + M.PAD, play.get_height(), 3):
    for x in range(M.PAD, play.get_width(), 3):
        r, gg, bb = px(play, x, y)
        if (bb > 180 and r < 90) or (gg > 100 and r < 90 and bb < 90) or (r > 180 and gg < 90 and bb < 90):
            num_px += 1
check("对局画面出现数字配色像素", num_px > 10, f"count={num_px}")

# 对局：HUD 数码管区域应有红色数字
led_px = sum(1 for y in range(13, 13 + 38, 2) for x in range(M.PAD + 4, M.PAD + 4 + 58, 2)
             if px(play, x, y)[0] > 150 and px(play, x, y)[1] < 90)
check("HUD 数码管绘制了红色数字", led_px > 20, f"count={led_px}")

# 结算：面板区域应比棋盘区域亮（浅灰面板盖在棋盘上）
won = pygame.image.load(os.path.join(SHOT_DIR, "03_won.png"))
cx, cy = won.get_width() // 2, won.get_height() // 2
panel_bright = sum(px(won, cx, cy)) / 3
corner_bright = sum(px(won, 2, won.get_height() - 2)) / 3
check("胜利结算面板显示在画面中央且更亮", panel_bright > corner_bright + 30,
      f"panel={panel_bright:.0f} corner={corner_bright:.0f}")

pygame.quit()

# ==============================================================
print(f"\n{'=' * 52}")
print(f"通过 {PASS} 项，失败 {FAIL} 项")
if FAILURES:
    print("失败清单：")
    for f in FAILURES:
        print("  -", f)
print(f"截图目录：{SHOT_DIR}")
print("=" * 52)


def main():
    """供 minesweeper.py --test 调用。"""
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if FAIL == 0 else 1)
