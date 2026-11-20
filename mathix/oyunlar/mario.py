"""MATHİX — Euler'ün Macerası (Mario tarzı platform oyunu).

Özellikler:
  - Kamera kaydırmalı geniş dünya (5000 px)
  - 12 düşman, 12 altın, 3 blok, 6 boru, 16 platform
  - Yakalanınca matematik sorusu (prosedürel)
  - 💡 AI İpucu butonu — uzun cevap gelirse soru kutusu OTOMATİK BÜYÜR
  - Bitirme / yenilgi ekranları
"""
import math
import random
import tkinter as tk

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN, GREEN_ACTIVE, RED, YELLOW,
    SKY_COLOR, GROUND_COLOR, GRASS_COLOR,
    PLAYER_COLOR, PLAYER_DARK, COIN_COLOR,
    BLOCK_COLOR, BLOCK_LIGHT, PIPE_COLOR,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY,
)
from mathix.ui.widgets import HoverButton
from mathix.soru.uretici import soru_uret
from mathix.ui.game_ai_hint import GameAIHint
from mathix.protection import GameProtection
from mathix.ui.music import GameMusic
from mathix.oyun_kayıtları import oyun_kaydi_ekle


# ==============================================================================
# MARIO — KURULUM EKRANI
# ==============================================================================
class MarioSetupFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        tk.Label(self, text="EULER'ÜN MACERASI",
                 font=FONT_TITLE, fg=TEXT_COLOR, bg=BG_COLOR
                 ).pack(pady=(80, 10))
        tk.Label(self, text="Sınıf Seviyesi ve Oyun Zorluğunu Seçin",
                 font=FONT_SUBTITLE, fg=SECONDARY_TEXT, bg=BG_COLOR
                 ).pack(pady=(0, 30))

        card = tk.Frame(self, bg=CARD_COLOR, bd=1, relief="flat",
                        highlightbackground=CARD_LIGHT, highlightthickness=1)
        card.pack(padx=100, pady=10, fill="x")

        self.var_sinif = tk.StringVar(value=f"{parent.active_student['sinif']}. Sınıf")
        self.var_zorluk = tk.StringVar(value="Orta")

        r1 = tk.Frame(card, bg=CARD_COLOR)
        r1.pack(fill="x", padx=40, pady=15)
        tk.Label(r1, text="SINIF LEVEL", font=FONT_BODY,
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(side="left")
        m1 = tk.OptionMenu(r1, self.var_sinif, "Rastgele",
                            *[f"{i}. Sınıf" for i in range(1, 13)])
        m1.config(font=FONT_BODY, bg=CARD_LIGHT, fg=TEXT_COLOR,
                  bd=0, highlightthickness=0, width=15)
        m1.pack(side="right")

        r2 = tk.Frame(card, bg=CARD_COLOR)
        r2.pack(fill="x", padx=40, pady=15)
        tk.Label(r2, text="OYUN ZORLUĞU", font=FONT_BODY,
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(side="left")
        m2 = tk.OptionMenu(r2, self.var_zorluk, "Rastgele",
                            "Kolay", "Orta", "Zor")
        m2.config(font=FONT_BODY, bg=CARD_LIGHT, fg=TEXT_COLOR,
                  bd=0, highlightthickness=0, width=15)
        m2.pack(side="right")

        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=100, pady=40)
        HoverButton(btn_frame, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="← Geri", command=self._geri,
                    width=15).pack(side="left")
        HoverButton(btn_frame, bg_color=GREEN, active_bg=GREEN_ACTIVE,
                    text="OYNA ➔", command=self.oyunu_baslat,
                    width=15).pack(side="right")

    def _geri(self):
        from mathix.menu.menu import GamesMenuFrame
        self.parent.show_frame(GamesMenuFrame)

    def oyunu_baslat(self):
        s = self.var_sinif.get()
        z = self.var_zorluk.get()
        s = random.randint(1, 12) if s == "Rastgele" else int(s.split(".")[0])
        z = random.choice(["Kolay", "Orta", "Zor"]) if z == "Rastgele" else z
        self.parent.oyun_ayarlari.update({"sinif": s, "zorluk": z})
        self.parent.show_frame(MarioGameFrame)


# ==============================================================================
# MARIO — OYUN EKRANI
# ==============================================================================
class MarioGameFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        self.game_running = True
        self.question_active = False
        self.result_shown = False
        self.pending_result_after = None
        self.game_loop_after = None

        # --- SEVİYE SİSTEMİ ---
        self.current_level = 1
        self.max_levels = 10
        self.level_configs = {
            1: {"name": "Güneşli Vadi", "bg": SKY_COLOR, "ground": GROUND_COLOR, "accent": GRASS_COLOR},
            2: {"name": "Hafif Yağmurlu", "bg": "#708090", "ground": "#5D4037", "accent": "#4A646C"},
            3: {"name": "Karlı Zirve", "bg": "#E0F7FA", "ground": "#BDBDBD", "accent": "#FFFFFF"},
            4: {"name": "Fırtınalı Orman", "bg": "#2F4F4F", "ground": "#3E2723", "accent": "#2E7D32"},
            5: {"name": "Altın Sahil", "bg": "#87CEEB", "ground": "#F4A460", "accent": "#FFD700"},
            6: {"name": "Kızıl Çöl", "bg": "#FFB347", "ground": "#A52A2A", "accent": "#D2691E"},
            7: {"name": "Gece Yarısı", "bg": "#0B1320", "ground": "#1A1A1A", "accent": "#4B0082"},
            8: {"name": "Lav Mağarası", "bg": "#4A0000", "ground": "#212121", "accent": "#FF4500"},
            9: {"name": "Bulut Şehri", "bg": "#B3E5FC", "ground": "#E1F5FE", "accent": "#FFFFFF"},
            10: {"name": "Kozmik Final", "bg": "#1A237E", "ground": "#311B92", "accent": "#FFD700"},
        }

        self.WORLD_WIDTH = 5000
        self.FINISH_X = 4700
        self._world_scale = 1.0
        self._world_offset_x = 0.0
        self._world_offset_y = 0.0
        self.camera_x = 0
        self.CAMERA_LEFT = 250
        self.CAMERA_RIGHT = 650

        self.player_x = 120
        self.player_y = 445
        self.player_dx = 0
        self.player_dy = 0
        self.player_gravity = 0.7
        self.player_jump_velocity = -15
        self.player_grounded = True
        self.animation_counter = 0

        self.enemies = []
        self.coins = []
        self.enemy_speed = 2
        self.enemy_frame = 0
        self.puan = 0
        self.dogru_sayisi = 0
        self.yanlis_sayisi = 0

        # Soru kutusu — dinamik ölçeklenmesi için referanslar
        self.q_box_id = None
        self.q_hint_id = None

        self.platformlar = [
            (250, 350, 150, 45), (570, 250, 100, 45), (950, 370, 140, 45),
            (1200, 300, 130, 45), (1450, 390, 170, 45), (1750, 330, 140, 45),
            (2000, 240, 150, 45), (2250, 360, 180, 45), (2550, 300, 150, 45),
            (2800, 200, 140, 45), (3050, 350, 180, 45), (3350, 270, 160, 45),
            (3650, 380, 140, 45), (3900, 300, 170, 45), (4200, 230, 150, 45),
            (4450, 350, 150, 45),
        ]
        self.question_blocks = []
        self.weather_after = None

        self.game_canvas = tk.Canvas(self, width=1000, height=650,
                                      bg=SKY_COLOR, highlightthickness=0)
        self.game_canvas.pack(fill="both", expand=True)
        self.game_canvas.bind("<Configure>", self._resize_game_view, add="+")

        self.setup_world()
        self._setup_touch_controls()
        self.bind_keys()
        self.setup_hud()
        self.game_canvas.focus_set()
        self.game_loop_after = self.after(30, self.oyun_dongusu)
        self.protection = GameProtection(self, "Euler'ün Macerası",
                                         self._koruma_duraklat, self._koruma_devam,
                                         student_id=self.parent.active_student["id"])
        self.music = GameMusic("mario")
        self.music.attach(self)

    def _resize_game_view(self, event=None):
        """Zoom the fixed 1000×650 game view uniformly to fit the Canvas."""
        width = max(1, event.width if event else self.game_canvas.winfo_width())
        height = max(1, event.height if event else self.game_canvas.winfo_height())
        scale = max(0.75, min(2.5, min(width / 1000, height / 650)))
        offset_x = (width - 1000 * scale) / 2
        offset_y = (height - 650 * scale) / 2
        ratio = scale / self._world_scale
        if abs(ratio - 1.0) > 0.001:
            self.game_canvas.scale("world", 0, 0, ratio, ratio)
            self.game_canvas.scale("coin", 0, 0, ratio, ratio)
        dx = offset_x - self._world_offset_x * ratio
        dy = offset_y - self._world_offset_y * ratio
        self.game_canvas.move("world", dx, dy)
        self.game_canvas.move("coin", dx, dy)
        self._world_scale = scale
        self._world_offset_x = offset_x
        self._world_offset_y = offset_y

    def _scale_new_world(self):
        """Scale freshly generated level items to the current Canvas view."""
        if self._world_scale != 1.0:
            self.game_canvas.scale("world", 0, 0, self._world_scale, self._world_scale)
            self.game_canvas.scale("coin", 0, 0, self._world_scale, self._world_scale)
        if self._world_offset_x or self._world_offset_y:
            self.game_canvas.move("world", self._world_offset_x, self._world_offset_y)
            self.game_canvas.move("coin", self._world_offset_x, self._world_offset_y)
        camera_shift = -self.camera_x * self._world_scale
        if camera_shift:
            self.game_canvas.move("world", camera_shift, 0)
            self.game_canvas.move("coin", camera_shift, 0)

    def _koruma_duraklat(self):
        self._koruma_onceki_durum = self.game_running
        if hasattr(self, "music"):
            self.music.pause()
        self.game_running = False
        if self.game_loop_after:
            try:
                self.after_cancel(self.game_loop_after)
            except tk.TclError:
                pass
            self.game_loop_after = None

    def _koruma_devam(self):
        if not self.question_active and getattr(self, "_koruma_onceki_durum", True):
            if hasattr(self, "music"):
                self.music.resume()
            self.game_running = True
            self.game_loop_after = self.after(30, self.oyun_dongusu)

    # --------------------------------------------------------- Dünya çizimi --
    def setup_world(self):
        cv = self.game_canvas
        conf = self.level_configs[self.current_level]
        cv.configure(bg=conf["bg"])

        # Platformlar kademeli daralır ve seviye ilerledikçe yükseklik farkı
        # artar; rota yine tek zıplayışla aşılabilecek sınırlar içinde kalır.
        level_step = self.current_level - 1
        height_pattern = (0, 1, 2, 1, -1, 0, 2, 1, -1, 1, 2, 0, -1, 1, 0)
        height_scale = 5 + level_step
        self.platformlar = []
        for i in range(15):
            x = 270 + i * 292 + ((self.current_level * 31 + i * 17) % 26)
            y = 365 + height_pattern[i % len(height_pattern)] * height_scale
            width = max(
                100,
                178 - level_step * 7 + ((i * 31 + self.current_level * 23) % 31) - 15,
            )
            self.platformlar.append((x, y, width, 45))
        self.question_blocks = []
        
        cv.create_rectangle(0, 0, self.WORLD_WIDTH, 650,
                            fill=conf["bg"], outline="", tags="world")

        # Uzak siluetler az sayıda büyük şekille derinlik verir; her karede
        # yeniden çizilmez ve kamera ile zemin gibi birlikte kayar.
        if self.current_level in (1, 3, 4, 5, 6, 9):
            ridge = "#A9C9D4" if self.current_level in (1, 9) else "#46685B"
            if self.current_level == 3:
                ridge = "#8DAFC0"
            cv.create_polygon(0, 365, 360, 220, 690, 355, 1050, 195,
                              1430, 365, 1810, 235, 2190, 370, 2600, 205,
                              3000, 360, 3400, 220, 3800, 365, 4230, 205,
                              4700, 350, 5000, 265, 5000, 500, 0, 500,
                              fill=ridge, outline="", tags="world")
            cv.create_polygon(0, 415, 520, 330, 980, 420, 1510, 310,
                              2070, 425, 2630, 320, 3220, 420, 3780, 305,
                              4380, 420, 5000, 335, 5000, 500, 0, 500,
                              fill="#597C69" if self.current_level in (1, 4) else "#7B9B89",
                              outline="", tags="world")
            if self.current_level == 3:
                # Beyaz zirve vurguları karlı bölgeyi okunaklı kılar.
                cv.create_polygon(205, 282, 360, 220, 430, 285, 378, 267,
                                  350, 278, 330, 250, 292, 284,
                                  fill="#F5FCFF", outline="", tags="world")
                cv.create_polygon(900, 255, 1050, 195, 1120, 260, 1070, 242,
                                  1048, 253, 1027, 228, 990, 259,
                                  fill="#F5FCFF", outline="", tags="world")

        # Güneş/ay ve atmosferik ışıklar: statik Canvas öğeleri, animasyon yok.
        if self.current_level in (1, 5, 6):
            sun_x = 860 if self.current_level == 1 else 760
            sun_color = "#FFE58A" if self.current_level != 6 else "#FFF1B0"
            cv.create_oval(sun_x-53, 48, sun_x+53, 154, fill=sun_color,
                           outline="", tags="world")
            cv.create_oval(sun_x-70, 31, sun_x+70, 171, outline="#FFF0B0",
                           width=2, tags="world")
        elif self.current_level in (7, 10):
            cv.create_oval(820, 65, 900, 145, fill="#F6F1D5", outline="",
                           tags="world")
            for sx, sy, sr in ((180, 80, 2), (520, 160, 2), (1160, 70, 3),
                               (1660, 165, 2), (2290, 85, 2), (3020, 145, 3),
                               (3640, 68, 2), (4340, 150, 2), (4820, 74, 3)):
                cv.create_oval(sx-sr, sy-sr, sx+sr, sy+sr, fill="#FFF2B0",
                               outline="", tags="world")

        # Sunny worlds have leafy trees; rain/snow have matching cloud layers.
        if self.current_level in (1, 4, 9):
            tree_colors = ("#287A42", "#32934D") if self.current_level == 1 else (
                ("#174D3A", "#2B7650") if self.current_level == 4 else
                ("#4E9FB5", "#7AC6D4"))
            for x in range(170, self.WORLD_WIDTH - 100, 560):
                trunk_y = 420
                cv.create_rectangle(x + 24, trunk_y, x + 42, 490,
                                    fill="#79502B", outline="#4D321D", tags="world")
                cv.create_oval(x, trunk_y - 65, x + 66, trunk_y + 3,
                               fill=tree_colors[0], outline="#1B5D32", width=2, tags="world")
                cv.create_oval(x + 14, trunk_y - 92, x + 78, trunk_y - 24,
                               fill=tree_colors[1], outline="#1B5D32", width=2, tags="world")

        cloud_col = "white" if self.current_level != 3 else "#D0E0FF"
        for x, y in [(120, 90), (450, 130), (730, 75), (1100, 100),
                     (1450, 70), (1800, 120), (2600, 130), (3400, 120),
                     (4200, 110)]:
            cv.create_oval(x, y + 3, x + 110, y + 38,
                           fill="#D0E0FF", outline="", tags="world")
            cv.create_oval(x, y, x + 60, y + 35,
                           fill=cloud_col, outline="", tags="world")
            cv.create_oval(x + 25, y - 15, x + 85, y + 35,
                           fill=cloud_col, outline="", tags="world")
            cv.create_oval(x + 55, y, x + 110, y + 35,
                           fill=cloud_col, outline="", tags="world")

        # Borular artık gerçek, zıplanabilir engeller. Seviyeler ilerledikçe
        # sayıları ve genişlikleri artar.
        pipe_count = 5 + (self.current_level + 1) // 2
        self.pipes = []
        pipe_start, pipe_end = 720, 4460
        pipe_width = 70 + self.current_level * 2
        pipe_height = 105 + min(20, self.current_level * 2)
        for i in range(pipe_count):
            bx = int(pipe_start + i * (pipe_end - pipe_start) / (pipe_count - 1))
            top = 500 - pipe_height
            self.pipes.append((bx, top, pipe_width, pipe_height))
            cv.create_rectangle(bx, top + 14, bx + pipe_width, 500,
                                 fill=PIPE_COLOR, outline="#0A6E32",
                                 width=3, tags="world")
            cv.create_line(bx + 15, top + 16, bx + 15, 498,
                           fill="#55D477", width=3, tags="world")
            cv.create_rectangle(bx - 6, top, bx + pipe_width + 6, top + 26,
                                 fill=PIPE_COLOR, outline="#0A6E32",
                                 width=3, tags="world")
            cv.create_line(bx + 4, top + 5, bx + pipe_width - 4, top + 5,
                           fill="#72E393", width=2, tags="world")

        # Platformlar
        for px, py, pw, ph in self.platformlar:
            cv.create_rectangle(px, py, px + pw, py + ph,
                                 fill=BLOCK_COLOR, outline="#7A3F17",
                                 width=2, tags="world")
            cv.create_rectangle(px, py, px + pw, py + 8,
                                 fill=BLOCK_LIGHT, outline="", tags="world")
            for step in range(px + 30, px + pw, 30):
                cv.create_line(step, py + 8, step, py + ph,
                                fill="#7A3F17", tags="world")

        # A head bump awards points once; blocks are solid platforms too.
        def add_question_block(bx, by, tag):
            self.question_blocks.append({
                "x": bx, "y": by, "tag": tag, "used": False,
            })
            rect_id = cv.create_rectangle(
                bx, by, bx + 44, by + 44, fill=BLOCK_COLOR,
                outline="#7A3F17", width=2,
                tags=("world", "qblock", tag),
            )
            cv.create_line(bx + 3, by + 3, bx + 41, by + 3,
                           fill=BLOCK_LIGHT, width=2, tags=("world", tag))
            cv.create_text(bx + 22, by + 22, text="?",
                           font=("Arial", 18, "bold"), fill=YELLOW,
                           tags=("world", tag, f"{tag}_mark"))
            self.question_blocks[-1]["rect_id"] = rect_id
            self.platformlar.append((bx, by, 44, 44))

        # Başlangıçta yan yana duran iki yüksek blok: ilk zıplayışta ulaşılır.
        add_question_block(80, 270, "question_block_start_1")
        add_question_block(128, 270, "question_block_start_2")

        # Zemin + çim
        cv.create_rectangle(0, 500, self.WORLD_WIDTH, 650,
                            fill=conf["ground"], outline="", tags="world")
        cv.create_rectangle(0, 490, self.WORLD_WIDTH, 505,
                            fill=conf["accent"], outline="", tags="world")
        ground_detail = {
            1: "#6EEB7F", 2: "#9CBBC6", 3: "#F7FFFF", 4: "#3E9B5E",
            5: "#FFE28A", 6: "#E87C42", 7: "#6256A5", 8: "#FF6A32",
            9: "#9DEBFF", 10: "#8B6BEA",
        }[self.current_level]
        for step in range(0, self.WORLD_WIDTH, 120):
            cv.create_line(step, 490, step + 9, 484,
                           fill=ground_detail, width=2, tags="world")
            cv.create_line(step + 14, 490, step + 19, 485,
                           fill=ground_detail, width=2, tags="world")

        # Biyomlara özgü, sabit zemin dokuları; animasyona ek yük getirmez.
        if self.current_level == 6:
            for x in range(240, self.WORLD_WIDTH, 680):
                cv.create_polygon(x, 490, x+18, 445, x+25, 490,
                                  fill="#3B8C58", outline="#27613C", tags="world")
                cv.create_line(x+20, 464, x+7, 453, fill="#5DBB70", width=3,
                               tags="world")
        elif self.current_level == 8:
            for x in range(180, self.WORLD_WIDTH, 520):
                cv.create_oval(x, 496, x+120, 512, fill="#FF4A16",
                               outline="#FFB02E", width=2, tags="world")
                cv.create_oval(x+22, 499, x+82, 506, fill="#FFD43B",
                               outline="", tags="world")

        # Düşman türleri seviyeye göre değişir; ilerleyen bölümlerde uçan ve
        # daha hızlı zırhlı düşmanlar da rotaya eklenir.
        enemy_rosters = {
            1: ("goomba", "goomba", "koopa"),
            2: ("goomba", "koopa", "beetle"),
            3: ("goomba", "beetle", "wisp"),
            4: ("koopa", "beetle", "wisp"),
            5: ("goomba", "koopa", "beetle", "wisp"),
            6: ("goomba", "beetle", "beetle", "wisp"),
            7: ("koopa", "beetle", "wisp", "wisp"),
            8: ("goomba", "beetle", "wisp", "wisp"),
            9: ("koopa", "beetle", "wisp", "wisp"),
            10: ("goomba", "koopa", "beetle", "wisp", "wisp"),
        }
        roster = enemy_rosters.get(self.current_level, enemy_rosters[10])
        enemy_spacing = max(285, 410 - (self.current_level - 1) * 12)
        for i, x in enumerate(range(430, 4500, enemy_spacing)):
            kind = roster[(i * 3 + random.randrange(len(roster))) % len(roster)]
            self.dusman_ekle(x, 466, kind)
        for i, (px, py, pw, _ph) in enumerate(self.platformlar[2::5]):
            kind = roster[(i * 2 + len(self.enemies)) % len(roster)]
            self.dusman_ekle(px + pw // 2, py - 35, kind)

        # Altınlar
        for i, (px, py, pw, _ph) in enumerate(self.platformlar[:15:2]):
            if i % 5 == 2:
                continue
            # Keep coin arcs away from enemies and block faces.
            for j in range(3):
                self.coin_ekle(px + pw // 2 - 22 + j * 24, py - 57 - (j == 1) * 14)
        for x in (120, 2500, 4620):
            self.coin_ekle(x, 425)

        self._setup_weather()

        # Bitiş bayrağı
        cv.create_rectangle(self.FINISH_X, 220, self.FINISH_X + 10, 500,
                            fill="#CCCCCC", outline="#666666", tags="world")
        cv.create_polygon(self.FINISH_X + 10, 230,
                           self.FINISH_X + 120, 265,
                           self.FINISH_X + 10, 300,
                           fill=GREEN, outline="#145C2A", width=2, tags="world")
        cv.create_text(self.FINISH_X + 55, 265, text="BİTİŞ",
                       font=("Segoe UI", 12, "bold"), fill="white",
                       tags="world")
        cv.create_oval(self.FINISH_X - 15, 485, self.FINISH_X + 25, 510,
                       fill="#555555", outline="", tags="world")
        self._scale_new_world()

    def _setup_weather(self):
        cv = self.game_canvas
        cv.delete("weather")
        if self.weather_after:
            try:
                self.after_cancel(self.weather_after)
            except tk.TclError:
                pass
        self.weather_after = None
        self.weather_particles = []
        if self.current_level in (2, 3):
            # Efektler mevcut oyun döngüsünde güncellenir; ikinci bir timer yok.
            for _ in range(18):
                x, y = random.randint(0, 1000), random.randint(0, 650)
                if self.current_level == 2:
                    ident = cv.create_line(x, y, x - 5, y + 18,
                                           fill="#B9D7E8", width=2,
                                           tags="weather")
                    speed = random.uniform(7.0, 11.0)
                    drift = random.uniform(-1.2, -0.4)
                else:
                    radius = random.choice((2, 3, 4))
                    ident = cv.create_oval(x, y, x + radius, y + radius,
                                           fill="#FFFFFF", outline="",
                                           tags="weather")
                    speed = random.uniform(2.8, 4.8)
                    drift = random.uniform(-0.45, 0.45)
                self.weather_particles.append((ident, speed, drift))

    def _advance_weather(self):
        if not self.weather_particles:
            return
        cv = self.game_canvas
        for ident, speed, drift in self.weather_particles:
            coords = cv.coords(ident)
            if not coords:
                continue
            cv.move(ident, drift, speed)
            coords = self.game_canvas.coords(ident)
            if coords and coords[1] > 650:
                x = random.randint(0, 1000)
                if self.current_level == 2:
                    cv.coords(ident, x, -20, x-5, -2)
                else:
                    radius = max(2, coords[2] - coords[0])
                    cv.coords(ident, x, -radius, x+radius, 0)

    # ---------------------------------------------------------- Düşman/altın --
    def _enemy_tags(self, tag):
        return ("world", "enemy", tag)

    def _enemy_oval(self, tag, coords, fill, outline="#33201A", width=1):
        return self.game_canvas.create_oval(
            *coords, fill=fill, outline=outline, width=width,
            tags=self._enemy_tags(tag),
        )

    def _enemy_line(self, tag, coords, fill, width=1):
        return self.game_canvas.create_line(
            *coords, fill=fill, width=width, capstyle="round",
            tags=self._enemy_tags(tag),
        )

    def _enemy_polygon(self, tag, coords, fill, outline="#33201A", width=1):
        return self.game_canvas.create_polygon(
            *coords, fill=fill, outline=outline, width=width,
            tags=self._enemy_tags(tag),
        )

    def _draw_enemy(self, kind, x, y, tag):
        if kind == "goomba":
            body = self._enemy_oval(tag, (x + 5, y + 13, x + 34, y + 33), "#A95C2A")
            self._enemy_oval(tag, (x + 2, y + 2, x + 37, y + 27), "#C98245", "#69391E", 2)
            self._enemy_oval(tag, (x + 10, y + 10, x + 18, y + 22), "#FFF3D5", "#53301D")
            self._enemy_oval(tag, (x + 23, y + 10, x + 31, y + 22), "#FFF3D5", "#53301D")
            self._enemy_oval(tag, (x + 13, y + 14, x + 16, y + 20), "#23160F", "#23160F")
            self._enemy_oval(tag, (x + 25, y + 14, x + 28, y + 20), "#23160F", "#23160F")
            self._enemy_line(tag, (x + 15, y + 26, x + 27, y + 26), "#4D2018", 2)
            self._enemy_oval(tag, (x + 1, y + 28, x + 16, y + 34), "#39231B")
            self._enemy_oval(tag, (x + 25, y + 28, x + 40, y + 34), "#39231B")
            return body, 40, 34

        if kind == "koopa":
            body = self._enemy_oval(tag, (x + 11, y + 17, x + 34, y + 33), "#E3C96B")
            self._enemy_oval(tag, (x + 3, y + 9, x + 31, y + 32), "#348B4D", "#174D2B", 2)
            self._enemy_oval(tag, (x + 8, y + 12, x + 27, y + 29), "#56B768", "#174D2B")
            self._enemy_line(tag, (x + 17, y + 13, x + 17, y + 28), "#174D2B", 2)
            self._enemy_line(tag, (x + 9, y + 21, x + 26, y + 21), "#174D2B", 2)
            self._enemy_oval(tag, (x + 24, y + 3, x + 43, y + 20), "#E7D17A", "#74612A", 2)
            self._enemy_oval(tag, (x + 34, y + 7, x + 39, y + 14), "white", "#5B4D25")
            self._enemy_oval(tag, (x + 36, y + 9, x + 38, y + 13), "#17211A", "#17211A")
            self._enemy_line(tag, (x + 34, y + 17, x + 41, y + 16), "#754D31", 1)
            self._enemy_oval(tag, (x + 8, y + 29, x + 19, y + 35), "#D7BC63")
            self._enemy_oval(tag, (x + 26, y + 29, x + 37, y + 35), "#D7BC63")
            return body, 44, 35

        if kind == "beetle":
            body = self._enemy_oval(tag, (x + 3, y + 9, x + 39, y + 31), "#263B76", "#111D43", 2)
            self._enemy_oval(tag, (x + 7, y + 5, x + 35, y + 28), "#405FBA", "#15244F", 2)
            self._enemy_polygon(tag, (x + 21, y + 7, x + 22, y + 27, x + 18, y + 27), "#182B62", "#182B62")
            self._enemy_line(tag, (x + 12, y + 9, x + 15, y + 4), "#182B62", 2)
            self._enemy_line(tag, (x + 29, y + 9, x + 32, y + 4), "#182B62", 2)
            self._enemy_oval(tag, (x + 12, y + 13, x + 18, y + 20), "#FFF3D5", "#111D43")
            self._enemy_oval(tag, (x + 25, y + 13, x + 31, y + 20), "#FFF3D5", "#111D43")
            self._enemy_oval(tag, (x + 14, y + 15, x + 17, y + 19), "#111D43", "#111D43")
            self._enemy_oval(tag, (x + 27, y + 15, x + 30, y + 19), "#111D43", "#111D43")
            for leg_x in (8, 17, 27, 36):
                self._enemy_line(tag, (x + leg_x, y + 25, x + leg_x - 3, y + 33), "#111D43", 2)
            return body, 42, 34

        # Uçan hayalet: seviye ilerledikçe zeminin üzerinden süzülür.
        body = self._enemy_polygon(
            tag, (x + 5, y + 28, x + 3, y + 12, x + 10, y + 3,
                  x + 20, y, x + 31, y + 5, x + 37, y + 16,
                  x + 34, y + 29, x + 27, y + 24, x + 20, y + 31,
                  x + 13, y + 25), "#9B6BCE", "#4A2D71", 2,
        )
        self._enemy_oval(tag, (x + 10, y + 10, x + 18, y + 21), "#F6F0FF", "#51356F")
        self._enemy_oval(tag, (x + 24, y + 10, x + 32, y + 21), "#F6F0FF", "#51356F")
        self._enemy_oval(tag, (x + 13, y + 14, x + 16, y + 19), "#29183F", "#29183F")
        self._enemy_oval(tag, (x + 26, y + 14, x + 29, y + 19), "#29183F", "#29183F")
        self._enemy_oval(tag, (x + 18, y + 23, x + 23, y + 27), "#4A2D71", "#4A2D71")
        self._enemy_oval(tag, (x + 4, y + 7, x + 10, y + 17), "#C8A9ED", "#7C54A8")
        self._enemy_oval(tag, (x + 31, y + 7, x + 37, y + 17), "#C8A9ED", "#7C54A8")
        return body, 40, 34

    def dusman_ekle(self, x, y, kind=None):
        if kind is None:
            kind = random.choice(("goomba", "koopa", "beetle", "wisp"))
        tag = f"enemy_{len(self.enemies)}"
        if kind == "wisp":
            y -= 45
        id_, width, height = self._draw_enemy(kind, x, y, tag)
        speed = {"goomba": 1.2, "koopa": 0.9,
                 "beetle": 2.0, "wisp": 1.65}[kind]
        gravity_base = {"goomba": 0.58, "koopa": 0.48,
                        "beetle": 0.78, "wisp": 0.0}[kind]
        gravity = max(0.0, gravity_base + random.uniform(-0.07, 0.07))
        mario_jump_height = (
            self.player_jump_velocity ** 2 / (2 * self.player_gravity)
        )
        # Düşman zıplaması seviye bantlarına göre kademeli yükselir.
        height_factor = {
            1: 0.0, 2: 0.0,
            3: 0.20, 4: 0.20,
            5: 0.45, 6: 0.45,
            7: 0.70, 8: 0.70,
            9: 1.0, 10: 1.0,
        }[self.current_level]
        jump_power = (
            math.sqrt(2 * gravity * mario_jump_height * height_factor)
            if gravity else 0
        )
        self.enemies.append({
            "x": x, "y": y, "dx": random.choice([-1, 1]),
            "base_y": y, "phase": random.random() * 6.28,
            "tag": tag, "id": id_, "kind": kind,
            "vertical_speed": 0.0,
            "gravity": gravity,
            "grounded": kind != "wisp",
            "jump_power": jump_power * random.uniform(0.97, 1.03),
            "jump_timer": random.randint(35, 110),
            "speed": speed, "min_x": max(20, x - 145),
            "max_x": min(self.WORLD_WIDTH - width, x + 145),
            "width": width, "height": height,
        })

    def coin_ekle(self, x, y):
        tag = f"coin_{len(self.coins)}"
        id_ = self.game_canvas.create_oval(
            x, y, x + 22, y + 30,
            fill=COIN_COLOR, outline="#C89B00", width=2,
            tags=(tag, "coin"),
        )
        self.game_canvas.create_oval(
            x + 6, y + 6, x + 16, y + 24,
            fill=COIN_COLOR, outline="white", width=1,
            tags=(tag, "coin"),
        )
        self.coins.append({"x": x, "y": y, "id": id_, "tag": tag})

    # ----------------------------------------------------------- Tuş bağları --
    def bind_keys(self):
        p = self.parent
        for key in ["<Left>", "a", "A"]:
            p.bind(key, lambda e: (self.set_dx(-6), self._hide_controls()))
        for key in ["<Right>", "d", "D"]:
            p.bind(key, lambda e: (self.set_dx(6), self._hide_controls()))
        for key in ["<KeyRelease-Left>", "<KeyRelease-Right>",
                    "<KeyRelease-a>", "<KeyRelease-d>",
                    "<KeyRelease-A>", "<KeyRelease-D>"]:
            p.bind(key, lambda e: self.set_dx(0))
        for key in ["<Up>", "<space>", "w", "W"]:
            p.bind(key, lambda e: (self.zipla(), self._hide_controls()))
        p.bind("<Escape>", lambda e: self.cikis_yap())

    def _setup_touch_controls(self):
        # Sol Kontroller (Sola, Sağa) - Sol En Alt
        self.ctrl_frame_left = tk.Frame(self, bg=BG_COLOR)
        self.ctrl_frame_left.place(relx=0.02, rely=0.88)
        
        self.btn_left = HoverButton(self.ctrl_frame_left, text="←", bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                                    width=6, height=2, command=lambda: self.set_dx(-6))
        self.btn_left.pack(side="left", padx=5)
        
        self.btn_right = HoverButton(self.ctrl_frame_left, text="→", bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                                      width=6, height=2, command=lambda: self.set_dx(6))
        self.btn_right.pack(side="left", padx=5)

        # Sağ Kontroller (Zıpla) - Sağ En Alt
        self.ctrl_frame_right = tk.Frame(self, bg=BG_COLOR)
        self.ctrl_frame_right.place(relx=0.86, rely=0.88)
        
        self.btn_jump = HoverButton(self.ctrl_frame_right, text="↑", bg_color=BLUE, active_bg=BLUE_ACTIVE,
                                    width=6, height=2, command=self.zipla)
        self.btn_jump.pack(side="left", padx=5)

        # Ekrana tıklayınca butonları göster
        self.game_canvas.bind("<Button-1>", lambda e: self._show_controls())



    def _hide_controls(self):
        if hasattr(self, 'ctrl_frame_left') and self.ctrl_frame_left.winfo_exists():
            self.ctrl_frame_left.place_forget()
        if hasattr(self, 'ctrl_frame_right') and self.ctrl_frame_right.winfo_exists():
            self.ctrl_frame_right.place_forget()

    def _show_controls(self):
        if hasattr(self, 'ctrl_frame_left') and self.ctrl_frame_left.winfo_exists():
            self.ctrl_frame_left.place(relx=0.02, rely=0.88)
        if hasattr(self, 'ctrl_frame_right') and self.ctrl_frame_right.winfo_exists():
            self.ctrl_frame_right.place(relx=0.86, rely=0.88)

    def set_dx(self, val):
        if not self.question_active:
            self.player_dx = val
            # Butonları hemen gizleme, kullanıcı basılı tuttuğunda hareket etsin

    def zipla(self, e=None):
        if self.player_grounded and self.game_running and not self.question_active:
            self.player_dy = self.player_jump_velocity
            self.player_grounded = False
            # Butonları hemen gizleme

    # ------------------------------------------------------------------ HUD --
    def setup_hud(self):
        self.game_canvas.create_rectangle(
            15, 12, 390, 48,
            fill=CARD_COLOR, outline=CARD_LIGHT, width=2,
            tags="hud",
        )
        self.hud_puan = self.game_canvas.create_text(
            105, 30, text="Puan: 0 ⭐",
            font=("Segoe UI", 13, "bold"), fill=YELLOW,
            tags="hud",
        )
        
        self.hud_seviye = self.game_canvas.create_text(
            290, 30, text=f"Seviye: {self.current_level}/{self.max_levels}",
            font=("Segoe UI", 13, "bold"), fill=TEXT_COLOR,
            tags="hud",
        )
        
        tk.Button(self, text="MENÜ", font=("Segoe UI", 10, "bold"),
                  bg=RED, fg=TEXT_COLOR, relief="flat", cursor="hand2",
                  command=self.cikis_yap).place(relx=0.985, y=12, anchor="ne",
                                                width=92, height=38)

    # --------------------------------------------------------- Çizim — oyuncu --
    def oyuncu_ciz(self):
        cv = self.game_canvas
        cv.delete("player")
        ex = self.player_x - self.camera_x
        ey = self.player_y
        self.animation_counter += abs(self.player_dx)

        foot_offset = 0
        if not self.player_grounded:
            foot_offset = -6
        elif self.player_dx != 0:
            foot_offset = math.sin(self.animation_counter * 0.2) * 5

        d = 4 if self.player_dx >= 0 else -4

        # Ayakkabılar
        cv.create_oval(ex + 2, ey + 35 + foot_offset, ex + 14, ey + 44 + foot_offset,
                       fill="#5B2C06", outline="black", tags="player")
        cv.create_oval(ex + 16, ey + 35 - foot_offset, ex + 28, ey + 44 - foot_offset,
                       fill="#5B2C06", outline="black", tags="player")

        # Tulum
        cv.create_rectangle(ex + 4, ey + 20, ex + 26, ey + 38,
                            fill="#1F6FEB", outline="black", tags="player")
        cv.create_rectangle(ex + 6, ey + 16, ex + 10, ey + 24,
                            fill="#1F6FEB", outline="", tags="player")
        cv.create_rectangle(ex + 20, ey + 16, ex + 24, ey + 24,
                            fill="#1F6FEB", outline="", tags="player")
        cv.create_oval(ex + 6, ey + 23, ex + 9, ey + 26,
                       fill=YELLOW, outline="", tags="player")
        cv.create_oval(ex + 21, ey + 23, ex + 24, ey + 26,
                       fill=YELLOW, outline="", tags="player")

        # Gömlek
        cv.create_rectangle(ex + 4, ey + 16, ex + 26, ey + 22,
                            fill=PLAYER_COLOR, outline="", tags="player")
        cv.create_oval(ex - 2, ey + 18, ex + 5, ey + 25,
                       fill=PLAYER_COLOR, outline="black", tags="player")
        cv.create_oval(ex + 25, ey + 18, ex + 32, ey + 25,
                       fill=PLAYER_COLOR, outline="black", tags="player")

        # Yüz
        cv.create_oval(ex + 5, ey, ex + 25, ey + 18,
                       fill="#F5B27A", outline="black", tags="player")
        cv.create_oval(ex + 12 + d, ey + 5, ex + 15 + d, ey + 9,
                       fill="white", outline="", tags="player")
        cv.create_oval(ex + 13 + d, ey + 6, ex + 15 + d, ey + 8,
                       fill="black", outline="", tags="player")
        cv.create_rectangle(ex + 10 + d, ey + 11, ex + 18 + d, ey + 14,
                            fill="black", outline="", tags="player")

        # Şapka
        cv.create_oval(ex + 3, ey - 8, ex + 27, ey + 4,
                       fill=PLAYER_COLOR, outline="black", tags="player")
        cv.create_rectangle(ex + 1 + d, ey, ex + 25 + d, ey + 3,
                            fill=PLAYER_COLOR, outline="", tags="player")
        cv.create_oval(ex + 11, ey - 4, ex + 19, ey + 2,
                       fill="white", outline="", tags="player")
        cv.create_text(ex + 15, ey - 1, text="M",
                       font=("Arial", 6, "bold"), fill=PLAYER_COLOR,
                       tags="player")
        if self._world_scale != 1.0:
            cv.scale("player", 0, 0, self._world_scale, self._world_scale)
        if self._world_offset_x or self._world_offset_y:
            cv.move("player", self._world_offset_x, self._world_offset_y)

    # -------------------------------------------------------------- Oyun loop --
    def dikdortgen_cakisiyor(self, x1, y1, w1, h1, x2, y2, w2, h2):
        return x1 < x2 + w2 and x1 + w1 > x2 and y1 < y2 + h2 and y1 + h1 > y2

    def oyun_dongusu(self):
        if not self.game_running or self.question_active:
            return

        # Hava efektleri aynı kare döngüsünde ilerler; böylece 160 ms'lik
        # basamaklı hareket ve fazladan Tk zamanlayıcısı ortadan kalkar.
        self._advance_weather()

        previous_x = self.player_x
        self.player_x += self.player_dx
        self.player_x = max(10, min(self.player_x, self.WORLD_WIDTH - 50))

        previous_y = self.player_y
        self.player_dy += self.player_gravity
        self.player_y += self.player_dy
        self.player_grounded = False

        if self.player_dy < 0:
            for block in self.question_blocks:
                bx, by = block["x"], block["y"]
                if (not block["used"] and self.player_x + 28 > bx
                        and self.player_x < bx + 44
                        and previous_y - 8 >= by + 44
                        and self.player_y - 8 <= by + 44):
                    block["used"] = True
                    self.player_y = by + 53
                    self.player_dy = 0
                    self.puan += 25
                    self.game_canvas.itemconfig(block["rect_id"], fill="#8A7250")
                    self.game_canvas.itemconfig(f"{block['tag']}_mark", text="✓")
                    self.game_canvas.itemconfig(
                        self.hud_puan, text=f"Puan: {self.puan} ⭐")
                    self.game_canvas.move(block["tag"], 0, -7 * self._world_scale)
                    self.after(100, lambda tag=block["tag"]:
                               self.game_canvas.move(tag, 0, 7 * self._world_scale))
                    score_id = self.game_canvas.create_text(
                        bx + 22, by - 12, text="+25 ⭐", fill=YELLOW,
                        font=("Segoe UI", 12, "bold"), tags=("world", "block_score"))
                    self.after(700, lambda ident=score_id:
                               self.game_canvas.delete(ident))
                    # Yan yana duran başlangıç bloklarında tek zıplayış
                    # iki bloğu aynı anda tetiklemesin.
                    break

        if self.player_y >= 445:
            self.player_y = 445
            self.player_dy = 0
            self.player_grounded = True

        for px, py, pw, ph in self.platformlar:
            if (self.player_x + 28 > px and self.player_x < px + pw
                    and self.player_y + 44 >= py
                    and self.player_y + 44 <= py + 18
                    and self.player_dy >= 0):
                self.player_y = py - 44
                self.player_dy = 0
                self.player_grounded = True

        # Boru yanlarına çarpılır; yukarıdan inen oyuncu borunun üstünde durur.
        for px, top, pw, _height in self.pipes:
            overlaps_x = self.player_x + 28 > px and self.player_x < px + pw
            if not overlaps_x:
                continue
            if (self.player_dy >= 0 and previous_y + 44 <= top
                    and self.player_y + 44 >= top):
                self.player_y = top - 44
                self.player_dy = 0
                self.player_grounded = True
            elif self.player_y + 44 > top and self.player_y < 500:
                if previous_x + 30 <= px and self.player_x + 30 > px:
                    self.player_x = px - 30
                elif previous_x >= px + pw and self.player_x < px + pw:
                    self.player_x = px + pw

        # Düşman hareketi
        self.enemy_frame += 1
        for enemy in self.enemies:
            old_x, old_y = enemy["x"], enemy["y"]
            enemy_speed = 0.06 + (self.current_level - 1) * 0.018
            enemy["x"] += enemy["dx"] * (enemy["speed"] + enemy_speed)
            if enemy["x"] < enemy["min_x"] or enemy["x"] > enemy["max_x"]:
                enemy["dx"] *= -1
                enemy["x"] = max(enemy["min_x"], min(enemy["x"], enemy["max_x"]))
            if enemy["kind"] == "wisp":
                enemy["phase"] += 0.08
                enemy["y"] = enemy["base_y"] + math.sin(enemy["phase"]) * 13
            else:
                enemy["jump_timer"] -= 1
                if (self.current_level >= 3 and enemy["grounded"]
                        and enemy["jump_timer"] <= 0):
                    enemy["vertical_speed"] = -enemy["jump_power"]
                    enemy["grounded"] = False
                    enemy["jump_timer"] = random.randint(65, 130)

                # Düşmanlar kendi yerçekimleriyle düşer, arada zıplar ve
                # platforma ya da zemine inince yeni zıplayış için bekler.
                enemy["vertical_speed"] += enemy["gravity"]
                enemy["y"] += enemy["vertical_speed"]
                landed = False
                for px, py, pw, _ph in self.platformlar:
                    old_bottom = old_y + enemy["height"]
                    new_bottom = enemy["y"] + enemy["height"]
                    horizontal_overlap = (
                        enemy["x"] + enemy["width"] > px
                        and enemy["x"] < px + pw
                    )
                    if (horizontal_overlap and enemy["vertical_speed"] >= 0
                            and old_bottom <= py and new_bottom >= py):
                        enemy["y"] = py - enemy["height"]
                        enemy["vertical_speed"] = 0.0
                        landed = True
                        break
                if enemy["y"] + enemy["height"] >= 500:
                    enemy["y"] = 500 - enemy["height"]
                    enemy["vertical_speed"] = 0.0
                    landed = True
                enemy["grounded"] = landed
            self.game_canvas.move(
                enemy["tag"], (enemy["x"] - old_x) * self._world_scale,
                (enemy["y"] - old_y) * self._world_scale)
            if self.dikdortgen_cakisiyor(
                self.player_x, self.player_y, 30, 45,
                enemy["x"], enemy["y"], enemy["width"], enemy["height"],
            ):
                self.karakter_yakalandi()
                return

        # Altın toplama
        for coin in self.coins[:]:
            if self.dikdortgen_cakisiyor(
                self.player_x, self.player_y, 30, 45,
                coin["x"], coin["y"], 22, 30,
            ):
                self.game_canvas.delete(coin["tag"])
                self.coins.remove(coin)
                self.puan += 5
                self.game_canvas.itemconfig(
                    self.hud_puan, text=f"Puan: {self.puan} ⭐"
                )

        if self.player_x + 30 >= self.FINISH_X:
            self.bolum_tamamlandi(True)
            return

        # Kamera
        eski = self.camera_x
        ekran_px = self.player_x - self.camera_x
        if ekran_px > self.CAMERA_RIGHT:
            self.camera_x = self.player_x - self.CAMERA_RIGHT
        elif ekran_px < self.CAMERA_LEFT:
            self.camera_x = self.player_x - self.CAMERA_LEFT
        self.camera_x = max(0, min(self.camera_x, self.WORLD_WIDTH - 1000))

        fark = self.camera_x - eski
        if fark != 0:
            self.game_canvas.move("world", -fark * self._world_scale, 0)
            self.game_canvas.move("coin", -fark * self._world_scale, 0)

        self.oyuncu_ciz()
        self.game_loop_after = self.after(30, self.oyun_dongusu)

    # --------------------------------------------------- Karakter yakalandı --
    def karakter_yakalandi(self):
        self.music.pause()
        self.question_active = True
        self.player_dx = 0

        # Soru kutusu — başlangıç boyutu
        self.q_box_id = self.game_canvas.create_rectangle(
            200, 130, 800, 480,
            fill="#101820", outline="white", width=3, tags="q_box",
        )
        self.game_canvas.create_text(
            500, 175, text="YAKALANDIN!",
            font=("Arial", 28, "bold"), fill=RED, tags="q_box",
        )

        r_zorluk = random.choice(["Kolay", "Orta", "Zor"])
        soru_metni, self.rescue_ans = soru_uret(
            self.parent.oyun_ayarlari["sinif"], r_zorluk, kullan_bank=False
        )

        self.game_canvas.create_text(
            500, 220,
            text=f"MATEMATİK KURTARMA SORUSU\nZorluk: {r_zorluk}",
            font=("Arial", 14, "bold"), fill=TEXT_COLOR,
            justify="center", tags="q_box",
        )
        self.game_canvas.create_text(
            500, 290, text=soru_metni,
            font=("Arial", 20, "bold"), fill=TEXT_COLOR,
            width=540, tags="q_box",
        )

        self.entry_rescue = tk.Entry(
            self, font=("Arial", 18), justify="center",
            bg=CARD_LIGHT, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat",
        )
        self.entry_rescue.place(x=400, y=345, width=200, height=45)
        self.entry_rescue.focus_set()

        def kurtul_aksiyon():
            txt = self.entry_rescue.get().strip()
            try:
                val = float(txt.replace(",", "."))
            except ValueError:
                self.game_canvas.delete("q_err")
                self.game_canvas.create_text(
                    500, 445, text="Geçerli bir sayı girin!",
                    font=("Arial", 12, "bold"), fill=RED,
                    tags=("q_box", "q_err"),
                )
                return

            if math.isclose(val, float(self.rescue_ans),
                            rel_tol=1e-9, abs_tol=1e-9):
                self.dogru_sayisi += 1
                self.puan += 25
                self.game_canvas.itemconfig(
                    self.hud_puan, text=f"Puan: {self.puan} ⭐"
                )
                self.guvenli_widget_sil(self.entry_rescue)
                self.guvenli_widget_sil(btn_ok)
                self.guvenli_widget_sil(btn_hint)
                self._ai_hint_panel.hide()
                self.game_canvas.delete("q_box")
                self.game_canvas.delete("q_err")

                # Yakın düşmanları temizle
                yakin = [
                    e for e in self.enemies
                    if math.sqrt((e["x"] - self.player_x) ** 2
                                 + (e["y"] - self.player_y) ** 2) <= 250
                ]
                for e in yakin:
                    self.game_canvas.delete(e["tag"])
                    if e in self.enemies:
                        self.enemies.remove(e)

                self.question_active = False
                self.music.resume()
                self.game_canvas.focus_set()
                self.after(50, self.oyun_dongusu)
            else:
                self.yanlis_sayisi += 1
                self.guvenli_widget_sil(self.entry_rescue)
                self.guvenli_widget_sil(btn_ok)
                self.guvenli_widget_sil(btn_hint)
                self._ai_hint_panel.hide()
                self.game_canvas.delete("q_box")
                self.game_canvas.delete("q_err")
                self.game_canvas.create_text(
                    500, 300,
                    text=f"Yanlış Cevap!\nDoğru yanıt: {self.rescue_ans}",
                    font=("Arial", 24, "bold"), fill=RED,
                    justify="center", tags="over",
                )
                self.pending_result_after = self.after(
                    1500, lambda: self.bolum_tamamlandi(False)
                )

        def ai_ipucu_aksiyon():
            if self.q_box_id is not None:
                self.game_canvas.coords(self.q_box_id, 200, 130, 800, 640)
            self._ai_hint_panel.start(
                f"Matematik sorusu: '{soru_metni}'. Çözümü kısa adımlarla "
                "açıkla ve doğru cevabı en sonda net biçimde yaz."
            )

        btn_ok = tk.Button(
            self, text="KURTUL!", font=("Arial", 12, "bold"),
            bg=GREEN, fg=TEXT_COLOR, command=kurtul_aksiyon,
            relief="flat", cursor="hand2",
        )
        btn_ok.place(x=400, y=400, width=95, height=40)

        btn_hint = tk.Button(
            self, text="💡 AI İpucu", font=("Arial", 11, "bold"),
            bg=BLUE, fg=TEXT_COLOR, command=ai_ipucu_aksiyon,
            relief="flat", cursor="hand2",
        )
        btn_hint.place(x=505, y=400, width=95, height=40)
        self._ai_hint_panel = GameAIHint(
            self, btn_hint, background="#101820", placement="place")

        self.entry_rescue.bind("<Return>", lambda e: kurtul_aksiyon())

    def guvenli_widget_sil(self, widget):
        if widget and widget.winfo_exists():
            widget.destroy()

    # --------------------------------------------------- Bölüm tamamlandı --
    def bolum_tamamlandi(self, kazanma_durumu):
        if self.result_shown:
            return
        if getattr(self, "_ai_hint_panel", None):
            self._ai_hint_panel.hide()

        if kazanma_durumu:
            if self.current_level < self.max_levels:
                self.current_level += 1
                self.result_shown = False
                self.game_running = True
                self.question_active = False
                
                # Reset player and camera
                self.player_x = 120
                self.player_y = 445
                self.player_dx = 0
                self.player_dy = 0
                self.camera_x = 0
                
                # Re-setup world
                self.game_canvas.delete("world")
                self.game_canvas.delete("coin")
                self.enemies = []
                self.coins = []
                self.setup_world()
                # Yeni dünyanın arka planı sonradan çizildiği için HUD'ı
                # tekrar en üste al; puan ve seviye sabit ekranda kalır.
                self.game_canvas.tag_raise("hud")
                
                # Update level HUD
                self.game_canvas.itemconfig(
                    self.hud_seviye, text=f"Seviye: {self.current_level}/{self.max_levels}"
                )
                
                # Resume game loop
                self.game_loop_after = self.after(30, self.oyun_dongusu)
                return
            else:
                # Final victory
                pass
        
        # Original game over / final victory logic
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        if self.weather_after:
            try:
                self.after_cancel(self.weather_after)
            except tk.TclError:
                pass
            self.weather_after = None
        self.result_shown = True
        self.game_running = False
        self.question_active = False
        self.player_dx = 0
        oyun_kaydi_ekle(
            self.parent.active_student, "Euler'ün Macerası", self.puan,
            "kazandı" if kazanma_durumu else "kaybetti",
            {"seviye": self.current_level, "toplam_seviye": self.max_levels,
             "dogru": self.dogru_sayisi, "yanlis": self.yanlis_sayisi},
        )

        if self.pending_result_after is not None:
            try:
                self.after_cancel(self.pending_result_after)
            except Exception:
                pass
            self.pending_result_after = None

        if self.game_loop_after is not None:
            try:
                self.after_cancel(self.game_loop_after)
            except Exception:
                pass
            self.game_loop_after = None

        # Klavye bağlarını kaldır
        for key in ["<Left>", "<Right>", "<Up>", "<space>", "w", "W",
                    "a", "A", "d", "D",
                    "<KeyRelease-Left>", "<KeyRelease-Right>",
                    "<KeyRelease-a>", "<KeyRelease-d>",
                    "<KeyRelease-A>", "<KeyRelease-D>", "<Escape>"]:
            try:
                self.parent.unbind(key)
            except Exception:
                pass

        # Tüm child widget'ları temizle
        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        try:
            self.game_canvas.destroy()
        except Exception:
            pass

        self.configure(bg=BG_COLOR)

        if kazanma_durumu:
            baslik = "🏆 KAZANDIN!"
            alt_baslik = "Tebrikler! Bitiş çizgisine ulaştın."
            renk = GREEN_ACTIVE
            durum = "MACERAYI BAŞARIYLA TAMAMLADIN"
        else:
            baslik = "💥 OYUN BİTTİ!"
            alt_baslik = "Kurtarma sorusunu yanlış cevapladın."
            renk = RED
            durum = "MACERA SONA ERDİ"

        tk.Label(self, text=baslik, font=("Segoe UI", 42, "bold"),
                 fg=renk, bg=BG_COLOR).pack(pady=(75, 10))
        tk.Label(self, text=alt_baslik, font=("Segoe UI", 17, "bold"),
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(pady=(0, 25))

        card = tk.Frame(self, bg=CARD_COLOR, width=560, height=250,
                        highlightbackground=CARD_LIGHT, highlightthickness=2)
        card.pack()
        card.pack_propagate(False)

        tk.Label(card, text=durum, font=("Segoe UI", 16, "bold"),
                 fg=renk, bg=CARD_COLOR).pack(pady=(28, 12))

        info_text = (
            f"✓ Doğru Kurtarma: {self.dogru_sayisi}    "
            f"✗ Yanlış Kurtarma: {self.yanlis_sayisi}\n\n"
            f"⭐ TOPLAM PUAN: {self.puan}"
        )
        tk.Label(card, text=info_text, font=("Segoe UI", 15, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR,
                 justify="center").pack(expand=True)

        btn_box = tk.Frame(self, bg=BG_COLOR)
        btn_box.pack(pady=30)

        HoverButton(btn_box, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="Yeniden Oyna",
                    command=lambda: self.parent.show_frame(MarioSetupFrame),
                    width=18, height=2).pack(side="left", padx=10)
        HoverButton(btn_box, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="Ana Menü",
                    command=self._ana_menu,
                    width=18, height=2).pack(side="left", padx=10)

    def _ana_menu(self):
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)

    # ------------------------------------------------------------ Çıkış --
    def cikis_yap(self):
        if not self.result_shown:
            oyun_kaydi_ekle(
                self.parent.active_student, "Euler'ün Macerası", self.puan,
                "yarıda bırakıldı",
                {"seviye": self.current_level, "toplam_seviye": self.max_levels,
                 "dogru": self.dogru_sayisi, "yanlis": self.yanlis_sayisi},
            )
            self.result_shown = True
        if getattr(self, "_ai_hint_panel", None):
            self._ai_hint_panel.hide()
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        if self.weather_after:
            try:
                self.after_cancel(self.weather_after)
            except tk.TclError:
                pass
            self.weather_after = None
        self.game_running = False
        self.question_active = False

        if self.game_loop_after is not None:
            try:
                self.after_cancel(self.game_loop_after)
            except Exception:
                pass
            self.game_loop_after = None
        if self.pending_result_after is not None:
            try:
                self.after_cancel(self.pending_result_after)
            except Exception:
                pass
            self.pending_result_after = None

        if hasattr(self, "entry_rescue"):
            self.guvenli_widget_sil(self.entry_rescue)

        for key in ["<Left>", "<Right>", "<Up>", "<space>",
                    "w", "W", "a", "A", "d", "D",
                    "<KeyRelease-Left>", "<KeyRelease-Right>",
                    "<KeyRelease-a>", "<KeyRelease-d>",
                    "<KeyRelease-A>", "<KeyRelease-D>", "<Escape>"]:
            try:
                self.parent.unbind(key)
            except Exception:
                pass

        self._ana_menu()
