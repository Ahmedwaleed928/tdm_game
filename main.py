# -*- coding: utf-8 -*-
# TDM Offline - لعبة تصويب جماعي (منظور علوي) ضد بوتات - Kivy
import math, random, time, os
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_SHAPER = True
except Exception:
    HAS_SHAPER = False


def find_font():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, 'fonts', 'arabic.ttf'),
              '/system/fonts/NotoNaskhArabic-Regular.ttf',
              '/system/fonts/NotoSansArabic-Regular.ttf',
              '/system/fonts/DroidSansArabic.ttf'):
        if os.path.exists(p):
            return p
    return None


FONT = find_font()
AR = bool(FONT and HAS_SHAPER)   # لو الخط أو المكتبة ناقصين تشتغل بالإنجليزي تلقائيًا

S = {
    'title': ('حرب الفرق', 'TEAM DEATHMATCH'),
    'goal': ('الهدف: {g} قتلة', 'Goal: {g} kills'),
    'n3': ('3 ضد 3', '3 vs 3'), 'n5': ('5 ضد 5', '5 vs 5'), 'n8': ('8 ضد 8', '8 vs 8'),
    'diff': ('الصعوبة: {d}', 'Difficulty: {d}'),
    'd0': ('سهل', 'Easy'), 'd1': ('متوسط', 'Normal'), 'd2': ('صعب', 'Hard'),
    'w0': ('مسدس', 'Pistol'), 'w1': ('رشاش', 'SMG'),
    'w2': ('بندقية', 'Rifle'), 'w3': ('شوتجن', 'Shotgun'),
    'reload': ('ذخيرة', 'RELOAD'), 'swap': ('سلاح', 'SWAP'),
    'reloading': ('جاري التعبئة...', 'Reloading...'),
    'you': ('أنت', 'You'), 'bot': ('بوت {n}', 'Bot {n}'),
    'kill': ('{a} قتل {b}', '{a} killed {b}'),
    'dead': ('تم قتلك! إعادة الظهور خلال {t}', 'You died! Respawn in {t}'),
    'win': ('فريقك فاز!', 'YOUR TEAM WINS!'),
    'lose': ('الفريق الآخر فاز', 'ENEMY TEAM WINS'),
    'draw': ('تعادل', 'DRAW'),
    'stats': ('قتلاتك {k}   موتاتك {d}', 'Kills {k}   Deaths {d}'),
    'tap': ('المس للعودة للقائمة', 'Tap to return'),
}


def raw(key, /, **kw):
    return S[key][0 if AR else 1].format(**kw)


def shape(s):
    return get_display(arabic_reshaper.reshape(s)) if AR else s


def tx(key, /, **kw):
    return shape(raw(key, **kw))


W, H = 2360, 1420
R = 13
GOAL = 30
MATCH_TIME = 300
WEAPONS = [
    dict(dmg=22, rate=.32, mag=12, spr=.04, spd=850, pel=1, rt=1.1, life=.9),
    dict(dmg=11, rate=.09, mag=30, spr=.10, spd=800, pel=1, rt=1.5, life=.8),
    dict(dmg=18, rate=.13, mag=30, spr=.05, spd=950, pel=1, rt=1.8, life=1.1),
    dict(dmg=9, rate=.85, mag=6, spr=.16, spd=750, pel=6, rt=2.2, life=.45),
]
# (سرعة الدوران, معامل التشتت, سرعة الحركة)
DIFF = [(2.2, 2.2, 115), (3.5, 1.4, 135), (5.5, 0.9, 150)]
BLUE, RED = (.2, .55, 1.0), (1.0, .3, .25)


class Actor:
    def __init__(s, team, player=False, n=0):
        s.team, s.pl, s.name = team, player, n
        s.kills = s.deaths = 0
        s.x = s.y = 0
        s.angle = 0
        s.hp = 100
        s.alive = True
        s.rt = s.inv = s.cd = s.rl = 0
        s.wi = 0
        s.ammo = []
        s.think = random.random() * .3
        s.tgt = None
        s.see = False
        s.strafe = 1
        s.stuck = s.blk = s.wang = 0


def nm(a):
    return raw('you') if a.pl else raw('bot', n=a.name)


class Game(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._tc = {}
        self.state = 'menu'
        self.diff = 1
        self.u = 1
        self.touches = {}
        self.keys = set()
        self.actors, self.bullets, self.feed = [], [], []
        self.score = [0, 0]
        self.tleft = MATCH_TIME
        self.over_t = 0
        self.result = 'draw'
        self.build_map()
        Window.bind(on_key_down=self.kd, on_key_up=self.ku)
        Clock.schedule_interval(self.update, 1 / 30.)

    # ---------- الخريطة ----------
    def build_map(self):
        rnd = random.Random(7)
        ws = [(0, -40, W, 40, 1), (0, H, W, 40, 1), (-40, -40, 40, H + 80, 1), (W, -40, 40, H + 80, 1)]
        for i in range(4):
            for j in range(3):
                if rnd.random() < .82:
                    ws.append((240 + 520 * i, 200 + 400 * j, 320, 220, 0))
        n = 0
        for _ in range(400):
            if n >= 16:
                break
            x, y = rnd.uniform(300, W - 340), rnd.uniform(60, H - 100)
            if all(not (x - 55 < bx + bw and x + 95 > bx and y - 55 < by + bh and y + 95 > by)
                   for bx, by, bw, bh, k in ws):
                ws.append((x, y, 40, 40, 2))
                n += 1
        self.walls = ws

    def hit_wall(self, x, y, r):
        for rx, ry, rw, rh, k in self.walls:
            if rx - r < x < rx + rw + r and ry - r < y < ry + rh + r:
                return True
        return False

    def los(self, x1, y1, x2, y2):
        n = int(math.hypot(x2 - x1, y2 - y1) / 24) + 1
        for i in range(1, n):
            t = i / n
            if self.hit_wall(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, 0):
                return False
        return True

    def move(self, a, dx, dy):
        if not self.hit_wall(a.x + dx, a.y, R):
            a.x += dx
        if not self.hit_wall(a.x, a.y + dy, R):
            a.y += dy

    # ---------- بداية المباراة ----------
    def start(self, n):
        self.actors = []
        for team in (0, 1):
            for i in range(n):
                a = Actor(team, player=(team == 0 and i == 0), n=i + 1 + team * n)
                self.actors.append(a)
                self.respawn(a)
        self.player = self.actors[0]
        self.bullets, self.feed, self.touches = [], [], {}
        self.score = [0, 0]
        self.tleft = MATCH_TIME
        self.state = 'play'

    def respawn(self, a):
        x = y = 100
        for _ in range(60):
            x = random.uniform(70, 170) if a.team == 0 else random.uniform(W - 170, W - 70)
            y = random.uniform(80, H - 80)
            if not self.hit_wall(x, y, 20):
                break
        a.x, a.y, a.hp, a.alive, a.inv = x, y, 100, True, 2.0
        a.angle = 0 if a.team == 0 else math.pi
        a.ammo = [w['mag'] for w in WEAPONS]
        a.wi = 2 if a.pl else random.randrange(4)
        a.cd = a.rl = 0
        a.tgt = None

    # ---------- القتال ----------
    def do_reload(self, a):
        if a.rl <= 0 and a.ammo[a.wi] < WEAPONS[a.wi]['mag']:
            a.rl = WEAPONS[a.wi]['rt']

    def swap(self, a):
        a.wi = (a.wi + 1) % len(WEAPONS)
        a.rl = 0

    def fire(self, a, sm):
        w = WEAPONS[a.wi]
        if a.cd > 0 or a.rl > 0:
            return
        if a.ammo[a.wi] <= 0:
            self.do_reload(a)
            return
        a.cd = w['rate']
        a.ammo[a.wi] -= 1
        a.inv = min(a.inv, 0)
        for _ in range(w['pel']):
            g = a.angle + random.gauss(0, w['spr'] * sm)
            c, s = math.cos(g), math.sin(g)
            self.bullets.append([a.x + c * 12, a.y + s * 12, c * w['spd'], s * w['spd'],
                                 w['dmg'], a.team, w['life'], a])
        if a.ammo[a.wi] <= 0:
            self.do_reload(a)

    def damage(self, e, d, by):
        e.hp -= d
        if e.hp <= 0 and e.alive:
            e.alive = False
            e.rt = 3
            e.deaths += 1
            by.kills += 1
            self.score[by.team] += 1
            self.feed.append([shape(raw('kill', a=nm(by), b=nm(e))), 4.0, by.team])
            self.feed = self.feed[-5:]

    # ---------- ذكاء البوت ----------
    def bot_ai(self, a, dt):
        cfg = DIFF[self.diff]
        a.think -= dt
        if a.think <= 0:
            a.think = random.uniform(.25, .5)
            best, bd = None, 1e18
            for e in self.actors:
                if e.team != a.team and e.alive:
                    d = (e.x - a.x) ** 2 + (e.y - a.y) ** 2
                    if d < bd:
                        best, bd = e, d
            a.tgt = best
            a.see = bool(best) and bd < 620 ** 2 and self.los(a.x, a.y, best.x, best.y)
            a.strafe = random.choice((-1, 1))
        t = a.tgt
        if t is None or not t.alive:
            a.think = 0
            return
        dx, dy = t.x - a.x, t.y - a.y
        d = math.hypot(dx, dy) or 1
        want = math.atan2(dy, dx)
        diff = (want - a.angle + math.pi) % (2 * math.pi) - math.pi
        st = cfg[0] * dt
        a.angle += max(-st, min(st, diff))
        if a.stuck > 0:
            a.stuck -= dt
            ang = a.wang
        elif a.see and d < 300:
            ang = want + math.pi if d < 150 else want + a.strafe * 1.57
        else:
            ang = want
        sp = cfg[2]
        px, py = a.x, a.y
        self.move(a, math.cos(ang) * sp * dt, math.sin(ang) * sp * dt)
        if math.hypot(a.x - px, a.y - py) < sp * dt * .3:
            a.blk += dt
            if a.blk > .35:
                a.blk = 0
                a.stuck = random.uniform(.5, 1.1)
                a.wang = want + random.choice((-1, 1)) * random.uniform(1.2, 2.0)
        else:
            a.blk = 0
        if a.see and abs(diff) < .3 and d < 600:
            self.fire(a, cfg[1])

    def player_step(self, a, dt, mv, aim):
        self.move(a, mv[0] * 165 * dt, mv[1] * 165 * dt)
        if aim and aim[2] > .2:
            a.angle = math.atan2(aim[1], aim[0])
            if aim[2] > .55:
                self.fire(a, 1.0)
        elif (mv[0] or mv[1]) and ' ' in self.keys:
            a.angle = math.atan2(mv[1], mv[0])
        if ' ' in self.keys:
            self.fire(a, 1.0)

    # ---------- التحديث ----------
    def update(self, dt):
        dt = min(dt, .05)
        self.u = self.height / 360. if self.height else 1
        if self.state == 'play':
            self.step(dt)
        self.draw()

    def step(self, dt):
        u = self.u
        mv, aim = [0, 0], None
        for side, ox, oy, cx, cy in self.touches.values():
            vx, vy = (cx - ox) / (55 * u), (cy - oy) / (55 * u)
            m = math.hypot(vx, vy)
            if m > 1:
                vx, vy, m = vx / m, vy / m, 1
            if side == 'move':
                mv = [vx, vy]
            else:
                aim = (vx, vy, m)
        kx = ('d' in self.keys) - ('a' in self.keys)
        ky = ('w' in self.keys) - ('s' in self.keys)
        if kx or ky:
            l = math.hypot(kx, ky)
            mv = [kx / l, ky / l]
        self.tleft -= dt
        for a in self.actors:
            if not a.alive:
                a.rt -= dt
                if a.rt <= 0:
                    self.respawn(a)
                continue
            a.cd -= dt
            a.inv -= dt
            if a.rl > 0:
                a.rl -= dt
                if a.rl <= 0:
                    a.ammo[a.wi] = WEAPONS[a.wi]['mag']
            if a.pl:
                self.player_step(a, dt, mv, aim)
            else:
                self.bot_ai(a, dt)
        nb = []
        for b in self.bullets:
            b[6] -= dt
            if b[6] <= 0:
                continue
            hit = False
            for _ in range(2):
                b[0] += b[2] * dt / 2
                b[1] += b[3] * dt / 2
                if self.hit_wall(b[0], b[1], 0):
                    hit = True
                    break
                for e in self.actors:
                    if e.alive and e.team != b[5] and e.inv <= 0 and \
                            (e.x - b[0]) ** 2 + (e.y - b[1]) ** 2 < R * R * 1.3:
                        self.damage(e, b[4], b[7])
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                nb.append(b)
        self.bullets = nb
        for f in self.feed:
            f[1] -= dt
        self.feed = [f for f in self.feed if f[1] > 0]
        if max(self.score) >= GOAL or self.tleft <= 0:
            s0, s1 = self.score
            self.result = 'win' if s0 > s1 else ('lose' if s0 < s1 else 'draw')
            self.state = 'over'
            self.over_t = time.time()
            self.touches = {}

    # ---------- الإدخال ----------
    def kd(self, win, key, scan, cp, mod):
        k = chr(key) if 0 < key < 128 else ''
        self.keys.add(k)
        if self.state == 'play' and self.player.alive:
            if k == 'r':
                self.do_reload(self.player)
            elif k == 'q':
                self.swap(self.player)

    def ku(self, win, key, *a):
        self.keys.discard(chr(key) if 0 < key < 128 else '')

    def btns(self):
        w, h = self.size
        u = self.u
        return {'reload': (w - 80 * u, 130 * u, 64 * u, 64 * u),
                'swap': (w - 80 * u, 56 * u, 64 * u, 64 * u)}

    def menu_btns(self):
        w, h = self.size
        u = self.u
        bw, bh = 230 * u, 40 * u
        return {n: (w / 2 - bw / 2, h / 2 + 50 * u - i * 52 * u, bw, bh)
                for i, n in enumerate(['n3', 'n5', 'n8', 'diff'])}

    def on_touch_down(self, t):
        if self.state == 'menu':
            for n, (x, y, bw, bh) in self.menu_btns().items():
                if x <= t.x <= x + bw and y <= t.y <= y + bh:
                    if n == 'diff':
                        self.diff = (self.diff + 1) % 3
                    else:
                        self.start(int(n[1:]))
            return True
        if self.state == 'over':
            if time.time() - self.over_t > 1.2:
                self.state = 'menu'
            return True
        for n, (x, y, bw, bh) in self.btns().items():
            if x <= t.x <= x + bw and y <= t.y <= y + bh:
                if self.player.alive:
                    self.do_reload(self.player) if n == 'reload' else self.swap(self.player)
                return True
        side = 'move' if t.x < self.width * .5 else 'aim'
        self.touches[t.uid] = [side, t.x, t.y, t.x, t.y]
        return True

    def on_touch_move(self, t):
        r = self.touches.get(t.uid)
        if r:
            r[3], r[4] = t.x, t.y
        return True

    def on_touch_up(self, t):
        self.touches.pop(t.uid, None)
        return True

    # ---------- الرسم ----------
    def tex(self, s, size):
        k = (s, size)
        t = self._tc.get(k)
        if t is None:
            cl = CoreLabel(text=s, font_size=size, font_name=FONT if AR else 'Roboto')
            cl.refresh()
            t = cl.texture
            if len(self._tc) > 300:
                self._tc.clear()
            self._tc[k] = t
        return t

    def text(self, s, x, y, size, col=(1, 1, 1, 1), anchor='c'):
        t = self.tex(s, max(8, int(size)))
        w, h = t.size
        if anchor == 'c':
            x -= w / 2
        elif anchor == 'r':
            x -= w
        Color(*col)
        Rectangle(texture=t, pos=(x, y - h / 2), size=(w, h))

    def draw(self):
        self.canvas.clear()
        with self.canvas:
            Color(.04, .04, .06, 1)
            Rectangle(pos=self.pos, size=self.size)
            if self.state == 'menu':
                self.draw_menu()
            elif self.actors:
                self.draw_world()
                self.draw_hud()
                if self.state == 'over':
                    self.draw_over()

    def draw_menu(self):
        w, h = self.size
        u = self.u
        self.text(tx('title'), w / 2, h - 35 * u, 30 * u, (1, .85, .3, 1))
        self.text(tx('goal', g=GOAL), w / 2, h - 70 * u, 14 * u, (.8, .8, .8, 1))
        for n, (x, y, bw, bh) in self.menu_btns().items():
            Color(.2, .35, .6, 1)
            Rectangle(pos=(x, y), size=(bw, bh))
            label = shape(raw('diff', d=raw('d%d' % self.diff))) if n == 'diff' else tx(n)
            self.text(label, x + bw / 2, y + bh / 2, 17 * u)

    def draw_world(self):
        w, h = self.size
        s = h / 430.
        P = self.player
        vw, vh = w / s, h / s
        cx = min(max(P.x - vw / 2, 0), max(W - vw, 0))
        cy = min(max(P.y - vh / 2, 0), max(H - vh, 0))
        Color(.15, .16, .18, 1)
        Rectangle(pos=(-cx * s, -cy * s), size=(W * s, H * s))
        Color(.18, .19, .21, 1)
        for gx in range(0, W, 200):
            if cx - 2 < gx < cx + vw:
                Line(points=[(gx - cx) * s, 0, (gx - cx) * s, h], width=1)
        for gy in range(0, H, 200):
            if cy - 2 < gy < cy + vh:
                Line(points=[0, (gy - cy) * s, w, (gy - cy) * s], width=1)
        for x, y, ww, hh, k in self.walls:
            if x + ww < cx or x > cx + vw or y + hh < cy or y > cy + vh:
                continue
            sx, sy = (x - cx) * s, (y - cy) * s
            if k == 0:
                Color(.30, .32, .37, 1)
                Rectangle(pos=(sx, sy), size=(ww * s, hh * s))
                Color(.40, .42, .48, 1)
                Rectangle(pos=(sx + 6 * s, sy + 6 * s), size=((ww - 12) * s, (hh - 12) * s))
            elif k == 1:
                Color(.05, .05, .07, 1)
                Rectangle(pos=(sx, sy), size=(ww * s, hh * s))
            else:
                Color(.35, .22, .1, 1)
                Rectangle(pos=(sx, sy), size=(ww * s, hh * s))
                Color(.55, .38, .2, 1)
                Rectangle(pos=(sx + 3 * s, sy + 3 * s), size=((ww - 6) * s, (hh - 6) * s))
        for a in self.actors:
            if not a.alive:
                continue
            sx, sy = (a.x - cx) * s, (a.y - cy) * s
            if sx < -40 or sx > w + 40 or sy < -40 or sy > h + 40:
                continue
            r = R * s
            col = BLUE if a.team == 0 else RED
            Color(col[0], col[1], col[2], .5 if a.inv > 0 else 1)
            Ellipse(pos=(sx - r, sy - r), size=(2 * r, 2 * r))
            if a.pl:
                Color(1, 1, 1, 1)
                Line(circle=(sx, sy, r + 3 * s), width=1.5)
            Color(.08, .08, .08, 1)
            Line(points=[sx, sy, sx + math.cos(a.angle) * (r + 9 * s),
                         sy + math.sin(a.angle) * (r + 9 * s)], width=max(1.5, 2.2 * s))
            bw = 30 * s
            Color(0, 0, 0, .6)
            Rectangle(pos=(sx - bw / 2, sy + r + 5 * s), size=(bw, 4 * s))
            Color(.3, 1, .3, 1)
            Rectangle(pos=(sx - bw / 2, sy + r + 5 * s), size=(bw * max(a.hp, 0) / 100., 4 * s))
        Color(1, .9, .3, 1)
        for b in self.bullets:
            bx, by = (b[0] - cx) * s, (b[1] - cy) * s
            Line(points=[bx, by, bx - b[2] * .025 * s, by - b[3] * .025 * s], width=1.6)

    def draw_hud(self):
        w, h = self.size
        u = self.u
        P = self.player
        Color(*BLUE)
        Rectangle(pos=(w / 2 - 78 * u, h - 34 * u), size=(16 * u, 16 * u))
        Color(*RED)
        Rectangle(pos=(w / 2 + 62 * u, h - 34 * u), size=(16 * u, 16 * u))
        self.text('%d  :  %d' % tuple(self.score), w / 2, h - 26 * u, 22 * u)
        m = max(0, int(self.tleft))
        self.text('%d:%02d' % (m // 60, m % 60), w / 2, h - 50 * u, 13 * u, (.8, .8, .8, 1))
        for i, (txt, ttl, team) in enumerate(self.feed):
            c = BLUE if team == 0 else RED
            self.text(txt, 10 * u, h - 20 * u - i * 17 * u, 12 * u, (c[0], c[1], c[2], min(1, ttl)), 'l')
        wp = WEAPONS[P.wi]
        if P.rl > 0:
            st = tx('reloading')
        else:
            st = shape('%s  %d/%d' % (raw('w%d' % P.wi), P.ammo[P.wi], wp['mag']))
        self.text(st, w - 10 * u, h - 20 * u, 14 * u, (1, 1, 1, 1), 'r')
        self.text(tx('stats', k=P.kills, d=P.deaths), w - 10 * u, h - 40 * u, 12 * u, (.8, .8, .8, 1), 'r')
        bw = 170 * u
        Color(0, 0, 0, .55)
        Rectangle(pos=(w / 2 - bw / 2, 12 * u), size=(bw, 10 * u))
        Color(.3, 1, .3, 1)
        Rectangle(pos=(w / 2 - bw / 2, 12 * u), size=(bw * max(P.hp, 0) / 100., 10 * u))
        for n, (x, y, bw2, bh2) in self.btns().items():
            Color(1, 1, 1, .18)
            Ellipse(pos=(x, y), size=(bw2, bh2))
            self.text(tx(n), x + bw2 / 2, y + bh2 / 2, 11 * u)
        for side, ox, oy, cx, cy in self.touches.values():
            Color(1, 1, 1, .12)
            Ellipse(pos=(ox - 55 * u, oy - 55 * u), size=(110 * u, 110 * u))
            vx, vy = cx - ox, cy - oy
            m = math.hypot(vx, vy)
            if m > 55 * u:
                vx, vy = vx / m * 55 * u, vy / m * 55 * u
            Color(1, .5, .3, .5) if side == 'aim' else Color(.4, .8, 1, .5)
            Ellipse(pos=(ox + vx - 22 * u, oy + vy - 22 * u), size=(44 * u, 44 * u))
        if not P.alive:
            Color(0, 0, 0, .45)
            Rectangle(pos=self.pos, size=self.size)
            self.text(tx('dead', t=int(math.ceil(P.rt))), w / 2, h / 2, 22 * u, (1, .4, .4, 1))

    def draw_over(self):
        w, h = self.size
        u = self.u
        P = self.player
        Color(0, 0, 0, .65)
        Rectangle(pos=self.pos, size=self.size)
        col = {'win': (.4, 1, .4, 1), 'lose': (1, .4, .4, 1), 'draw': (1, 1, .5, 1)}[self.result]
        self.text(tx(self.result), w / 2, h / 2 + 40 * u, 32 * u, col)
        self.text('%d : %d' % tuple(self.score), w / 2, h / 2, 24 * u)
        self.text(tx('stats', k=P.kills, d=P.deaths), w / 2, h / 2 - 35 * u, 16 * u)
        self.text(tx('tap'), w / 2, h / 2 - 75 * u, 13 * u, (.8, .8, .8, 1))


class TDMApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0, 1)
        return Game()

    def on_pause(self):
        return True


if __name__ == '__main__':
    TDMApp().run()
