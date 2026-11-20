"""MATHİX — Fibonacci'nin Yılanı.

Soru ekranı: Canvas üstüne gömülü Tkinter Frame → içerik ne kadar
uzun olursa olsun otomatik ölçeklenir, hiçbir yazı üst üste binmez.
"""
import math
import random
import tkinter as tk
from mathix.protection import GameProtection
from mathix.ui.music import GameMusic
from mathix.oyun_kayıtları import oyun_kaydi_ekle

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN, GREEN_ACTIVE, RED, YELLOW,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY,
    SN_BG, SN_GRID, SN_HEAD, SN_EYE,
    SN_FOOD_A, SN_FOOD_B, SN_WALL_GLOW, SN_PANEL,
)
from mathix.ui.widgets import HoverButton
from mathix.soru.uretici import soru_uret
from mathix.ui.game_ai_hint import GameAIHint


# ==============================================================================
# SABİTLER
# ==============================================================================
SNAKE_CELL = 25
SNAKE_COLS = 32
SNAKE_ROWS = 22
SNAKE_W = SNAKE_COLS * SNAKE_CELL   # 800
SNAKE_H = SNAKE_ROWS * SNAKE_CELL   # 550


# ==============================================================================
# YILAN — KURULUM EKRANI
# ==============================================================================
class SnakeSetupFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        tk.Label(self, text="🐍 FİBONACCİ'NİN YILANI",
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
        self.parent.show_frame(SnakeGameFrame)


# ==============================================================================
# YILAN — OYUN EKRANI
# ==============================================================================
class SnakeGameFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.sinif = parent.oyun_ayarlari["sinif"]
        self.zorluk = parent.oyun_ayarlari["zorluk"]

        # Oyun durumu
        self.snake = []
        self.direction = (1, 0)
        self.next_dir = (1, 0)
        self.food = None
        self.food_gold = False
        self.score = 0
        self.high_score = 0
        self.dogru_s = 0
        self.yanlis_s = 0
        self.lives = 3
        self.level = 1
        self.foods_eaten = 0

        self.running = True
        self.paused = False
        self.q_active = False
        self.result_shown = False
        self.after_id = None

        # Hız
        self.base_speed = {"Kolay": 200, "Orta": 140, "Zor": 90}[self.zorluk]
        self.speed = self.base_speed

        # Soru ekranı referansları
        self.q_frame = None
        self._aktif_soru = ""
        self.rescue_ans = None
        self._wall_nx = 0
        self._wall_ny = 0
        self.cell_size = SNAKE_CELL
        self.board_x = 0
        self.board_y = 0
        self.board_width = SNAKE_W
        self.board_height = SNAKE_H
        self._resize_job = None

        self._build_ui()
        self._build_touch_controls()
        self._new_game()
        self._bind_keys()
        self._tick()
        self.protection = GameProtection(self, "Yılan Oyunu",
                                         self._koruma_duraklat, self._koruma_devam,
                                         student_id=self.parent.active_student["id"])
        self.music = GameMusic("snake")
        self.music.attach(self)

    def _koruma_duraklat(self):
        if hasattr(self, "music"):
            self.music.pause()
        self._koruma_onceki_durum = self.running
        self.running = False

    def _koruma_devam(self):
        if getattr(self, "_koruma_onceki_durum", False) and not self.result_shown:
            if not self.q_active and not self.paused and hasattr(self, "music"):
                self.music.resume()
            self.running = True
            if not self.q_active:
                self._tick()

    # --------------------------------------------------------------- UI --
    def _build_ui(self):
        top = tk.Frame(self, bg=SN_PANEL, height=50)
        top.pack(fill="x")
        top.pack_propagate(False)

        self.lbl_score = tk.Label(top, text="PUAN: 0",
                                   font=("Segoe UI", 11, "bold"),
                                   fg=SN_HEAD, bg=SN_PANEL)
        self.lbl_score.pack(side="left", padx=18, pady=10)

        self.lbl_lives = tk.Label(top, text="❤ ❤ ❤",
                                   font=("Segoe UI", 11, "bold"),
                                   fg="#FF4444", bg=SN_PANEL)
        self.lbl_lives.pack(side="left", padx=10)

        self.lbl_level = tk.Label(top, text="SEVİYE 1",
                                   font=("Segoe UI", 11, "bold"),
                                   fg=YELLOW, bg=SN_PANEL)
        self.lbl_level.pack(side="left", padx=10)

        self.lbl_info = tk.Label(top, text="", font=("Segoe UI", 11),
                                  fg=SECONDARY_TEXT, bg=SN_PANEL)
        self.lbl_info.pack(side="left", padx=10)

        self.lbl_hi = tk.Label(top, text="EN YÜKSEK: 0",
                                font=("Segoe UI", 11),
                                fg=SECONDARY_TEXT, bg=SN_PANEL)
        self.lbl_hi.pack(side="right", padx=18)

        HoverButton(top, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="Ana Menü", command=self._quit,
                    width=10, height=1).pack(side="right", padx=8, pady=8)

        canvas_frame = tk.Frame(self, bg=BG_COLOR)
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas_frame = canvas_frame

        self.canvas = tk.Canvas(canvas_frame, width=SNAKE_W, height=SNAKE_H,
                                bg=SN_BG, highlightthickness=2,
                                highlightbackground="#1E3A5F")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._schedule_board_resize, add="+")
        self.canvas.bind("<Button-1>", lambda _e: self._show_touch_controls())

        bot = tk.Frame(self, bg=SN_PANEL, height=32)
        bot.pack(fill="x")
        bot.pack_propagate(False)
        tk.Label(bot,
                 text="← ↑ → ↓ / WASD  •  SPACE = Duraklat",
                 font=("Segoe UI", 11), fg=SECONDARY_TEXT,
                 bg=SN_PANEL).pack(pady=6)

    def _schedule_board_resize(self, event=None):
        if self.result_shown:
            return
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        try:
            self._resize_job = self.after(80, self._resize_board)
        except tk.TclError:
            self._resize_job = None

    def _resize_board(self, event=None):
        self._resize_job = None
        if self.result_shown or not self.canvas.winfo_exists():
            return
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width <= 1 or height <= 1:
            return
        cell = max(16, int(min(width / SNAKE_COLS, height / SNAKE_ROWS)))
        board_width, board_height = cell * SNAKE_COLS, cell * SNAKE_ROWS
        board_x, board_y = (width - board_width) // 2, (height - board_height) // 2
        if (cell, board_x, board_y) == (self.cell_size, self.board_x, self.board_y):
            return
        self.cell_size, self.board_x, self.board_y = cell, board_x, board_y
        self.board_width, self.board_height = board_width, board_height
        if hasattr(self, "snake") and self.snake:
            self._draw_grid()
            self._draw_frame()
            if self.paused:
                self._draw_pause_overlay()
            if self.q_active:
                self._draw_question_shade()

    def _board_center(self):
        return self.board_x + self.board_width // 2, self.board_y + self.board_height // 2

    def _draw_pause_overlay(self):
        cx, cy = self._board_center()
        self.canvas.delete("pause")
        self.canvas.create_text(cx, cy,
                                text="⏸ DURAKLADI\nDevam için üstteki düğmeye bas",
                                font=("Segoe UI", 11, "bold"),
                                fill=YELLOW, justify="center", tags="pause")

    def _draw_question_shade(self):
        self.canvas.delete("q_over")
        self.canvas.create_rectangle(
            self.board_x, self.board_y,
            self.board_x + self.board_width, self.board_y + self.board_height,
            fill="black", stipple="gray50", outline="", tags="q_over",
        )

    def _build_touch_controls(self):
        pad = tk.Frame(self, bg="#101E30", highlightbackground="#345477",
                       highlightthickness=2)
        self.touch_controls = pad
        # WASD yerleşimi, ok tuşu simgeleriyle gösterilir.
        keys = [
            (0, 1, (0, -1), "↑"),
            (1, 0, (-1, 0), "←"),
            (1, 1, (0, 1), "↓"),
            (1, 2, (1, 0), "→"),
        ]
        for row, column, direction, label in keys:
            tk.Button(
                pad, text=label, font=("Segoe UI", 22, "bold"),
                width=3, height=1, bg="#243A58", fg=TEXT_COLOR,
                activebackground="#3D5D82", activeforeground="white",
                relief="flat", cursor="hand2",
                command=lambda d=direction: self._set_touch_direction(d),
            ).grid(row=row, column=column, padx=4, pady=4)
        self._show_touch_controls()

    def _set_touch_direction(self, direction):
        if direction != (-self.direction[0], -self.direction[1]):
            self.next_dir = direction

    def _show_touch_controls(self):
        if hasattr(self, "touch_controls") and not self.result_shown:
            self.touch_controls.place(relx=0.5, rely=0.99, anchor="s")

    def _hide_touch_controls(self):
        if hasattr(self, "touch_controls"):
            self.touch_controls.place_forget()

    def _toggle_pause(self):
        if self.result_shown or self.q_active:
            return
        self.paused = not self.paused
        if self.paused:
            self.music.pause()
            self._draw_pause_overlay()
        else:
            self.canvas.delete("pause")
            self.music.resume()

    # -------------------------------------------------- oyun başlangıcı --
    def _new_game(self):
        cx, cy = SNAKE_COLS // 2, SNAKE_ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_dir = (1, 0)
        self._place_food()
        self._draw_grid()

    def _place_food(self):
        occupied = set(self.snake)
        while True:
            c = random.randint(1, SNAKE_COLS - 2)
            r = random.randint(1, SNAKE_ROWS - 2)
            if (c, r) not in occupied:
                self.food = (c, r)
                self.food_gold = random.random() < 0.20
                break

    # ------------------------------------------------------------ çizim --
    def _draw_grid(self):
        self.canvas.delete("all")
        # Hafif neon ışık noktaları ve seviye rengi oyun alanına derinlik verir.
        palette = [(SN_BG, SN_GRID), ("#071C25", "#123542"),
                   ("#10172B", "#27365A"), ("#21142A", "#49304D")]
        bg, grid = palette[(self.level - 1) % len(palette)]
        self.canvas.configure(bg=bg)
        for c in range(SNAKE_COLS):
            for r in range(SNAKE_ROWS):
                x1 = self.board_x + c * self.cell_size
                y1 = self.board_y + r * self.cell_size
                x2, y2 = x1 + self.cell_size, y1 + self.cell_size
                self.canvas.create_rectangle(x1, y1, x2, y2,
                                             fill=bg, outline=grid,
                                             width=1, tags="grid")
        for c, r in ((2, 2), (SNAKE_COLS - 3, 3), (4, SNAKE_ROWS - 3),
                     (SNAKE_COLS - 4, SNAKE_ROWS - 4)):
            x = self.board_x + c * self.cell_size + self.cell_size // 2
            y = self.board_y + r * self.cell_size + self.cell_size // 2
            radius = max(2, self.cell_size // 12)
            self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill="#315D70",
                                    outline="", tags="grid")

    def _draw_frame(self):
        self.canvas.delete("dyn")
        self._draw_food()
        self._draw_snake()
        self._draw_border()

    def _draw_food(self):
        c, r = self.food
        inset = max(2, self.cell_size // 12)
        x1 = self.board_x + c * self.cell_size + inset
        y1 = self.board_y + r * self.cell_size + inset
        x2 = self.board_x + (c + 1) * self.cell_size - inset
        y2 = self.board_y + (r + 1) * self.cell_size - inset
        col = SN_FOOD_B if self.food_gold else SN_FOOD_A
        glow = "#FFB700" if self.food_gold else "#FF0033"
        glow_size = max(2, self.cell_size // 12)
        self.canvas.create_oval(x1 - glow_size, y1 - glow_size,
                                x2 + glow_size, y2 + glow_size,
                                fill=glow, outline="", tags="dyn")
        self.canvas.create_oval(x1, y1, x2, y2,
                                fill=col, outline="white", width=1,
                                tags="dyn")
        if self.food_gold:
            mx = (x1 + x2) // 2
            my = (y1 + y2) // 2
            self.canvas.create_text(mx, my, text="★",
                                    font=("Arial", 11, "bold"),
                                    fill="white", tags="dyn")

    def _draw_snake(self):
        n = len(self.snake)
        for i, (c, r) in enumerate(self.snake):
            x1 = self.board_x + c * self.cell_size + 1
            y1 = self.board_y + r * self.cell_size + 1
            x2 = self.board_x + (c + 1) * self.cell_size - 1
            y2 = self.board_y + (r + 1) * self.cell_size - 1
            if i == 0:
                self.canvas.create_oval(x1, y1, x2, y2,
                                         fill=SN_HEAD, outline=SN_EYE,
                                         width=2, tags="dyn")
                dc, dr = self.direction
                eye_offset = max(3, self.cell_size // 6)
                eye_r = max(2, self.cell_size // 9)
                if dc == 1:    ex, ey = x2 - eye_offset, y1 + eye_offset
                elif dc == -1: ex, ey = x1 + eye_offset, y1 + eye_offset
                elif dr == -1: ex, ey = x2 - eye_offset, y1 + eye_offset
                else:           ex, ey = x2 - eye_offset, y2 - eye_offset
                self.canvas.create_oval(ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r,
                                        fill="white", outline="", tags="dyn")
                pupil_r = max(1, eye_r // 2)
                self.canvas.create_oval(ex - pupil_r, ey - pupil_r,
                                        ex + pupil_r, ey + pupil_r,
                                        fill="#10283A", outline="", tags="dyn")
            else:
                ratio = 1 - (i / n) * 0.45
                g = int(0xCC * ratio)
                b = int(0x66 * ratio)
                body_col = f"#00{g:02X}{b:02X}"
                margin = max(1, self.cell_size // 30) + min(i // 4, self.cell_size // 7)
                self.canvas.create_oval(x1 + margin, y1 + margin,
                                        x2 - margin, y2 - margin,
                                        fill=body_col, outline="#063E3C",
                                        width=1, tags="dyn")
                if i % 3 == 0:
                    detail = max(3, self.cell_size // 5)
                    self.canvas.create_arc(x1+detail, y1+detail, x2-detail, y2-detail,
                                           start=20, extent=140, style="arc",
                                           outline="#B5FFE3", width=1, tags="dyn")

    def _draw_border(self):
        self.canvas.create_rectangle(self.board_x, self.board_y,
                                     self.board_x + self.board_width,
                                     self.board_y + self.board_height,
                                     outline="#1E4070", width=3, tags="dyn")

    def _update_hud(self):
        self.lbl_score.config(text=f"PUAN: {self.score}")
        self.lbl_hi.config(text=f"EN YÜKSEK: {self.high_score}")
        self.lbl_level.config(text=f"SEVİYE {self.level}")
        hearts = "❤ " * self.lives + "🖤 " * (3 - self.lives)
        self.lbl_lives.config(text=hearts.strip())
        self.lbl_info.config(
            text=f"Sınıf: {self.sinif}  •  {self.zorluk}  •  "
                 f"✓{self.dogru_s}  ✗{self.yanlis_s}"
        )

    # ------------------------------------------------------- oyun döngüsü --
    def _tick(self):
        if not self.running or self.q_active or self.result_shown:
            return
        if self.paused:
            self.after_id = self.after(100, self._tick)
            return

        self.direction = self.next_dir
        hx, hy = self.snake[0]
        dc, dr = self.direction
        nx, ny = hx + dc, hy + dr

        if nx < 0 or nx >= SNAKE_COLS or ny < 0 or ny >= SNAKE_ROWS:
            self._wall_hit(nx, ny)
            return

        if (nx, ny) in self.snake[1:]:
            self._lose_life("Kendine çarptın!")
            return

        ate = (nx, ny) == self.food
        new_snake = [(nx, ny)] + self.snake
        if not ate:
            new_snake = new_snake[:-1]
        self.snake = new_snake

        if ate:
            pts = 20 if self.food_gold else 10
            pts += self.level * 2
            self.score += pts
            if self.score > self.high_score:
                self.high_score = self.score
            self.foods_eaten += 1
            if self.foods_eaten % 5 == 0:
                self.level += 1
                self.speed = max(60, self.speed - 15)
                self._draw_grid()
                self._flash_level_up()
            self._place_food()

        self._draw_frame()
        self._update_hud()
        self.after_id = self.after(self.speed, self._tick)

    def _flash_level_up(self):
        tag = "lvlup"
        self.canvas.delete(tag)
        cx, cy = self._board_center()
        self.canvas.create_text(cx, cy,
                                text=f"SEVİYE {self.level}! 🎉",
                                font=("Segoe UI", 11, "bold"),
                                fill=YELLOW, tags=tag)
        self.after(900, lambda: self.canvas.delete(tag))

    # ==================================================================
    # DUVAR ÇARPMASI → SORU EKRANI
    # ==================================================================
    def _wall_hit(self, nx, ny):
        self.music.pause()
        self.q_active = True
        self.running = False

        soru_metni, self.rescue_ans = soru_uret(
            self.sinif, self.zorluk, kullan_bank=False
        )
        self._aktif_soru = soru_metni

        # ---- Karartma ----
        self._draw_question_shade()

        # ---- Frame (canvas'ın ortasına gömülür) ----
        self.q_frame = tk.Frame(
            self, bg="#0D1B30",
            highlightbackground=SN_WALL_GLOW,
            highlightthickness=4,
        )

        # 1) Başlık
        tk.Label(
            self.q_frame,
            text="⚠ DUVARA ÇARPTIN! Soruyu çöz, devam et →",
            font=("Segoe UI", 11, "bold"),
            fg=SN_WALL_GLOW, bg="#0D1B30",
        ).pack(pady=(16, 8), padx=24)

        # 2) Soru metni — uzunluğa göre dinamik font
        tk.Label(
            self.q_frame, text=soru_metni,
            font=("Segoe UI", 11, "bold"),
            fg="white", bg="#0D1B30",
            wraplength=620, justify="center",
        ).pack(padx=30, pady=12)

        # 3) Giriş alanı + buton
        input_row = tk.Frame(self.q_frame, bg="#0D1B30")
        input_row.pack(pady=(6, 4))

        self._q_entry = tk.Entry(
            input_row, font=("Segoe UI", 11, "bold"),
            width=12, justify="center",
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat",
        )
        self._q_entry.pack(side="left", padx=(0, 10), ipady=6)
        self._q_entry.focus_set()
        self._q_entry.bind("<Return>", lambda e: self._check_answer())

        self._q_btn = tk.Button(
            input_row, text="CEVAPLA",
            font=("Segoe UI", 11, "bold"),
            bg=GREEN, fg="white", relief="flat", cursor="hand2",
            command=self._check_answer,
        )
        self._q_btn.pack(side="left", ipadx=12, ipady=4)

        # 4) AI İpucu butonu
        self._q_ai_btn = tk.Button(
            self.q_frame, text="💡 AI İpucu",
            font=("Segoe UI", 11, "bold"),
            bg=BLUE, fg="white", relief="flat", cursor="hand2",
            command=self._ai_ipucu,
        )
        self._q_ai_btn.pack(pady=(6, 8), ipadx=24, ipady=4)
        self._ai_hint_panel = GameAIHint(
            self.q_frame, self._q_ai_btn, background="#0D1B30")

        # Frame'i canvas'ın üstüne ortala
        self.q_frame.place(relx=0.5, rely=0.5, anchor="center")

        self._wall_nx = nx
        self._wall_ny = ny

    # ------------------------------------------------------------- AI İpucu --
    def _ai_ipucu(self):
        if not self.q_active:
            return
        self._ai_hint_panel.start(
            f"Matematik sorusu: '{self._aktif_soru}'. Çözümü kısa adımlarla "
            "açıkla ve doğru cevabı en sonda net biçimde yaz."
        )

    # ---------------------------------------------------------- Cevap kontrol --
    def _check_answer(self):
        if not self.q_active:
            return
        raw = self._q_entry.get().strip()
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

        # Temizle
        if getattr(self, "_ai_hint_panel", None):
            self._ai_hint_panel.hide()
        try:
            self.q_frame.destroy()
        except Exception:
            pass
        self.q_frame = None
        self.canvas.delete("q_over")
        self.q_active = False
        if hasattr(self, "music"):
            self.music.resume()

        if correct:
            self.dogru_s += 1
            self.score += 15
            nx, ny = self._wall_nx, self._wall_ny
            wnx = nx % SNAKE_COLS
            wny = ny % SNAKE_ROWS
            self.snake = [(wnx, wny)] + self.snake[:-1]
            self._show_banner("✓ DOĞRU! Devam et →", SN_HEAD, 900)
            self.running = True
            self.after(950, self._tick)
        else:
            self.yanlis_s += 1
            self._lose_life(f"Yanlış! Doğru cevap: {self.rescue_ans}")

    # --------------------------------------------------------------- Can kaybı --
    def _lose_life(self, mesaj):
        self.lives -= 1
        self._update_hud()
        if self.lives <= 0:
            self._game_over()
            return
        self._show_banner(f"💔 {mesaj}\n{self.lives} can kaldı!", RED, 1200)
        cx, cy = SNAKE_COLS // 2, SNAKE_ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_dir = (1, 0)
        self._draw_frame()
        self.running = True

        def _safe_tick():
            if not self.result_shown and self.running:
                self._tick()
        self.after_id = self.after(1300, _safe_tick)

    def _show_banner(self, text, color, ms):
        self.canvas.delete("banner")
        cx, cy = self._board_center()
        self.canvas.create_text(cx, cy,
                                text=text,
                                font=("Segoe UI", 11, "bold"),
                                fill=color, justify="center", tags="banner")
        self.after(ms, lambda: self.canvas.delete("banner"))

    # --------------------------------------------------------- oyun sonu --
    def _game_over(self):
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        if self.result_shown:
            return
        self.result_shown = True
        self.running = False
        oyun_kaydi_ekle(
            self.parent.active_student, "Fibonacci'nin Yılanı", self.score,
            "tamamlandı",
            {"seviye": self.level, "yenen_yem": self.foods_eaten,
             "dogru": self.dogru_s, "yanlis": self.yanlis_s,
             "en_yuksek_puan": self.high_score},
        )

        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError:
                pass
            self._resize_job = None

        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

        for k in ["<Left>", "<Right>", "<Up>", "<Down>",
                  "a", "A", "d", "D", "w", "W", "s", "S",
                  "<space>", "<Escape>"]:
            try:
                self.parent.unbind(k)
            except Exception:
                pass

        try:
            if self.q_frame:
                if getattr(self, "_ai_hint_panel", None):
                    self._ai_hint_panel.hide()
                self.q_frame.destroy()
        except Exception:
            pass

        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        self.configure(bg=BG_COLOR)
        content = tk.Frame(self, bg=BG_COLOR)
        content.pack(expand=True)
        display_scale = min(1.4, max(1.0, self.winfo_width() / 1000))

        tk.Label(content, text="🐍 OYUN BİTTİ!",
                 font=("Segoe UI", round(38 * display_scale), "bold"),
                 fg=RED, bg=BG_COLOR).pack(pady=(24, 8))
        tk.Label(content, text="Fibonacci'nin Yılanı sona erdi.",
                 font=("Segoe UI", round(14 * display_scale),),
                 fg=SECONDARY_TEXT, bg=BG_COLOR).pack()

        card = tk.Frame(content, bg=CARD_COLOR,
                        width=round(520 * display_scale),
                        height=round(240 * display_scale),
                        highlightbackground=CARD_LIGHT, highlightthickness=2)
        card.pack(pady=25)
        card.pack_propagate(False)

        tk.Label(card, text="SONUÇLAR",
                 font=("Segoe UI", round(15 * display_scale), "bold"),
                 fg=YELLOW, bg=CARD_COLOR).pack(pady=(22, 6))

        info = (f"⭐  Puan: {self.score}     🏆 En Yüksek: {self.high_score}\n"
                f"✓  Doğru: {self.dogru_s}       ✗ Yanlış: {self.yanlis_s}\n"
                f"📈 Seviye: {self.level}     🍎 Yenen: {self.foods_eaten}")
        tk.Label(card, text=info, font=("Segoe UI", round(13 * display_scale)),
                 fg=TEXT_COLOR, bg=CARD_COLOR,
                 justify="center").pack(expand=True)

        btn_box = tk.Frame(content, bg=BG_COLOR)
        btn_box.pack(pady=15)
        HoverButton(btn_box, bg_color=GREEN, active_bg=GREEN_ACTIVE,
                    text="Tekrar Oyna",
                    command=lambda: self.parent.show_frame(SnakeSetupFrame),
                    width=16, height=2).pack(side="left", padx=10)
        HoverButton(btn_box, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="Ana Menü", command=self._ana_menu,
                    width=16, height=2).pack(side="left", padx=10)

    def _ana_menu(self):
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)

    # ------------------------------------------------------ tuş bağları --
    def _bind_keys(self):
        dirs = {
            "<Left>": (-1, 0), "a": (-1, 0), "A": (-1, 0),
            "<Right>": (1, 0), "d": (1, 0), "D": (1, 0),
            "<Up>": (0, -1), "w": (0, -1), "W": (0, -1),
            "<Down>": (0, 1), "s": (0, 1), "S": (0, 1),
        }

        def set_dir(dc, dr):
            if (dc, dr) != (-self.direction[0], -self.direction[1]):
                self.next_dir = (dc, dr)
                self._hide_touch_controls()

        for key, (dc, dr) in dirs.items():
            self.parent.bind(key, lambda e, x=dc, y=dr: set_dir(x, y))

        self.parent.bind("<space>", lambda e: self._toggle_pause())
        self.parent.bind("<Escape>", lambda e: self._quit())

    def _quit(self):
        if not self.result_shown:
            oyun_kaydi_ekle(
                self.parent.active_student, "Fibonacci'nin Yılanı", self.score,
                "yarıda bırakıldı",
                {"seviye": self.level, "yenen_yem": self.foods_eaten,
                 "dogru": self.dogru_s, "yanlis": self.yanlis_s,
                 "en_yuksek_puan": self.high_score},
            )
            self.result_shown = True
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        self.running = False
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass

        try:
            if self.q_frame:
                self.q_frame.destroy()
        except Exception:
            pass

        for k in ["<Left>", "<Right>", "<Up>", "<Down>",
                  "a", "A", "d", "D", "w", "W", "s", "S",
                  "<space>", "<Escape>"]:
            try:
                self.parent.unbind(k)
            except Exception:
                pass
        self._ana_menu()
