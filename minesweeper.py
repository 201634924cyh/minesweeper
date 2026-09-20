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

# 难度菜单布局（菜单自带窗口尺寸，不能沿用棋盘窗口——初级盘只有 370px 高，
# 菜单需要 378px 才放得下三张卡片，否则第三张会被切掉、底部提示还会压在卡片上）
MENU_W = 380              # 菜单窗口宽度下限（实际宽度还会按底部提示文字撑开）
MENU_TOP = 160            # 第一张卡片的 y
MENU_CARD_W, MENU_CARD_H = 250, 62
MENU_CARD_GAP = 16
MENU_TIP_H = 44           # 底部提示文字预留高度
MENU_TIP = "左键翻开 · 右键插旗 · 中键快速翻开 · F2 重开 · ESC 退出"

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
# 中文字体候选，按 Windows -> macOS -> Linux 排序，pygame 逐个匹配取第一个命中的。
# 必须覆盖三大平台：只列 Windows 字体的话，Linux / macOS 上中文会全部渲染成豆腐块 □。
_FONT_FAMILIES = ("microsoftyaheiui,microsoftyahei,msyh,simhei,dengxian,simsun,"
                  "pingfangsc,hiraginosansgb,stheiti,songtisc,"
                  "notosanscjksc,notosanscjk,wenquanyimicrohei,wenquanyizenhei,"
                  "droidsansfallback,sourcehansanssc,arialunicodems")

_FONT_CACHE = {}      # (size, bold) -> pygame.font.Font
_FONT_PATH = {}       # bold -> 字体文件路径 | None


def _has_cjk(font):
    """字体是否真的带中文字形。缺字形时 metrics() 返回 None，画出来就是豆腐块。"""
    try:
        return all(v is not None for v in font.metrics("扫雷"))
    except Exception:
        return False


def _resolve_font_path(bold=False):
    """定位一个真正能画中文的字体文件；实在找不到返回 None。"""
    if bold in _FONT_PATH:
        return _FONT_PATH[bold]

    path = pygame.font.match_font(_FONT_FAMILIES, bold=bold)
    if path:
        try:
            if _has_cjk(pygame.font.Font(path, 24)):
                _FONT_PATH[bold] = path
                return path
        except Exception:
            pass

    # 候选全落空时兜底：遍历系统字体，取第一个真能画出“扫”字的。
    for name in sorted(pygame.font.get_fonts()):
        candidate = pygame.font.match_font(name, bold=bold)
        if not candidate:
            continue
        try:
            if _has_cjk(pygame.font.Font(candidate, 24)):
                _FONT_PATH[bold] = candidate
                return candidate
        except Exception:
            continue

    _FONT_PATH[bold] = None
    return None


def get_font(size, bold=False):
    """优先使用系统中文字体，找不到则退回默认字体（此时中文会变豆腐块）。"""
    key = (size, bold)
    font = _FONT_CACHE.get(key)
    if font is None:
        path = _resolve_font_path(bold)
        try:
            font = pygame.font.Font(path, size) if path else pygame.font.Font(None, size)
        except Exception:
            font = pygame.font.Font(None, size)
        _FONT_CACHE[key] = font
    return font


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
        """在 (safe_c, safe_r) 及其周围之外随机布雷，保证首点必为空。

        幂等：已布雷的棋盘再调用一次不会叠加布雷。
        """
        if self.armed:
            return
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
    def face(self, surf, center, state, face_state):
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
        self.set_difficulty(0, start=False)
        self.open_menu()

    # ---------- 尺寸 / 难度 ----------
    def size_for(self, idx):
        d = DIFFICULTIES[idx]
        w = d["cols"] * CELL + PAD * 2
        h = d["rows"] * CELL + PAD * 2 + HUD_H
        return max(360, w), max(320, h)

    def menu_size(self):
        """菜单所需窗口尺寸：三张卡片 + 底部提示，一个都不能少。

        宽度按底部提示文字的实际渲染宽度撑开，否则提示会被窗口左右裁掉。
        """
        cards = len(DIFFICULTIES) * MENU_CARD_H + (len(DIFFICULTIES) - 1) * MENU_CARD_GAP
        tip_w = self.ren.f_small.render(MENU_TIP, True, C_SHADOW).get_width()
        w = max(MENU_W, MENU_CARD_W + 80, tip_w + 24)
        return w, MENU_TOP + cards + MENU_TIP_H

    def open_menu(self):
        """切到难度菜单，并把窗口调整成菜单需要的尺寸。"""
        self.menu = True
        self.screen = pygame.display.set_mode(self.menu_size())
        self.last_tick = pygame.time.get_ticks()

    def set_difficulty(self, idx, start=True):
        self.diff_index = idx % len(DIFFICULTIES)
        d = DIFFICULTIES[self.diff_index]
        w, h = self.size_for(self.diff_index)
        self.screen = pygame.display.set_mode((w, h))
        self.board = Board(d["cols"], d["rows"], d["mines"])
        self.origin = (PAD, HUD_H + PAD)
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
                self.open_menu()
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
                    self.board.reveal(*hit)
                    self.face_state = self._face_for_state()
                elif self.board.state == ST_PLAY:
                    # 同时按下左右键 => 和弦
                    if pygame.mouse.get_pressed()[2]:
                        h2 = self.pick(ev.pos)
                        if h2:
                            self.board.chord(*h2)
            elif ev.button == 3:
                if pygame.mouse.get_pressed()[0]:
                    h2 = self.pick(ev.pos)
                    if h2:
                        self.board.chord(*h2)
                self.face_state = self._face_for_state()

        return True

    def _menu_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, rect in enumerate(getattr(self, "_menu_rects", [])):
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
        self.face_rect = self.ren.face(self.screen, (sw // 2, HUD_H // 2),
                                       self.board.state, self.face_state)
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

    def draw_menu(self):
        sw, sh = self.screen.get_size()
        self.screen.fill((232, 232, 232))
        title = self.ren.f_title.render("扫  雷", True, (40, 40, 40))
        self.screen.blit(title, title.get_rect(center=(sw // 2, 76)))
        sub = self.ren.f_small.render("Minesweeper · pygame", True, C_SHADOW)
        self.screen.blit(sub, sub.get_rect(center=(sw // 2, 112)))

        self._menu_rects = []
        cards_h = len(DIFFICULTIES) * MENU_CARD_H + (len(DIFFICULTIES) - 1) * MENU_CARD_GAP
        # 窗口比菜单高时垂直居中，否则贴着 MENU_TOP 往下排（窗口已由 open_menu 保证够大）
        y0 = max(MENU_TOP, (sh - cards_h) // 2)
        for i, d in enumerate(DIFFICULTIES):
            rect = pygame.Rect(sw // 2 - MENU_CARD_W // 2,
                               y0 + i * (MENU_CARD_H + MENU_CARD_GAP),
                               MENU_CARD_W, MENU_CARD_H)
            self._menu_rects.append(rect)
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (214, 226, 245) if hovered else C_FACE, rect, border_radius=6)
            bevel(self.screen, rect, raised=True, t=3)
            nm = self.ren.f_menu.render(d["name"], True, (20, 60, 140))
            ds = self.ren.f_small.render(d["desc"], True, C_DARK)
            self.screen.blit(nm, nm.get_rect(midleft=(rect.left + 22, rect.centery - 9)))
            self.screen.blit(ds, ds.get_rect(midleft=(rect.left + 22, rect.centery + 15)))

        tip = self.ren.f_small.render(MENU_TIP, True, C_SHADOW)
        last_bottom = y0 + cards_h
        self.screen.blit(tip, tip.get_rect(center=(sw // 2, min(sh - 22, last_bottom + 24))))

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
def main():
    """入口：--test 交给 selftest.py 跑完整无头自检（SDL dummy 驱动）。"""
    if "--test" in sys.argv:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import selftest
        sys.exit(0 if selftest.main() else 1)
    Game().run()


if __name__ == "__main__":
    main()
