# -*- coding: utf-8 -*-
"""
经典扫雷 Minesweeper  —— pygame 实现
------------------------------------
操作:
    左键        翻开格子
    右键        插旗 / 取消旗
    中键        (或 左右键同时按) 在已翻开的数字格上快速翻开周围
    F2          重新开始
    1 / 2 / 3   切换 初级 / 中级 / 高级
    M           返回难度菜单
    ESC         退出
"""

import math
import os
import random
import sys

import pygame

# ============================ 配置常量 ============================
CELL = 32                 # 单格像素
PAD = 10                  # 棋盘外边距
HUD_H = 62                # 顶部信息栏高度
LED_W, LED_H = 58, 38     # 数码管尺寸
FACE_R = 20               # 笑脸半径

DIFFICULTIES = [
    {"key": "beginner",     "name": "初级", "cols": 9,  "rows": 9,  "mines": 10, "desc": "9 × 9 · 10 雷"},
    {"key": "intermediate", "name": "中级", "cols": 16, "rows": 16, "mines": 40, "desc": "16 × 16 · 40 雷"},
    {"key": "expert",       "name": "高级", "cols": 30, "rows": 16, "mines": 99, "desc": "30 × 16 · 99 雷"},
]

# —— 配色（经典 Win 风格）——
C_FACE      = (192, 192, 192)
C_LIGHT     = (255, 255, 255)
C_SHADOW    = (128, 128, 128)
C_DARK      = (90, 90, 90)
C_BLACK     = (0, 0, 0)
C_OPEN_BG   = (200, 200, 200)
C_BOOM_BG   = (255, 60, 60)
C_YELLOW    = (255, 215, 0)
C_RED       = (220, 30, 30)
C_GREEN     = (0, 128, 0)
C_LED_BG    = (10, 10, 10)
C_LED_FG    = (255, 40, 40)

NUM_COLORS = {
    1: (0, 0, 255),
    2: (0, 128, 0),
    3: (255, 0, 0),
    4: (0, 0, 128),
    5: (128, 0, 0),
    6: (0, 128, 128),
    7: (0, 0, 0),
    8: (128, 128, 128),
}

ST_PLAY, ST_WON, ST_LOST = "play", "won", "lost"


# ============================ 工具函数 ============================
def get_font(size, bold=False):
    """优先使用系统中文字体，找不到则退回默认字体。"""
    for name in ("microsoftyahei", "msyh", "simhei", "dengxian", "simsun", "arialunicode"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            try:
                return pygame.font.Font(path, size)
            except Exception:
                pass
    return pygame.font.Font(None, size)


def bevel(surf, rect, raised=True, t=3):
    """绘制经典 3D 斜角边框。"""
    x, y, w, h = rect
    hi = C_LIGHT if raised else C_SHADOW
    lo = C_SHADOW if raised else C_LIGHT
    t = min(t, w // 2, h // 2)
    # 高光（上 + 左）
    pygame.draw.polygon(surf, hi, [
        (x, y), (x + w - 1, y), (x + w - 1 - t, y + t),
        (x + t, y + t), (x + t, y + h - 1 - t), (x, y + h - 1),
    ])
    # 阴影（下 + 右）
    pygame.draw.polygon(surf, lo, [
        (x + w - 1, y), (x + w - 1, y + h - 1), (x, y + h - 1),
        (x + t, y + h - 1 - t), (x + w - 1 - t, y + h - 1 - t), (x + w - 1 - t, y + t),
    ])


def sunken_panel(surf, rect, t=3):
    """凹陷面板（黑底 + 内斜角）。"""
    bevel(surf, rect, raised=False, t=t)
    inner = pygame.Rect(rect).inflate(-2 * t, -2 * t)
    pygame.draw.rect(surf, C_LED_BG, inner)
    return inner


# ============================ 棋盘逻辑 ============================
class Cell:
    __slots__ = ("mine", "open", "flag", "adj", "boom", "wrong")

    def __init__(self):
        self.mine = False
        self.open = False
        self.flag = False
        self.adj = 0
        self.boom = False    # 本局被踩中的那颗雷
        self.wrong = False   # 标错旗（失败时显示）


class Board:
    """纯逻辑层：布雷、翻格、胜负判定，不涉及任何绘制。"""

    def __init__(self, cols, rows, mines):
        self.cols = cols
        self.rows = rows
        self.total_mines = mines
        self.cells = [[Cell() for _ in range(cols)] for _ in range(rows)]
        self.armed = False       # 是否已布雷（首次点击后才布）
        self.state = ST_PLAY
        self.flags = 0
        self.opened = 0
        self.time = 0

    # ---------- 基础 ----------
    def inside(self, c, r):
        return 0 <= c < self.cols and 0 <= r < self.rows

    def neighbors(self, c, r):
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                nc, nr = c + dc, r + dr
                if self.inside(nc, nr):
                    yield nc, nr

    def cell(self, c, r):
        return self.cells[r][c]

    # ---------- 布雷（首次点击安全）----------
    def arm(self, safe_c, safe_r):
        """在 (safe_c, safe_r) 及其周围之外随机布雷，保证首点必为空。"""
        forbidden = {(safe_c, safe_r)}
        forbidden.update(self.neighbors(safe_c, safe_r))

        candidates = [(c, r) for r in range(self.rows) for c in range(self.cols)
                      if (c, r) not in forbidden]
        if len(candidates) < self.total_mines:      # 极端情况兜底：只排除中心格
            candidates = [(c, r) for r in range(self.rows) for c in range(self.cols)
                          if (c, r) != (safe_c, safe_r)]

        for c, r in random.sample(candidates, self.total_mines):
            self.cell(c, r).mine = True

        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cell(c, r)
                cell.adj = sum(1 for nc, nr in self.neighbors(c, r)
                               if self.cell(nc, nr).mine)
        self.armed = True

    # ---------- 翻格 ----------
    def reveal(self, c, r):
        """左键翻开。返回 True 表示踩雷。"""
        if self.state != ST_PLAY or not self.inside(c, r):
            return False
        cell = self.cell(c, r)
        if cell.flag or cell.open:
            return False

        if not self.armed:
            self.arm(c, r)

        if cell.mine:
            cell.open = True
            cell.boom = True
            self.lose()
            return True

        self._flood(c, r)
        self._check_win()
        return False

    def _flood(self, c, r):
        """迭代式洪水填充，遇到数字停止扩散。"""
        stack = [(c, r)]
        while stack:
            cc, cr = stack.pop()
            cell = self.cell(cc, cr)
            if cell.open or cell.flag or cell.mine:
                continue
            cell.open = True
            self.opened += 1
            if cell.adj == 0:
                for nc, nr in self.neighbors(cc, cr):
                    if not self.cell(nc, nr).open:
                        stack.append((nc, nr))

    # ---------- 标旗 ----------
    def toggle_flag(self, c, r):
        if self.state != ST_PLAY or not self.inside(c, r):
            return
        cell = self.cell(c, r)
        if cell.open:
            return
        cell.flag = not cell.flag
        self.flags += 1 if cell.flag else -1

    # ---------- 快速翻开（和弦）----------
    def chord(self, c, r):
        """数字格上，若周围旗数 == 数字，翻开其余未标旗的邻格。"""
        if self.state != ST_PLAY or not self.inside(c, r):
            return False
        cell = self.cell(c, r)
        if not cell.open or cell.adj == 0:
            return False
        nbs = [(nc, nr) for nc, nr in self.neighbors(c, r) if not self.cell(nc, nr).open]
        if sum(1 for nc, nr in nbs if self.cell(nc, nr).flag) != cell.adj:
            return False
        boom = False
        for nc, nr in nbs:
            if not self.cell(nc, nr).flag:
                if self.reveal(nc, nr):
                    boom = True
        return boom

    # ---------- 胜负 ----------
    def _check_win(self):
        need = self.cols * self.rows - self.total_mines
        if self.opened >= need:
            self.win()

    def win(self):
        self.state = ST_WON
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cell(c, r)
                if cell.mine and not cell.flag:
                    cell.flag = True
        self.flags = self.total_mines

    def lose(self):
        self.state = ST_LOST
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cell(c, r)
                if cell.mine and not cell.flag and not cell.boom:
                    cell.open = True          # 展示所有未标出的雷
                if cell.flag and not cell.mine:
                    cell.wrong = True         # 标错的旗

    def tick(self):
        if self.state == ST_PLAY and self.armed and self.time < 999:
            self.time += 1


# ============================ 渲染层 ============================
class Renderer:
    def __init__(self):
        self.f_num = get_font(24, bold=True)
        self.f_led = get_font(30, bold=True)
        self.f_title = get_font(46, bold=True)
        self.f_menu = get_font(22, bold=True)
        self.f_small = get_font(16)
        self.f_hint = get_font(18)

    # ---------- 数码管 ----------
    def led(self, surf, rect, value):
        inner = sunken_panel(surf, rect, t=3)
        v = max(-99, min(999, value))
        if v < 0:
            txt = "-" + str(-v).zfill(2)
        else:
            txt = str(v).zfill(3)
        img = self.f_led.render(txt, True, C_LED_FG)
        surf.blit(img, img.get_rect(center=inner.center))

    # ---------- 笑脸按钮 ----------
    def face(self, surf, center, face_state):
        r = FACE_R
        rect = pygame.Rect(center[0] - r - 4, center[1] - r - 4, 2 * r + 8, 2 * r + 8)
        pygame.draw.rect(surf, C_FACE, rect)
        bevel(surf, rect, raised=(face_state != "press"), t=3)

        cx, cy = center
        pygame.draw.circle(surf, C_YELLOW, (cx, cy), r)
        pygame.draw.circle(surf, C_BLACK, (cx, cy), r, 2)

        eye_dx, eye_dy = r // 3, r // 3
        if face_state == "cool":                      # 胜利：墨镜
            pygame.draw.rect(surf, C_BLACK, (cx - r + 4, cy - 8, r * 2 - 8, 9), border_radius=3)
            pygame.draw.line(surf, C_BLACK, (cx - r + 2, cy - 6), (cx + r - 2, cy - 6), 3)
        elif face_state == "dead":                    # 失败：X 眼
            for sx in (-1, 1):
                ex = cx + sx * eye_dx
                pygame.draw.line(surf, C_BLACK, (ex - 4, cy - eye_dy - 4), (ex + 4, cy - eye_dy + 4), 2)
                pygame.draw.line(surf, C_BLACK, (ex - 4, cy - eye_dy + 4), (ex + 4, cy - eye_dy - 4), 2)
        else:
            for sx in (-1, 1):
                pygame.draw.circle(surf, C_BLACK, (cx + sx * eye_dx, cy - eye_dy), max(2, r // 8))

        mouth = pygame.Rect(cx - r // 2, cy - 2, r, r * 0.8)
        if face_state == "dead":                      # 撇嘴
            pygame.draw.arc(surf, C_BLACK, mouth, 0, math.pi, 2)
        elif face_state == "press":                   # 惊讶 O 嘴
            pygame.draw.ellipse(surf, C_BLACK, (cx - 5, cy + 5, 10, 12))
        else:                                         # 微笑
            pygame.draw.arc(surf, C_BLACK, mouth, math.pi, 2 * math.pi, 2)
        return rect

    # ---------- 单个格子 ----------
    def cell(self, surf, rect, cell):
        x, y, w, h = rect
        if not cell.open:
            pygame.draw.rect(surf, C_FACE, rect)
            bevel(surf, rect, raised=True, t=3)
            if cell.flag:
                self._flag(surf, rect, wrong=cell.wrong)
            return

        # 已翻开
        bg = C_BOOM_BG if cell.boom else C_OPEN_BG
        pygame.draw.rect(surf, bg, rect)
        pygame.draw.rect(surf, C_SHADOW, rect, 1)

        if cell.mine:
            self._mine(surf, rect)
        elif cell.wrong:
            self._flag(surf, rect, wrong=True)
        elif cell.adj > 0:
            img = self.f_num.render(str(cell.adj), True, NUM_COLORS[cell.adj])
            surf.blit(img, img.get_rect(center=rect.center))

    def _mine(self, surf, rect):
        cx, cy = rect.center
        r = rect.width // 5
        # 八向尖刺
        for i in range(4):
            a = i * math.pi / 4
            dx, dy = math.cos(a) * (r + 4), math.sin(a) * (r + 4)
            pygame.draw.line(surf, C_BLACK, (cx - dx, cy - dy), (cx + dx, cy + dy), 2)
        pygame.draw.circle(surf, C_BLACK, (cx, cy), r)
        pygame.draw.circle(surf, C_LIGHT, (cx - r // 2, cy - r // 2), max(2, r // 3))

    def _flag(self, surf, rect, wrong=False):
        cx, cy = rect.center
        pole_h = rect.height // 2
        top = cy - pole_h // 2
        pygame.draw.line(surf, C_BLACK, (cx, top), (cx, top + pole_h), 2)          # 旗杆
        pygame.draw.polygon(surf, C_RED, [                                          # 旗面
            (cx, top), (cx + pole_h // 2, top + pole_h // 4), (cx, top + pole_h // 2),
        ])
        pygame.draw.line(surf, C_BLACK, (cx - 6, top + pole_h), (cx + 6, top + pole_h), 3)  # 底座
        if wrong:                                                                   # 标错的旗打红叉
            d = rect.width // 4
            pygame.draw.line(surf, C_RED, (cx - d, cy - d), (cx + d, cy + d), 3)
            pygame.draw.line(surf, C_RED, (cx - d, cy + d), (cx + d, cy - d), 3)


# ============================ 游戏主体 ============================
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("扫雷 Minesweeper")
        self.ren = Renderer()
        self.diff_index = 0
        self.board = None
        self.screen = None
        self.menu = True
        self.face_state = "smile"
        self.face_rect = None
        self.origin = (0, 0)
        self.last_tick = 0
        self.clock = pygame.time.Clock()
        self._menu_rects = []
        self._tip_rect = pygame.Rect(0, 0, 0, 0)
        self.set_difficulty(0, start=False)

    # ---------- 尺寸 / 难度 ----------
    def size_for(self, idx):
        d = DIFFICULTIES[idx]
        w = d["cols"] * CELL + PAD * 2
        h = d["rows"] * CELL + PAD * 2 + HUD_H
        return max(360, w), max(320, h)

    def _board_origin(self, sw, sh, d):
        """棋盘在窗口内居中定位。

        初级棋盘仅 288px 宽，会被 size_for 的 360px 下限撑宽，
        所以不能直接写 `(PAD, HUD_H + PAD)`——那样左留白 10px、右留白 62px。
        这里按窗口实际尺寸反算，保证左右、上下留白一致。
        """
        ox = max(PAD, (sw - d["cols"] * CELL) // 2)
        oy = HUD_H + max(PAD, (sh - HUD_H - d["rows"] * CELL) // 2)
        return ox, oy

    def set_difficulty(self, idx, start=True):
        self.diff_index = idx % len(DIFFICULTIES)
        d = DIFFICULTIES[self.diff_index]
        w, h = self.size_for(self.diff_index)
        self.screen = pygame.display.set_mode((w, h))
        self.board = Board(d["cols"], d["rows"], d["mines"])
        self.origin = self._board_origin(w, h, d)
        self.face_state = "smile"
        self.last_tick = pygame.time.get_ticks()
        if start:
            self.menu = False

    def restart(self):
        d = DIFFICULTIES[self.diff_index]
        self.board = Board(d["cols"], d["rows"], d["mines"])
        self.face_state = "smile"
        self.last_tick = pygame.time.get_ticks()
        self.menu = False

    # ---------- 坐标换算 ----------
    def pick(self, pos):
        mx, my = pos
        ox, oy = self.origin
        c = (mx - ox) // CELL
        r = (my - oy) // CELL
        if 0 <= c < self.board.cols and 0 <= r < self.board.rows and mx >= ox and my >= oy:
            return c, r
        return None

    # ---------- 输入 ----------
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            return False

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return False
            if ev.key == pygame.K_F2:
                self.restart()
            elif ev.key in (pygame.K_1, pygame.K_KP1):
                self.set_difficulty(0)
            elif ev.key in (pygame.K_2, pygame.K_KP2):
                self.set_difficulty(1)
            elif ev.key in (pygame.K_3, pygame.K_KP3):
                self.set_difficulty(2)
            elif ev.key == pygame.K_m:
                self.menu = True
            return True

        if self.menu:
            self._menu_event(ev)
            return True

        if ev.type == pygame.MOUSEBUTTONDOWN:
            if self.face_rect and self.face_rect.collidepoint(ev.pos):
                if ev.button == 1:
                    self.face_state = "press"
                return True
            if ev.button == 1:
                self.face_state = "press"
            elif ev.button == 3:
                hit = self.pick(ev.pos)
                if hit:
                    self.board.toggle_flag(*hit)
            elif ev.button == 2:
                hit = self.pick(ev.pos)
                if hit:
                    self.board.chord(*hit)

        elif ev.type == pygame.MOUSEBUTTONUP:
            if self.face_rect and self.face_rect.collidepoint(ev.pos) and ev.button == 1:
                self.restart()
                return True
            if ev.button == 1:
                self.face_state = self._face_for_state()
                hit = self.pick(ev.pos)
                if hit and self.board.state == ST_PLAY:
                    # 左右键同按 = 和弦：右键仍按住时，松开左键不能当成普通翻开。
                    # （原先无论右键是否按住都直接 reveal，和弦分支永远走不到）
                    if pygame.mouse.get_pressed()[2]:
                        self.board.chord(*hit)
                    else:
                        self.board.reveal(*hit)
                    self.face_state = self._face_for_state()
            elif ev.button == 3:
                if pygame.mouse.get_pressed()[0]:
                    h2 = self.pick(ev.pos)
                    if h2:
                        self.board.chord(*h2)
                self.face_state = self._face_for_state()

        return True

    def _menu_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, rect in enumerate(self._menu_rects):
                if rect.collidepoint(ev.pos):
                    self.set_difficulty(i)
                    return

    def _face_for_state(self):
        if self.board.state == ST_WON:
            return "cool"
        if self.board.state == ST_LOST:
            return "dead"
        return "smile"

    # ---------- 更新 ----------
    def update(self):
        now = pygame.time.get_ticks()
        if not self.menu and self.board.state == ST_PLAY:
            if now - self.last_tick >= 1000:
                self.board.tick()
                self.last_tick = now
        else:
            self.last_tick = now

        # 表情跟随胜负状态自动同步（按下时的惊讶脸保留）
        if not self.menu:
            st = self.board.state
            if st == ST_WON:
                self.face_state = "cool"
            elif st == ST_LOST:
                self.face_state = "dead"
            elif self.face_state in ("cool", "dead"):
                self.face_state = "smile"

    # ---------- 绘制 ----------
    def draw_hud(self):
        sw = self.screen.get_width()
        hud = pygame.Rect(0, 0, sw, HUD_H)
        pygame.draw.rect(self.screen, C_FACE, hud)
        bevel(self.screen, (PAD - 4, 6, sw - 2 * (PAD - 4), HUD_H - 12), raised=False, t=3)

        # 剩余雷数
        self.ren.led(self.screen, pygame.Rect(PAD + 4, 13, LED_W, LED_H),
                     self.board.total_mines - self.board.flags)
        # 笑脸
        self.face_rect = self.ren.face(self.screen, (sw // 2, HUD_H // 2), self.face_state)
        # 计时
        self.ren.led(self.screen, pygame.Rect(sw - PAD - 4 - LED_W, 13, LED_W, LED_H),
                     self.board.time)

    def draw_board(self):
        b = self.board
        ox, oy = self.origin
        bw, bh = b.cols * CELL, b.rows * CELL
        # 外框
        frame = pygame.Rect(ox - PAD + 4, oy - PAD + 4, bw + 2 * (PAD - 4), bh + 2 * (PAD - 4))
        pygame.draw.rect(self.screen, C_FACE, frame)
        bevel(self.screen, frame, raised=False, t=3)

        for r in range(b.rows):
            for c in range(b.cols):
                rect = pygame.Rect(ox + c * CELL, oy + r * CELL, CELL, CELL)
                self.ren.cell(self.screen, rect, b.cell(c, r))

    def draw_overlay(self):
        if self.board.state == ST_PLAY:
            return
        b = self.board
        sw, sh = self.screen.get_size()
        won = b.state == ST_WON
        title = "你赢了！" if won else "踩雷了…"
        color = (40, 140, 60) if won else (180, 40, 40)

        panel = pygame.Rect(0, 0, 300, 132)
        panel.center = (sw // 2, sh // 2)
        shade = pygame.Surface((sw, sh), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 90))
        self.screen.blit(shade, (0, 0))

        pygame.draw.rect(self.screen, C_FACE, panel, border_radius=8)
        bevel(self.screen, panel, raised=True, t=3)
        t = self.ren.f_title.render(title, True, color)
        self.screen.blit(t, t.get_rect(center=(panel.centerx, panel.top + 38)))
        info = self.ren.f_hint.render(f"用时 {b.time} 秒   ·   {DIFFICULTIES[self.diff_index]['name']}",
                                      True, C_DARK)
        self.screen.blit(info, info.get_rect(center=(panel.centerx, panel.top + 80)))
        tip = self.ren.f_small.render("F2 / 点笑脸 重新开始，M 返回菜单", True, C_SHADOW)
        self.screen.blit(tip, tip.get_rect(center=(panel.centerx, panel.top + 108)))

    def _menu_geometry(self, sh, n):
        """菜单纵向布局 → (标题中心 y, 副标题中心 y, 按钮起始 y, 按钮高, 按钮间距, 提示中心 y)。

        空间宽裕时沿用原始间距；窗口装不下时按 间距 → 按钮高度 → 整体上移 的顺序压缩。
        初级窗口只有 370px 高，硬编码的 y0=160 会让第三个按钮越过底边并与提示文字重叠。
        """
        h_title = self.ren.f_title.get_height()
        h_small = self.ren.f_small.get_height()
        tip_y = sh - 34
        limit = tip_y - h_small // 2 - 10          # 按钮块底边的下限

        y_title, y_sub, y0 = 76, 112, 160
        for gap, bh in ((16, 62), (12, 62), (12, 58), (10, 56)):
            if y0 + n * bh + (n - 1) * gap <= limit:
                return y_title, y_sub, y0, bh, gap, tip_y

        # 压到最小仍装不下：按钮块贴住底部上限，标题区一道上移
        gap, bh = 10, 56
        need = n * bh + (n - 1) * gap
        y0 = max(0, limit - need)
        y_sub = min(y_sub, y0 - 12 - h_small // 2)
        y_title = min(y_title, y_sub - h_small // 2 - 6 - h_title // 2)
        return y_title, y_sub, y0, bh, gap, tip_y

    def _menu_tip(self, sw):
        """底部提示按窗口宽度选取最长的可容纳版本，窄窗口下不会横向出界。"""
        for text in ("左键翻开 · 右键插旗 · 中键快速翻开 · F2 重开 · ESC 退出",
                     "左键翻开 · 右键插旗 · 中键和弦 · F2 重开",
                     "左键翻开 · 右键插旗 · F2 重开"):
            if self.ren.f_small.size(text)[0] <= sw - 20:
                return text
        return "左键翻开 · 右键插旗"

    def draw_menu(self):
        sw, sh = self.screen.get_size()
        self.screen.fill((232, 232, 232))
        n = len(DIFFICULTIES)
        y_title, y_sub, y0, bh, gap, tip_y = self._menu_geometry(sh, n)

        title = self.ren.f_title.render("扫  雷", True, (40, 40, 40))
        self.screen.blit(title, title.get_rect(center=(sw // 2, y_title)))
        sub = self.ren.f_small.render("Minesweeper · pygame", True, C_SHADOW)
        self.screen.blit(sub, sub.get_rect(center=(sw // 2, y_sub)))

        bw = min(250, max(150, sw - 60))
        self._menu_rects = []
        for i, d in enumerate(DIFFICULTIES):
            rect = pygame.Rect(sw // 2 - bw // 2, y0 + i * (bh + gap), bw, bh)
            self._menu_rects.append(rect)
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (214, 226, 245) if hovered else C_FACE, rect, border_radius=6)
            bevel(self.screen, rect, raised=True, t=3)
            # 两行文字的内缩量随按钮高度等比收缩，矮按钮里文字也不会出框
            off1 = max(7, min(9, bh * 3 // 20))
            off2 = max(11, min(15, bh // 4))
            nm = self.ren.f_menu.render(d["name"], True, (20, 60, 140))
            ds = self.ren.f_small.render(d["desc"], True, C_DARK)
            self.screen.blit(nm, nm.get_rect(midleft=(rect.left + 22, rect.centery - off1)))
            self.screen.blit(ds, ds.get_rect(midleft=(rect.left + 22, rect.centery + off2)))

        tip = self.ren.f_small.render(self._menu_tip(sw), True, C_SHADOW)
        self._tip_rect = tip.get_rect(center=(sw // 2, tip_y))
        self.screen.blit(tip, self._tip_rect)

    def draw(self):
        if self.screen is None:
            return
        self.screen.fill(C_FACE)
        if self.menu:
            self.draw_menu()
        else:
            self.draw_hud()
            self.draw_board()
            self.draw_overlay()
        pygame.display.flip()

    # ---------- 主循环 ----------
    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if not self.handle_event(ev):
                    running = False
            self.update()
            self.draw()
            self.clock.tick(60)
        pygame.quit()


# ============================ 无头自测 ============================
def smoke_test():
    """SDL dummy 驱动下无头跑通完整流程，返回退出码（0 = 全部通过）。

    覆盖：三档难度的必胜路径与必败路径、首击安全、每格数字校验、
    和弦（旗数匹配 / 不足两种情形）、随机对局计数一致性、
    菜单几何（按钮与提示不越界）以及胜负结算面板绘制。
    """
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    random.seed(20260920)

    fails = []
    total = 0

    def check(name, cond, detail=""):
        nonlocal total
        total += 1
        if cond:
            print(f"  [ok]   {name}")
        else:
            fails.append(f"{name}   {detail}")
            print(f"  [FAIL] {name}   {detail}")

    def mines_of(b):
        return [(c, r) for r in range(b.rows) for c in range(b.cols) if b.cell(c, r).mine]

    def opened_of(b):
        return [(c, r) for r in range(b.rows) for c in range(b.cols) if b.cell(c, r).open]

    def flags_of(b):
        return [(c, r) for r in range(b.rows) for c in range(b.cols) if b.cell(c, r).flag]

    def find_chordable(b):
        """找一个可验证和弦的数字格：adj > 0 且至少有一个未翻开的非雷邻格。"""
        for c, r in opened_of(b):
            if b.cell(c, r).adj == 0:
                continue
            nb = [(nc, nr) for nc, nr in b.neighbors(c, r) if not b.cell(nc, nr).open]
            if any(not b.cell(nc, nr).mine for nc, nr in nb):
                return c, r, nb
        return None

    g = Game()

    # ---------- 1. 三档难度：必胜路径（逐格翻开全部非雷格） ----------
    print("\n[1] 三档难度必胜路径")
    for idx, d in enumerate(DIFFICULTIES):
        g.set_difficulty(idx)
        g.menu = False
        b = g.board
        b.arm(d["cols"] // 2, d["rows"] // 2)
        need = d["cols"] * d["rows"] - d["mines"]
        safe = [(c, r) for r in range(b.rows) for c in range(b.cols)
                if not b.cell(c, r).mine]
        for i, (c, r) in enumerate(safe):
            b.reveal(c, r)
            if i % 16 == 0:                 # 边翻边渲染，顺带压一遍绘制路径
                g.update()
                g.draw()
        g.draw()
        check(f"{d['name']}：必胜路径判定为胜利", b.state == ST_WON, f"state={b.state}")
        check(f"{d['name']}：胜利时翻开数 = 非雷格总数", b.opened == need,
              f"opened={b.opened} != {need}")
        check(f"{d['name']}：胜利时旗数 = 雷数", b.flags == d["mines"],
              f"flags={b.flags} != {d['mines']}")
        check(f"{d['name']}：盘上雷数正确", len(mines_of(b)) == d["mines"],
              f"{len(mines_of(b))}")
        check(f"{d['name']}：没有任何雷格被翻开",
              not any(b.cell(c, r).open for c, r in mines_of(b)))

    # ---------- 2. 三档难度：必败路径 ----------
    print("\n[2] 三档难度必败路径")
    for idx, d in enumerate(DIFFICULTIES):
        g.set_difficulty(idx)
        g.menu = False
        b = g.board
        b.arm(0, 0)
        mc, mr = mines_of(b)[0]
        b.reveal(mc, mr)
        g.update()
        g.draw()
        check(f"{d['name']}：踩雷判定为失败", b.state == ST_LOST, f"state={b.state}")
        check(f"{d['name']}：踩中的那颗雷被标记 boom", b.cell(mc, mr).boom)
        check(f"{d['name']}：失败后全部地雷展示",
              all(b.cell(c, r).open for c, r in mines_of(b)))
        closed_safe = [(c, r) for r in range(b.rows) for c in range(b.cols)
                       if not b.cell(c, r).open and not b.cell(c, r).mine]
        check(f"{d['name']}：失败后拒绝继续翻开",
              bool(closed_safe) and b.reveal(*closed_safe[0]) is False,
              f"closed_safe={len(closed_safe)}")

    # ---------- 3. 首击安全 + 每格数字 ----------
    print("\n[3] 首击安全与数字正确性")
    for idx, d in enumerate(DIFFICULTIES):
        bad = None
        for _ in range(40):
            b = Board(d["cols"], d["rows"], d["mines"])
            c, r = random.randrange(d["cols"]), random.randrange(d["rows"])
            b.reveal(c, r)
            if b.cell(c, r).mine or b.cell(c, r).adj != 0:
                bad = (c, r, b.cell(c, r).mine, b.cell(c, r).adj)
                break
        check(f"{d['name']}：首击 40 次均安全且周围一圈无雷", bad is None, f"{bad}")

        b = Board(d["cols"], d["rows"], d["mines"])
        b.arm(d["cols"] // 2, d["rows"] // 2)
        wrong = [(c, r) for r in range(b.rows) for c in range(b.cols)
                 if b.cell(c, r).adj != sum(1 for nc, nr in b.neighbors(c, r)
                                            if b.cell(nc, nr).mine)]
        check(f"{d['name']}：每格数字 = 邻雷数", not wrong, f"不符 {wrong[:4]}")

    # ---------- 4. 和弦 ----------
    print("\n[4] 和弦（数字格上快速翻开周围）")
    b = Board(9, 9, 10)
    b.arm(4, 4)
    b.reveal(4, 4)
    t = find_chordable(b)
    check("和弦：洪水区边界存在可验证的数字格", t is not None, "未找到")
    if t:
        c, r, nb = t
        b.chord(c, r)                                   # 未插旗 -> 不应翻开
        touched = [x for x in nb if not b.cell(*x).mine and b.cell(*x).open]
        check("和弦：旗数不足时保持不动", not touched, f"被误翻开 {touched}")
        for nc, nr in nb:                               # 补满旗
            if b.cell(nc, nr).mine:
                b.toggle_flag(nc, nr)
        b.chord(c, r)
        missed = [x for x in nb if not b.cell(*x).mine and not b.cell(*x).open]
        check("和弦：旗数匹配时翻开其余安全邻格", not missed, f"未翻开 {missed}")

    # ---------- 5. 随机对局一致性 ----------
    print("\n[5] 随机对局 400 帧")
    g.set_difficulty(0)
    g.menu = False
    frames = 0
    for _ in range(400):
        b = g.board                        # 每轮重新绑定：restart 会换一张新盘
        c, r = random.randrange(b.cols), random.randrange(b.rows)
        if random.random() < 0.25:
            b.toggle_flag(c, r)
        else:
            b.reveal(c, r)
        if b.state != ST_PLAY:
            g.restart()
        g.update()
        g.draw()
        frames += 1
    b = g.board
    check("随机对局后 opened 计数与实际翻开格数一致", b.opened == len(opened_of(b)),
          f"{b.opened} != {len(opened_of(b))}")
    check("随机对局后 flags 计数与实际旗数一致", b.flags == len(flags_of(b)),
          f"{b.flags} != {len(flags_of(b))}")
    check("随机对局后盘上雷数正确", len(mines_of(b)) == b.total_mines,
          f"{len(mines_of(b))} != {b.total_mines}")

    # ---------- 6. 菜单几何与结算面板 ----------
    print("\n[6] 菜单几何与结算面板")
    for idx, d in enumerate(DIFFICULTIES):
        g.set_difficulty(idx)
        g.menu = True
        g.draw()
        sw, sh = g.screen.get_size()
        rects = g._menu_rects
        check(f"{d['name']}：难度按钮全部落在窗口内",
              len(rects) == len(DIFFICULTIES)
              and all(0 <= r.left and r.right <= sw and 0 <= r.top and r.bottom <= sh
                      for r in rects),
              f"窗口 {sw}x{sh} 按钮 {[tuple(r) for r in rects]}")
        check(f"{d['name']}：按钮块不越过底部提示行",
              rects[-1].bottom <= g._tip_rect.top,
              f"按钮底 {rects[-1].bottom} / 提示顶 {g._tip_rect.top}")
        check(f"{d['name']}：提示文字不横向出界",
              0 <= g._tip_rect.left and g._tip_rect.right <= sw,
              f"提示 {g._tip_rect.left}..{g._tip_rect.right} / 窗口宽 {sw}")
        right_gap = sw - (g.origin[0] + d["cols"] * CELL)
        check(f"{d['name']}：棋盘左右留白对称",
              abs(g.origin[0] - right_gap) <= 1,
              f"左 {g.origin[0]} / 右 {right_gap}")

        g.menu = False
        g.board.arm(0, 0)
        g.board.lose()
        g.draw()
        shade = g.screen.get_at((2, 2))[:3]
        check(f"{d['name']}：失败结算面板带遮罩", sum(shade) < sum(C_FACE) - 30, f"{shade}")
        g.board.win()
        g.draw()
        check(f"{d['name']}：胜利结算面板可绘制", g.board.state == ST_WON)

    print("\n" + "=" * 56)
    if fails:
        print(f"[SMOKE FAILED] {total - len(fails)}/{total} 项通过")
        for f in fails:
            print("  [FAIL] " + f)
        print("=" * 56)
        pygame.quit()
        return 1
    print(f"[SMOKE OK] 全部 {total} 项通过 · 随机对局 {frames} 帧")
    print("=" * 56)
    pygame.quit()
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(smoke_test())
    else:
        Game().run()
