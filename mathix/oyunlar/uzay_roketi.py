"""MATHİX — Newton'un İntikamı (uzay shooter).

Özellikler:
  - Sonsuz dalga veya dalga limiti
  - 3 tip düşman (mor/mavi/kırmızı)
  - Otomatik ateş + düşman ateşi
  - Vurulunca matematik sorusu (Frame tabanlı, otomatik ölçeklenir)
  - 💡 AI İpucu — kutu otomatik büyür
  - Oyun sonu → 🤖 AI DEĞERLENDİRMESİ (canlı stream)
"""
import math
import random
import threading
import tkinter as tk
from mathix.protection import GameProtection
from mathix.ui.music import GameMusic

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN, GREEN_ACTIVE, RED, YELLOW,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY,
)
from mathix.ui.widgets import HoverButton
from mathix.soru.uretici import soru_uret
from mathix.ai.ollama_client import ai_stream_chat
from mathix.ui.game_ai_hint import GameAIHint
from mathix.oyun_kayıtları import oyun_kaydi_ekle


# ==============================================================================
# SABİTLER
# ==============================================================================
SP_W, SP_H = 1000, 590
PURPLE = "#7722CC"
PURPLE_ACT = "#9933EE"

# Düşman tipleri
_ET = [
    {"body": "#CC44FF", "wing": "#880ACC", "score": 30},
    {"body": "#00CCFF", "wing": "#007AAA", "score": 20},
    {"body": "#FF4444", "wing": "#990000", "score": 10},
]


# ==============================================================================
# 🚀 UZAY — KURULUM EKRANI
# ==============================================================================
class SpaceSetupFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        tk.Label(self, text="🚀 NEWTON'UN İNTİKAMI",
                 font=("Segoe UI", 30, "bold"),
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(pady=(50, 6))
        tk.Label(self,
                 text="Düşman gemilerini imha et, matematik gücünle hayatta kal!",
                 font=FONT_SUBTITLE, fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(pady=(0, 22))

        card = tk.Frame(self, bg=CARD_COLOR,
                        highlightbackground=CARD_LIGHT, highlightthickness=1)
        card.pack(padx=140, pady=6, fill="x")

        self.var_sinif = tk.StringVar(value=f"{parent.active_student['sinif']}. Sınıf")
        self.var_zorluk = tk.StringVar(value="Orta")
        self.var_dalga = tk.StringVar(value="Sonsuz")

        def satir(pf, lbl, var, opts):
            r = tk.Frame(pf, bg=CARD_COLOR)
            r.pack(fill="x", padx=40, pady=13)
            tk.Label(r, text=lbl, font=FONT_BODY,
                     fg=TEXT_COLOR, bg=CARD_COLOR).pack(side="left")
            m = tk.OptionMenu(r, var, *opts)
            m.config(font=FONT_BODY, bg=CARD_LIGHT, fg=TEXT_COLOR,
                     bd=0, highlightthickness=0, width=15)
            m.pack(side="right")

        satir(card, "SINIF SEVİYESİ", self.var_sinif,
              ["Rastgele"] + [f"{i}. Sınıf" for i in range(1, 13)])
        satir(card, "SORU ZORLUĞU", self.var_zorluk,
              ["Rastgele", "Kolay", "Orta", "Zor"])
        satir(card, "DALGA SAYISI", self.var_dalga,
              ["Sonsuz", "3 Dalga", "5 Dalga", "10 Dalga"])

        info = tk.Frame(self, bg=CARD_COLOR,
                        highlightbackground=PURPLE, highlightthickness=1)
        info.pack(padx=140, pady=10, fill="x")
        tk.Label(info,
                 text="🎮  ← → veya A/D ile hareket  •  Otomatik ateş\n"
                      "💥  Vurulursan matematik sorusu gelir — doğruysa hayatta kalırsın!\n"
                      "💡  AI İpucu butonu soru ekranında aktif",
                 font=("Segoe UI", 10), fg=SECONDARY_TEXT, bg=CARD_COLOR,
                 justify="center").pack(pady=10)

        btn_f = tk.Frame(self, bg=BG_COLOR)
        btn_f.pack(fill="x", padx=140, pady=24)
        HoverButton(btn_f, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="← Geri", command=self._geri,
                    width=15).pack(side="left")
        HoverButton(btn_f, bg_color=PURPLE, active_bg=PURPLE_ACT,
                    text="BAŞLAT ➔", command=self.baslat,
                    width=15).pack(side="right")

    def _geri(self):
        from mathix.menu.menu import GamesMenuFrame
        self.parent.show_frame(GamesMenuFrame)

    def baslat(self):
        s = self.var_sinif.get()
        z = self.var_zorluk.get()
        d = self.var_dalga.get()
        sinif = random.randint(1, 12) if s == "Rastgele" else int(s.split(".")[0])
        zorluk = random.choice(["Kolay", "Orta", "Zor"]) if z == "Rastgele" else z
        max_d = 0 if d == "Sonsuz" else int(d.split()[0])
        self.parent.oyun_ayarlari.update(
            {"sinif": sinif, "zorluk": zorluk, "max_dalga": max_d}
        )
        self.parent.show_frame(SpaceGameFrame)


# ==============================================================================
# 🚀 UZAY — OYUN EKRANI
# ==============================================================================
class SpaceGameFrame(tk.Frame):
    TICK_MS = 30
    P_BULLET_SPEED = 14
    E_BULLET_SPEED = 4.5
    STAR_COUNT = 90
    ENEMY_ROWS = 3
    ENEMY_COLS = 7
    EW, EH = 46, 32
    PW, PH = 44, 52

    def __init__(self, parent):
        super().__init__(parent, bg="#000010")
        self.parent = parent
        self.sinif = parent.oyun_ayarlari["sinif"]
        self.zorluk = parent.oyun_ayarlari["zorluk"]
        self.max_d = parent.oyun_ayarlari.get("max_dalga", 0)

        # Oyun durumu
        self.score = 0
        self.lives = 3
        self.wave = 1
        self.dogru_s = 0
        self.yanlis_s = 0
        self.toplam_soru = 0

        self.running = False
        self.q_active = False
        self.ended = False
        self.tick_id = None
        self.ticks = 0

        self.px = SP_W // 2
        self.py = SP_H - 100
        self.moving_l = False
        self.moving_r = False
        self.moving_u = False
        self.moving_d = False
        self.fire_cooldown = 0

        self.stars = []
        self.enemies = []
        self.p_bullets = []
        self.e_bullets = []
        self.expl = []
        self.e_dx = 1.4
        self.e_fire_cd = 0

        # Soru ekranı referansları
        self.q_frame = None
        self._aktif_soru = ""
        self.rescue_ans = None
        self._q_entry = None
        self._q_btn = None
        self._q_ai_btn = None

        self._build_ui()
        self._setup_touch_controls()
        self._spawn_stars()
        self._spawn_wave()
        self._bind_keys()
        self.running = True
        self._tick()
        self.protection = GameProtection(self, "Uzay Roketi",
                                         self._koruma_duraklat, self._koruma_devam,
                                         student_id=self.parent.active_student["id"])
        self.music = GameMusic("space")
        self.music.attach(self)

    def _koruma_duraklat(self):
        if hasattr(self, "music"):
            self.music.pause()
        self._koruma_onceki_durum = self.running
        self.running = False
        if self.tick_id:
            try:
                self.after_cancel(self.tick_id)
            except tk.TclError:
                pass
            self.tick_id = None

    def _koruma_devam(self):
        if getattr(self, "_koruma_onceki_durum", False) and not self.ended:
            if not self.q_active and hasattr(self, "music"):
                self.music.resume()
            self.running = True
            if not self.q_active:
                self._tick()

    # ================================================================ UI ====
    def _build_ui(self):
        hud = tk.Frame(self, bg="#05050F", height=44)
        hud.pack(fill="x")
        hud.pack_propagate(False)

        self.lbl_score = tk.Label(hud, text="PUAN: 0",
            font=("Segoe UI", 13, "bold"), fg=YELLOW, bg="#05050F")
        self.lbl_score.pack(side="left", padx=16, pady=8)

        self.lbl_lives = tk.Label(hud, text="❤ ❤ ❤",
            font=("Segoe UI", 13, "bold"), fg="#FF4444", bg="#05050F")
        self.lbl_lives.pack(side="left", padx=10)

        self.lbl_wave = tk.Label(hud, text="DALGA 1",
            font=("Segoe UI", 11, "bold"), fg=PURPLE, bg="#05050F")
        self.lbl_wave.pack(side="left", padx=10)

        self.lbl_info = tk.Label(hud, text=f"{self.sinif}. Sınıf  •  {self.zorluk}",
            font=("Segoe UI", 10), fg=SECONDARY_TEXT, bg="#05050F")
        self.lbl_info.pack(side="left", padx=8)

        HoverButton(hud, bg_color="#330022", active_bg="#550033",
                    text="MENÜ", command=self._quit,
                    width=7, height=1).pack(side="right", padx=10, pady=6)

        cf = tk.Frame(self, bg="#000010")
        cf.pack(expand=True)
        self.cv = tk.Canvas(cf, width=SP_W, height=SP_H,
                                bg="#000010", highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", lambda e: self._show_controls())

    # ============================================================= stars ====
    def _spawn_stars(self):
        self.stars = [
            (random.randint(0, SP_W),
             random.randint(0, SP_H),
             random.choice([1, 1, 1, 2, 2, 3]),
             random.uniform(0.4, 1.8))
            for _ in range(self.STAR_COUNT)
        ]

    def _move_stars(self):
        new = []
        for x, y, r, sp in self.stars:
            y += sp
            if y > SP_H:
                y = 0
                x = random.randint(0, SP_W)
            new.append((x, y, r, sp))
        self.stars = new

    # =========================================================== enemies ====
    def _spawn_wave(self):
        self.enemies = []
        self.p_bullets = []
        self.e_bullets = []
        self.e_dx = 1.4 + self.wave * 0.2
        start_x = 100
        start_y = 80
        gap_x, gap_y = 100, 60
        for row in range(self.ENEMY_ROWS):
            et = _ET[row]
            for col in range(self.ENEMY_COLS):
                self.enemies.append({
                    "x": start_x + col * gap_x,
                    "y": start_y + row * gap_y,
                    "type": row,
                    "alive": True,
                    "body": et["body"],
                    "wing": et["wing"],
                    "score": et["score"] + self.wave * 5,
                    "phase": random.random() * math.tau,
                })

    # =========================================================== drawing ====
    def _draw_frame(self):
        cv = self.cv
        cv.delete("g")

        for x, y, r, _ in self.stars:
            bright = min(255, 80 + int(r * 58))
            col = f"#{bright:02X}{bright:02X}{bright:02X}"
            cv.create_oval(x - r, y - r, x + r, y + r,
                           fill=col, outline="", tags="g")

        for e in self.enemies:
            if e["alive"]:
                self._draw_enemy(e)

        next_expl = []
        for ex, ey, r, mx, col in self.expl:
            if r < mx:
                cv.create_oval(ex - r, ey - r, ex + r, ey + r,
                               fill=col, outline="", tags="g")
                cv.create_oval(ex - r // 2, ey - r // 2,
                               ex + r // 2, ey + r // 2,
                               fill="#FFFFFF", outline="", tags="g")
                next_expl.append((ex, ey, r + 4, mx, col))
        self.expl = next_expl

        for bx, by in self.p_bullets:
            cv.create_rectangle(bx - 3, by - 10, bx + 3, by,
                                fill="#00FFFF", outline="", tags="g")
            cv.create_rectangle(bx - 1, by - 18, bx + 1, by - 10,
                                fill="#AAFFFF", outline="", tags="g")

        for bx, by, *_ in self.e_bullets:
            cv.create_oval(bx - 4, by - 4, bx + 4, by + 4,
                           fill="#FF4400", outline="#FF8800", width=1,
                           tags="g")
            cv.create_oval(bx - 2, by - 2, bx + 2, by + 2,
                           fill="#FFFF00", outline="", tags="g")

        self._draw_player()

    def _draw_enemy(self, e):
        cv = self.cv
        x, y = e["x"], e["y"]
        bc, wc = e["body"], e["wing"]
        ew2, eh2 = self.EW // 2, self.EH // 2
        kind = e["type"]
        flap = math.sin(self.ticks * 0.16 + e.get("phase", 0)) * 5

        cv.create_polygon(x - ew2 - 14, y + flap, x - ew2, y - eh2 + 4,
                          x - ew2, y + eh2 - 4,
                          fill=wc, outline="", tags="g")
        cv.create_polygon(x + ew2 + 14, y - flap, x + ew2, y - eh2 + 4,
                          x + ew2, y + eh2 - 4,
                          fill=wc, outline="", tags="g")
        cv.create_oval(x - ew2, y - eh2, x + ew2, y + eh2,
                       fill=bc, outline="#FFFFFF", width=1, tags="g")
        cv.create_oval(x - 10, y - 10, x + 10, y + 10,
                       fill="#001133", outline=wc, width=2, tags="g")
        if kind == 0:  # mor: ağır komuta gemisi, üç parlak sensör
            cv.create_rectangle(x-13, y+8, x+13, y+13, fill="#3C1558",
                                outline=wc, width=1, tags="g")
            for sx in (-7, 0, 7):
                cv.create_oval(x+sx-2, y+9, x+sx+2, y+13,
                               fill="#FFE66D", outline="", tags="g")
        elif kind == 1:  # mavi: kanat çizgileri ve enerji çekirdeği
            cv.create_line(x-18, y-4, x-8, y+2, x-18, y+8,
                           fill="#D8FAFF", width=2, tags="g")
            cv.create_line(x+18, y-4, x+8, y+2, x+18, y+8,
                           fill="#D8FAFF", width=2, tags="g")
            cv.create_oval(x-3, y-3, x+3, y+3, fill="#BFFFFF",
                           outline="", tags="g")
        else:  # kırmızı: saldırgan gemide sivri ön kısım
            cv.create_polygon(x, y-eh2-8, x-7, y-eh2+2, x+7, y-eh2+2,
                              fill="#FFB0A8", outline="", tags="g")
            cv.create_line(x-12, y+10, x+12, y+10, fill="#FFB04A",
                           width=2, tags="g")
        cv.create_oval(x - 7, y - 6, x - 2, y - 1,
                       fill="#FF0000", outline="", tags="g")
        cv.create_oval(x + 2, y - 6, x + 7, y - 1,
                       fill="#FF0000", outline="", tags="g")
        cv.create_line(x - 8, y - eh2, x - 4, y - eh2 - 8,
                       fill=wc, width=2, tags="g")
        cv.create_line(x + 8, y - eh2, x + 4, y - eh2 - 8,
                       fill=wc, width=2, tags="g")
        cv.create_oval(x - 6, y - eh2 - 11, x - 2, y - eh2 - 7,
                       fill=bc, tags="g")
        cv.create_oval(x + 2, y - eh2 - 11, x + 6, y - eh2 - 7,
                       fill=bc, tags="g")

    def _draw_player(self):
        cv = self.cv
        x, y = self.px, self.py
        h = self.PH

        for i in range(3):
            flame_h = random.randint(8, 22)
            fx = x + (i - 1) * 10
            col = ["#FF4400", "#FF8800", "#FFCC00"][i]
            cv.create_polygon(fx - 5, y + h // 2 - 2, fx + 5, y + h // 2 - 2,
                              fx, y + h // 2 + flame_h,
                              fill=col, outline="", tags="g")

        cv.create_polygon(x, y - h // 2, x - 14, y + h // 2 - 10,
                          x + 14, y + h // 2 - 10,
                          fill="#6699FF", outline="#AACCFF", width=1,
                          tags="g")
        cv.create_polygon(x - 4, y - h // 2 + 4, x + 4, y - h // 2 + 4,
                          x + 6, y + h // 2 - 14, x - 6, y + h // 2 - 14,
                          fill="#AADDFF", outline="", tags="g")
        cv.create_polygon(x - 14, y + h // 2 - 10, x - 30, y + h // 2 + 4,
                          x - 8, y + h // 2 - 2,
                          fill="#334488", outline="#5566BB", width=1,
                          tags="g")
        cv.create_polygon(x + 14, y + h // 2 - 10, x + 30, y + h // 2 + 4,
                          x + 8, y + h // 2 - 2,
                          fill="#334488", outline="#5566BB", width=1,
                          tags="g")
        cv.create_oval(x - 8, y - h // 2 + 6, x + 8, y - h // 2 + 22,
                       fill="#001155", outline="#00AAFF", width=1,
                       tags="g")
        cv.create_oval(x - 4, y - h // 2 + 8, x + 4, y - h // 2 + 16,
                       fill="#0033AA", outline="", tags="g")
        cv.create_oval(x - 5, y - h // 2 + 22, x + 5, y - h // 2 + 32,
                       fill="#00FFFF", outline="", tags="g")

    # =========================================================== game tick =
    def _tick(self):
        if not self.running or self.q_active or self.ended:
            return
        self.ticks += 1

        if self.moving_l:
            self.px = max(self.PW // 2 + 5, self.px - 6)
        if self.moving_r:
            self.px = min(SP_W - self.PW // 2 - 5, self.px + 6)
        if self.moving_u:
            self.py = max(self.PH // 2 + 5, self.py - 6)
        if self.moving_d:
            self.py = min(SP_H - self.PH // 2 - 5, self.py + 6)

        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        elif self.auto_fire_enabled:
            self.p_bullets.append([self.px, self.py - self.PH // 2])
            self.fire_cooldown = 16

        self.p_bullets = [[bx, by - self.P_BULLET_SPEED]
                          for bx, by in self.p_bullets if by > 0]

        self._move_stars()

        alive = [e for e in self.enemies if e["alive"]]
        if alive:
            min_x = min(e["x"] for e in alive)
            max_x = max(e["x"] for e in alive)
            if (max_x + self.EW // 2 >= SP_W - 10
                    or min_x - self.EW // 2 <= 10):
                self.e_dx *= -1
                for e in alive:
                    e["y"] += 18
            for e in alive:
                if e["type"] == 1:
                    e["x"] += self.e_dx * 1.18
                    e["y"] += math.sin(self.ticks * 0.07 + e["phase"]) * 1.1
                elif e["type"] == 2:
                    e["x"] += self.e_dx * 0.88
                else:
                    e["x"] += self.e_dx

        self.e_fire_cd -= 1
        if self.e_fire_cd <= 0 and alive:
            shooter = random.choice(alive)
            dx_to_p = (self.px - shooter["x"])
            dist = max(1, abs(self.py - shooter["y"]))
            angle_x = dx_to_p / dist * self.E_BULLET_SPEED
            self.e_bullets.append([
                shooter["x"], shooter["y"] + self.EH // 2,
                angle_x, self.E_BULLET_SPEED,
            ])
            fire_interval = max(20, 55 - self.wave * 4)
            self.e_fire_cd = random.randint(fire_interval, fire_interval + 20)

        next_eb = []
        for bx, by, bdx, bdy in self.e_bullets:
            bx += bdx
            by += bdy
            if by < SP_H + 10:
                next_eb.append([bx, by, bdx, bdy])
        self.e_bullets = next_eb

        for b in self.p_bullets[:]:
            bx, by = b
            for e in self.enemies:
                if not e["alive"]:
                    continue
                if (e["x"] - self.EW // 2 < bx < e["x"] + self.EW // 2
                        and e["y"] - self.EH // 2 < by < e["y"] + self.EH // 2):
                    e["alive"] = False
                    self.score += e["score"]
                    self.lbl_score.config(text=f"PUAN: {self.score}")
                    col = random.choice(["#FF6600", "#FF9900",
                                         "#FFCC00", "#FF4400"])
                    self.expl.append((e["x"], e["y"], 2, 38, col))
                    if b in self.p_bullets:
                        self.p_bullets.remove(b)
                    break

        for eb in self.e_bullets[:]:
            bx, by = eb[0], eb[1]
            if (self.px - 20 < bx < self.px + 20
                    and self.py - 28 < by < self.py + 28):
                self.e_bullets.remove(eb)
                self.expl.append((self.px, self.py, 2, 30, "#00AAFF"))
                self._player_hit()
                return

        for e in alive:
            if e["y"] + self.EH // 2 >= self.py - 30:
                self._player_hit()
                return

        if not any(e["alive"] for e in self.enemies):
            self.wave += 1
            if self.max_d > 0 and self.wave > self.max_d:
                self._game_over(win=True)
                return
            self.lbl_wave.config(text=f"DALGA {self.wave}")
            self._spawn_wave()

        self._draw_frame()
        self.tick_id = self.after(self.TICK_MS, self._tick)

    # ====================================================== oyuncu vuruldu ==
    def _player_hit(self):
        """Oyuncu vurulunca Frame tabanlı matematik sorusu aç."""
        self.music.pause()
        self.q_active = True
        self.running = False

        soru_metni, self.rescue_ans = soru_uret(
            self.sinif, self.zorluk, kullan_bank=False
        )
        self._aktif_soru = soru_metni
        self.toplam_soru += 1

        # Karartma
        self.cv.delete("q_sp")
        self.cv.create_rectangle(
            0, 0, SP_W, SP_H,
            fill="black", stipple="gray50", outline="", tags="q_sp",
        )

        # Frame
        self.q_frame = tk.Frame(
            self, bg="#0A0812",
            highlightbackground="#FF2200", highlightthickness=4,
        )

        tk.Label(
            self.q_frame,
            text="💥 GEMİN VURULDU! Soruyu çöz, hayatta kal!",
            font=("Segoe UI", 13, "bold"),
            fg="#FF6600", bg="#0A0812",
        ).pack(pady=(16, 8), padx=24)

        # Soru metni — dinamik font
        uzunluk = len(soru_metni)
        if uzunluk <= 25:
            q_font = 17
        elif uzunluk <= 50:
            q_font = 15
        elif uzunluk <= 90:
            q_font = 13
        else:
            q_font = 11

        tk.Label(
            self.q_frame, text=soru_metni,
            font=("Segoe UI", q_font, "bold"),
            fg="white", bg="#0A0812",
            wraplength=620, justify="center",
        ).pack(padx=30, pady=12)

        # Giriş + buton
        input_row = tk.Frame(self.q_frame, bg="#0A0812")
        input_row.pack(pady=(6, 4))

        self._q_entry = tk.Entry(
            input_row, font=("Segoe UI", 15, "bold"),
            width=12, justify="center",
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat",
        )
        self._q_entry.pack(side="left", padx=(0, 10), ipady=6)
        self._q_entry.focus_set()
        self._q_entry.bind("<Return>", lambda e: self._check_space_ans())

        self._q_btn = tk.Button(
            input_row, text="CEVAPLA",
            font=("Segoe UI", 12, "bold"),
            bg=GREEN, fg="white", relief="flat", cursor="hand2",
            command=self._check_space_ans,
        )
        self._q_btn.pack(side="left", ipadx=12, ipady=4)

        self._q_ai_btn = tk.Button(
            self.q_frame, text="💡 AI İpucu",
            font=("Segoe UI", 11, "bold"),
            bg=BLUE, fg="white", relief="flat", cursor="hand2",
            command=self._ai_ipucu,
        )
        self._q_ai_btn.pack(pady=(6, 8), ipadx=24, ipady=4)
        self._ai_hint_panel = GameAIHint(
            self.q_frame, self._q_ai_btn, background="#0A0812")

        self.q_frame.place(relx=0.5, rely=0.5, anchor="center")

    # ------------------------------------------------------------- AI İpucu --
    def _ai_ipucu(self):
        if not self.q_active:
            return
        self._ai_hint_panel.start(
            f"Matematik sorusu: '{self._aktif_soru}'. Çözümü kısa adımlarla "
            "açıkla ve doğru cevabı en sonda net biçimde yaz."
        )

    # -------------------------------------------------------- Cevap kontrol --
    def _check_space_ans(self):
        if not self.q_active:
            return
        raw = (self._q_entry.get() if self._q_entry else "").strip()
        if not raw:
            return

        correct = False
        try:
            uv = float(raw.replace(",", "."))
            av = (float(self.rescue_ans)
                  if self.rescue_ans is not None else None)
            if av is not None and math.isclose(uv, av,
                                                rel_tol=1e-6, abs_tol=1e-6):
                correct = True
        except (ValueError, TypeError):
            pass

        try:
            if self.q_frame:
                if getattr(self, "_ai_hint_panel", None):
                    self._ai_hint_panel.hide()
                self.q_frame.destroy()
        except Exception:
            pass
        self.q_frame = None
        self.cv.delete("q_sp")
        self.q_active = False
        if correct:
            self.music.resume()

        if correct:
            self.dogru_s += 1
            self.score += 30
            self.lbl_score.config(text=f"PUAN: {self.score}")
            cleared = [
                e for e in self.enemies
                if e["alive"] and math.hypot(e["x"] - self.px,
                                              e["y"] - self.py) < 200
            ]
            for e in cleared:
                e["alive"] = False
                self.expl.append((e["x"], e["y"], 2, 30, "#FFAA00"))
            self._flash_banner("✓ DOĞRU! Gemi kurtuldu! +30 💥",
                                "#00FF88", 1000)
            self.running = True
            self.after(1050, self._tick)
        else:
            self.yanlis_s += 1
            ans_str = str(self.rescue_ans) if self.rescue_ans else "?"
            self._lose_life(f"✗ Yanlış! Doğru cevap: {ans_str}")
            # Yanlış cevapta oyun devam ediyorsa müziği geri başlat.
            # Son can da gittiyse _game_over müziği kapalı tutar.
            if not self.ended:
                self.music.resume()

    def _lose_life(self, msg):
        self.lives -= 1
        hearts = "❤ " * self.lives + "🖤 " * (3 - self.lives)
        self.lbl_lives.config(text=hearts.strip())
        if self.lives <= 0:
            self._game_over(win=False)
            return
        self._flash_banner(f"💔 {msg}\n{self.lives} kalkan kaldı!",
                            RED, 1400)
        self.running = True

        def safe_tick():
            if not self.ended and self.running:
                self._tick()
        self.after(1450, safe_tick)

    def _flash_banner(self, text, color, ms):
        self.cv.delete("banner")
        self.cv.create_text(SP_W // 2, SP_H // 2,
                            text=text, font=("Segoe UI", 20, "bold"),
                            fill=color, justify="center", tags="banner")
        self.after(ms, lambda: self.cv.delete("banner"))

    # ========================================================= key bindings =
    def _setup_touch_controls(self):
        # Neon joystick with a generous touch target and centered knob.
        self.joy_bg = tk.Canvas(self, width=176, height=176, bg="#0C1525",
                                highlightthickness=2, highlightbackground="#314B70")
        self.joy_bg.place(relx=0.055, rely=0.69)
        self.joy_bg.create_oval(10, 10, 166, 166, fill="#111F35",
                                outline="#263D61", width=2)
        self.joy_bg.create_oval(30, 30, 146, 146, outline="#5F79AA", width=2)
        self.joy_bg.create_line(88, 22, 88, 154, fill="#263D61", dash=(3, 4))
        self.joy_bg.create_line(22, 88, 154, 88, fill="#263D61", dash=(3, 4))
        self.joy_stick = tk.Canvas(self.joy_bg, width=60, height=60,
                                   bg="#0C1525", highlightthickness=0,
                                   cursor="hand2")
        self.joy_stick.create_oval(4, 4, 56, 56, fill="#566EF2",
                                   outline="#A7B4FF", width=3)
        self.joy_stick.create_oval(17, 14, 28, 25, fill="#E2E7FF", outline="")
        self.joy_stick.place(x=58, y=58)
        
        def move_joy(event):
            widget = event.widget
            px = event.x_root - self.joy_bg.winfo_rootx()
            py = event.y_root - self.joy_bg.winfo_rooty()
            dx = px - 88
            dy = py - 88
            self.moving_l = dx < -20
            self.moving_r = dx > 20
            self.moving_u = dy < -20
            self.moving_d = dy > 20
            length = max(1, math.hypot(dx, dy))
            scale = min(1, 52 / length)
            nx = int(58 + max(-52, min(52, dx * scale)))
            ny = int(58 + max(-52, min(52, dy * scale)))
            self.joy_stick.place(x=nx, y=ny)

        def release_joy(event):
            self.moving_l = self.moving_r = self.moving_u = self.moving_d = False
            self.joy_stick.place(x=50, y=50)

        for widget in (self.joy_bg, self.joy_stick):
            widget.bind("<Button-1>", move_joy)
            widget.bind("<B1-Motion>", move_joy)
            widget.bind("<ButtonRelease-1>", release_joy)

        # Sağ Ateş Butonları
        self.btn_fire = HoverButton(self, text="🔥 ATEŞ", bg_color=RED, active_bg="#9B111E",
                                    width=12, height=3, command=self._manual_fire)
        self.btn_fire.place(relx=0.82, rely=0.70, relwidth=0.12, relheight=0.10)
        
        self.btn_auto = HoverButton(self, text="⚙ AUTO", bg_color=BLUE, active_bg=BLUE_ACTIVE,
                                    width=10, height=2, command=self._toggle_auto_fire)
        self.btn_auto.place(relx=0.82, rely=0.82, relwidth=0.12, relheight=0.07)
        self.auto_fire_enabled = False # Varsayılan: Kapalı

    def _hide_controls(self):
        """Klavye veya Joystick etkileşimi başladığında tüm kontrolleri gizle."""
        if self.joy_bg.winfo_exists():
            self.joy_bg.place_forget()
        if self.btn_fire.winfo_exists():
            self.btn_fire.place_forget()
        if self.btn_auto.winfo_exists():
            self.btn_auto.place_forget()

    def _show_controls(self):
        """Ekran tıklandığında kontrolleri şık bir şekilde geri getir."""
        if self.joy_bg.winfo_exists():
            self.joy_bg.place(relx=0.055, rely=0.69)
        if self.btn_fire.winfo_exists():
            self.btn_fire.place(relx=0.82, rely=0.70, relwidth=0.12, relheight=0.10)
        if self.btn_auto.winfo_exists():
            self.btn_auto.place(relx=0.82, rely=0.82, relwidth=0.12, relheight=0.07)

    def _manual_fire(self):
        if self.running and not self.q_active:
            self.p_bullets.append([self.px, self.py - self.PH // 2])

    def _toggle_auto_fire(self):
        self.auto_fire_enabled = not self.auto_fire_enabled
        self.btn_auto.config(text="⚙ AUTO: ON" if self.auto_fire_enabled else "⚙ AUTO: OFF")

    def _bind_keys(self):
        p = self.parent
        def start_move(key, attr):
            setattr(self, attr, True)
            self._hide_controls()

        p.bind("<Left>", lambda e: start_move(e, "moving_l"))
        p.bind("<Right>", lambda e: start_move(e, "moving_r"))
        p.bind("a", lambda e: start_move(e, "moving_l"))
        p.bind("A", lambda e: start_move(e, "moving_l"))
        p.bind("d", lambda e: start_move(e, "moving_r"))
        p.bind("D", lambda e: start_move(e, "moving_r"))
        p.bind("<Up>", lambda e: start_move(e, "moving_u"))
        p.bind("w", lambda e: start_move(e, "moving_u"))
        p.bind("W", lambda e: start_move(e, "moving_u"))
        p.bind("<Down>", lambda e: start_move(e, "moving_d"))
        p.bind("s", lambda e: start_move(e, "moving_d"))
        p.bind("S", lambda e: start_move(e, "moving_d"))
        p.bind("e", lambda e: (self._toggle_auto_fire(), self._hide_controls()))
        p.bind("E", lambda e: (self._toggle_auto_fire(), self._hide_controls()))
        p.bind("<space>", lambda e: (self._manual_fire(), self._hide_controls()))
        p.bind("<KeyRelease-Left>",
               lambda e: setattr(self, "moving_l", False))
        p.bind("<KeyRelease-Right>",
               lambda e: setattr(self, "moving_r", False))
        p.bind("<KeyRelease-a>",
               lambda e: setattr(self, "moving_l", False))
        p.bind("<KeyRelease-A>",
               lambda e: setattr(self, "moving_l", False))
        p.bind("<KeyRelease-d>",
               lambda e: setattr(self, "moving_r", False))
        p.bind("<KeyRelease-D>",
               lambda e: setattr(self, "moving_r", False))
        p.bind("<KeyRelease-Up>",
               lambda e: setattr(self, "moving_u", False))
        p.bind("<KeyRelease-w>",
               lambda e: setattr(self, "moving_u", False))
        p.bind("<KeyRelease-W>",
               lambda e: setattr(self, "moving_u", False))
        p.bind("<KeyRelease-Down>",
               lambda e: setattr(self, "moving_d", False))
        p.bind("<KeyRelease-s>",
               lambda e: setattr(self, "moving_d", False))
        p.bind("<KeyRelease-S>",
               lambda e: setattr(self, "moving_d", False))
        p.bind("<Escape>", lambda e: self._quit())

    def _unbind_keys(self):
        for k in ["<Left>", "<Right>", "<Up>", "<Down>",
                  "a", "A", "d", "D", "w", "W", "s", "S", "e", "E", "<space>",
                  "<KeyRelease-Left>", "<KeyRelease-Right>",
                  "<KeyRelease-Up>", "<KeyRelease-Down>",
                  "<KeyRelease-a>", "<KeyRelease-A>",
                  "<KeyRelease-d>", "<KeyRelease-D>",
                  "<KeyRelease-w>", "<KeyRelease-W>",
                  "<KeyRelease-s>", "<KeyRelease-S>", "<Escape>"]:
            try:
                self.parent.unbind(k)
            except Exception:
                pass

    # ============================================================= game over =
    def _game_over(self, win=False):
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        if self.ended:
            return
        self.ended = True
        self.running = False
        oyun_kaydi_ekle(
            self.parent.active_student, "Newton'un İntikamı", self.score,
            "kazandı" if win else "kaybetti",
            {"dalga": self.wave, "dogru": self.dogru_s,
             "yanlis": self.yanlis_s, "toplam_soru": self.toplam_soru},
        )

        if self.tick_id:
            try:
                self.after_cancel(self.tick_id)
            except Exception:
                pass
        try:
            if self.q_frame:
                if getattr(self, "_ai_hint_panel", None):
                    self._ai_hint_panel.hide()
                self.q_frame.destroy()
        except Exception:
            pass
        self._unbind_keys()

        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        self.configure(bg=BG_COLOR)

        baslik = "🏆 ZAFER!" if win else "💥 OYUN BİTTİ!"
        renk = YELLOW if win else RED
        tk.Label(self, text=baslik, font=("Segoe UI", 36, "bold"),
                 fg=renk, bg=BG_COLOR).pack(pady=(30, 6))
        tk.Label(self, text="Newton'un İntikamı tamamlandı." if win
                 else "Newton'un İntikamı sona erdi.",
                 font=("Segoe UI", 13), fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack()

        card = tk.Frame(self, bg=CARD_COLOR,
                        highlightbackground=PURPLE, highlightthickness=2)
        card.pack(padx=200, pady=18, fill="x")
        tk.Label(card, text="SONUÇLAR", font=("Segoe UI", 14, "bold"),
                 fg=YELLOW, bg=CARD_COLOR).pack(pady=(16, 8))
        info = (f"⭐  Puan: {self.score}\n"
                f"💥  Ulaşılan Dalga: {self.wave}\n"
                f"✓   Doğru: {self.dogru_s}     ✗ Yanlış: {self.yanlis_s}")
        tk.Label(card, text=info, font=("Segoe UI", 13),
                 fg=TEXT_COLOR, bg=CARD_COLOR,
                 justify="center").pack(pady=8, padx=20)

        # ---- AI Değerlendirmesi ----
        HoverButton(
            self, bg_color="#6A1B9A", active_bg="#8E24AA",
            text="🤖 AI DEĞERLENDİRMESİ GÖR",
            command=self._ai_degerlendirme_ac,
            width=28, height=2,
        ).pack(pady=10)

        btn_box = tk.Frame(self, bg=BG_COLOR)
        btn_box.pack(pady=12)
        HoverButton(btn_box, bg_color=PURPLE, active_bg=PURPLE_ACT,
                    text="Tekrar Oyna",
                    command=lambda: self.parent.show_frame(SpaceSetupFrame),
                    width=15, height=2).pack(side="left", padx=10)
        HoverButton(btn_box, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="Ana Menü", command=self._ana_menu,
                    width=15, height=2).pack(side="left", padx=10)

    def _ana_menu(self):
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)

    def _ai_degerlendirme_ac(self):
        self.parent.show_frame(
            AIUzayFrame,
            ozet={
                "sinif": self.sinif,
                "zorluk": self.zorluk,
                "score": self.score,
                "wave": self.wave,
                "dogru": self.dogru_s,
                "yanlis": self.yanlis_s,
                "toplam_soru": self.toplam_soru,
            },
        )

    def _quit(self):
        if not self.ended:
            oyun_kaydi_ekle(
                self.parent.active_student, "Newton'un İntikamı", self.score,
                "yarıda bırakıldı",
                {"dalga": self.wave, "dogru": self.dogru_s,
                 "yanlis": self.yanlis_s, "toplam_soru": self.toplam_soru},
            )
            self.ended = True
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        self.ended = True
        self.running = False
        if self.tick_id:
            try:
                self.after_cancel(self.tick_id)
            except Exception:
                pass
        try:
            if self.q_frame:
                if getattr(self, "_ai_hint_panel", None):
                    self._ai_hint_panel.hide()
                self.q_frame.destroy()
        except Exception:
            pass
        self._unbind_keys()
        self._ana_menu()


# ==============================================================================
# 🚀 UZAY — AI DEĞERLENDİRME EKRANI (canlı stream)
# ==============================================================================
class AIUzayFrame(tk.Frame):
    """Newton'un İntikamı sonuçlarını AI'ya gönderir, kişisel öneri stream eder."""

    def __init__(self, parent, ozet):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.ozet = ozet
        self.streaming = False
        self.stop_event = threading.Event()
        self.screen_alive = True
        self.tam_metin = ""

        self._build_ui()
        self.parent.bind("<Escape>", self._esc_handler)
        self.after(300, self._analiz_baslat)

    def _esc_handler(self, event=None):
        self._geri()

    # -------------------------------------------------------------- UI --
    def _build_ui(self):
        top = tk.Frame(self, bg=BG_COLOR, height=70)
        top.pack(fill="x", padx=24, pady=(18, 4))
        top.pack_propagate(False)

        tk.Label(
            top, text="🤖 AI DEĞERLENDİRMESİ",
            font=("Segoe UI", 22, "bold"),
            fg=TEXT_COLOR, bg=BG_COLOR,
        ).pack(side="left", anchor="w")

        self.lbl_durum = tk.Label(
            top, text="● Hazırlanıyor...",
            font=("Segoe UI", 10, "bold"),
            fg=YELLOW, bg=BG_COLOR,
        )
        self.lbl_durum.pack(side="right", anchor="e")

        tk.Label(
            self,
            text="Newton'un İntikamı sonuçların analiz ediliyor...  (ESC = geri)",
            font=("Segoe UI", 11),
            fg=SECONDARY_TEXT, bg=BG_COLOR,
        ).pack(padx=24, anchor="w")

        ozet_card = tk.Frame(self, bg=CARD_COLOR,
                              highlightbackground=CARD_LIGHT,
                              highlightthickness=1)
        ozet_card.pack(fill="x", padx=24, pady=(8, 6))

        ozet_satir = tk.Frame(ozet_card, bg=CARD_COLOR)
        ozet_satir.pack(pady=10, padx=14)

        def mini_istat(lbl, val, renk):
            f = tk.Frame(ozet_satir, bg=CARD_COLOR)
            f.pack(side="left", padx=10)
            tk.Label(f, text=lbl, font=("Segoe UI", 9),
                     fg=SECONDARY_TEXT, bg=CARD_COLOR).pack()
            tk.Label(f, text=str(val), font=("Segoe UI", 14, "bold"),
                     fg=renk, bg=CARD_COLOR).pack()

        mini_istat("PUAN", self.ozet["score"], YELLOW)
        mini_istat("DALGA", self.ozet["wave"], PURPLE)
        mini_istat("DOĞRU", self.ozet["dogru"], GREEN_ACTIVE)
        mini_istat("YANLIŞ", self.ozet["yanlis"], RED)
        mini_istat("KURTARMA", f"{self.ozet['dogru']}/{self.ozet['toplam_soru']}",
                   BLUE_ACTIVE)
        mini_istat("SEVİYE",
                   f"{self.ozet['sinif']}. sn / {self.ozet['zorluk']}",
                   SECONDARY_TEXT)

        outer = tk.Frame(self, bg=CARD_COLOR)
        outer.pack(fill="both", expand=True, padx=24, pady=(4, 12))

        self.text = tk.Text(
            outer, font=("Segoe UI", 16),
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat", wrap="word",
            padx=18, pady=14,
            spacing1=3, spacing3=3,
        )
        scroll = tk.Scrollbar(
            outer, orient="vertical", command=self.text.yview,
            bg=CARD_COLOR, troughcolor=CARD_COLOR,
            relief="flat", width=10,
        )
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.config(state="disabled")

        bottom = tk.Frame(self, bg=BG_COLOR)
        bottom.pack(fill="x", padx=24, pady=(0, 18))

        HoverButton(
            bottom, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
            text="← Sonuçlara Dön",
            command=self._geri,
            width=16, height=1,
        ).pack(side="left")

        HoverButton(
            bottom, bg_color=BLUE, active_bg=BLUE_ACTIVE,
            text="↻ Yeniden Sor",
            command=self._yeniden_baslat,
            width=14, height=1,
        ).pack(side="left", padx=8)

        HoverButton(
            bottom, bg_color=RED, active_bg="#9B111E",
            text="■ Durdur",
            command=lambda: self.stop_event.set(),
            width=10, height=1,
        ).pack(side="right")

    # -------------------------------------------------- Stream / analiz --
    def _analiz_baslat(self):
        if not self.screen_alive:
            return

        self.streaming = True
        self.tam_metin = ""
        self.stop_event = threading.Event()
        self.lbl_durum.config(text="● AI yazıyor...", fg=BLUE_ACTIVE)

        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")

        prompt = self._prompt_olustur()
        messages = [
            {
                "role": "system",
                "content": (
                    "Sen MATHİX eğitim platformunun AI Öğretmenisin. "
                    "Bir öğrencinin 'Newton'un İntikamı' adlı uzay temalı "
                    "matematik shooter oyunundaki performansını analiz "
                    "edip kişiselleştirilmiş, sıcak ve motive edici bir "
                    "geri bildirim yazacaksın. Türkçe yaz. Başlıklar ve "
                    "madde işaretleri kullan. 180 kelimeyi geçme. Oyunda "
                    "gemi vurulunca matematik sorusu çıkıyor — doğru "
                    "cevap gemiyi kurtarıyor, yanlış cevap kalkan kaybettiriyor."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        def on_chunk(token):
            if not self.screen_alive:
                return
            self.tam_metin += token
            self.parent.after(0, lambda: self._ekle(token))

        def on_done(full_text, stopped):
            if not self.screen_alive:
                return
            self.streaming = False
            if stopped:
                self.parent.after(0, lambda: self.lbl_durum.config(
                    text="■ Durduruldu", fg=YELLOW))
            else:
                self.parent.after(0, lambda: self.lbl_durum.config(
                    text="✓ Analiz tamamlandı", fg=GREEN_ACTIVE))

        def on_error(err):
            if not self.screen_alive:
                return
            self.streaming = False
            self.parent.after(0, lambda: self._hata(err))

        ai_stream_chat(
            "ogretmen:latest", messages,
            on_chunk, on_done, on_error, self.stop_event,
        )

    def _ekle(self, token):
        if not self.text.winfo_exists():
            return
        self.text.config(state="normal")
        self.text.insert("end", token)
        length = len(self.text.get("1.0", "end-1c"))
        size = 17 if length < 500 else 16 if length < 1400 else 14
        self.text.configure(font=("Segoe UI", size), spacing1=max(3, size // 3),
                            spacing3=max(3, size // 3))
        self.text.see("end")
        self.text.config(state="disabled")

    def _hata(self, err):
        if not self.text.winfo_exists():
            return
        self.lbl_durum.config(text="⚠ Ollama hatası", fg=RED)
        self.text.config(state="normal")
        self.text.insert(
            "end",
            f"\n\n⚠️ AI'ya bağlanılamadı:\n{err}\n\n"
            "Ollama'nın çalıştığından ve 'ogretmen:latest' modelinin "
            "yüklü olduğundan emin ol.",
        )
        self.text.config(state="disabled")

    # -------------------------------------------------- Prompt oluşturma --
    def _prompt_olustur(self):
        o = self.ozet
        toplam = o["toplam_soru"] or 1
        isabet = o["dogru"] / toplam * 100

        return (
            f"Oyun: Newton'un İntikamı (uzay temalı matematik shooter)\n"
            f"Öğrenci: {o['sinif']}. sınıf  •  Zorluk: {o['zorluk']}\n"
            f"Toplam puan: {o['score']}\n"
            f"Ulaşılan dalga: {o['wave']}\n"
            f"Toplam kurtarma sorusu: {o['toplam_soru']}\n"
            f"Doğru: {o['dogru']}  |  Yanlış: {o['yanlis']}\n"
            f"Kurtarma isabet oranı: %{isabet:.1f}\n\n"
            "Görev: Öğrenciye kişisel geri bildirim yaz:\n"
            "1) Kısa ve sıcak bir motivasyon cümlesi\n"
            "2) Oyun ve matematik performansı analizi\n"
            "3) 2-3 somut geliştirme önerisi\n"
            "4) Bir sonraki denemede hedef önerisi\n"
            "5) Cesaretlendirici bir kapanış"
        )

    # ---------------------------------------------------- Navigasyon --
    def _geri(self):
        self.screen_alive = False
        self.stop_event.set()
        try:
            self.parent.unbind("<Escape>")
        except Exception:
            pass
        self.parent.show_frame(SpaceSetupFrame)

    def _yeniden_baslat(self):
        if self.streaming:
            return
        self._analiz_baslat()
