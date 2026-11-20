"""MATHİX — Ana menü ve oyun menüsü ekranları."""
import tkinter as tk
from tkinter import messagebox

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN, GREEN_ACTIVE, RED, YELLOW,
    PLAYER_DARK, FONT_TITLE, FONT_SUBTITLE, FONT_BODY,
    ORANGE, ORANGE_ACTIVE,
)
from mathix.ui.widgets import HoverButton


# ==============================================================================
# ANA MENÜ
# ==============================================================================
class MainMenuFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        left_frame = tk.Frame(self, bg=BG_COLOR, width=460)
        left_frame.pack(side="left", fill="y", padx=(40, 20), pady=32)
        left_frame.pack_propagate(False)
        self.left_frame = left_frame

        tk.Label(
            left_frame, text="MATHİX",
            font=("Segoe UI", 48, "bold"),
            fg=TEXT_COLOR, bg=BG_COLOR,
        ).pack(anchor="w")
        tk.Label(
            left_frame, text="Öğren. Çöz. Ustalaş.",
            font=("Segoe UI", 14, "italic"),
            fg=SECONDARY_TEXT, bg=BG_COLOR,
        ).pack(anchor="w", pady=(0, 20))
        student = parent.active_student
        tk.Label(
            left_frame, text=f"👤 {student['isim']}  •  {student['sinif']}. sınıf",
            font=("Segoe UI", 10, "bold"), fg=GREEN_ACTIVE, bg=BG_COLOR,
        ).pack(anchor="w", pady=(0, 10))

        HoverButton(
            left_frame, bg_color=BLUE, active_bg=BLUE_ACTIVE,
            text="MATEMATİK ALIŞTIRMALARI",
            command=self._git_ayarlar,
            height=2, width=28,
        ).pack(anchor="w", pady=6)

        HoverButton(
            left_frame, bg_color=GREEN, active_bg=GREEN_ACTIVE,
            text="🎮 OYUNLAR",
            command=self._git_oyunlar,
            height=2, width=28,
        ).pack(anchor="w", pady=6)

        HoverButton(
            left_frame, bg_color="#6A1B9A", active_bg="#8E24AA",
            text="🤖 AI ÖĞRETMEN",
            command=self._git_ai,
            height=2, width=28,
        ).pack(anchor="w", pady=6)

        HoverButton(
            left_frame, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
            text="NASIL OYNANIR?",
            command=self.show_info,
            height=2, width=28,
        ).pack(anchor="w", pady=6)

        HoverButton(
            left_frame, bg_color=RED, active_bg=PLAYER_DARK,
            text="OYUNDAN ÇIK",
            command=parent.quit,
            height=2, width=28,
        ).pack(anchor="w", pady=6)

        tk.Label(
            left_frame, text="MATHİX AI SÜRÜMÜ",
            font=("Arial", 9), fg=SECONDARY_TEXT, bg=BG_COLOR,
        ).pack(anchor="w", pady=(20, 0))

        self.draw_decorative_canvas()
        self.bind("<Configure>", self._resize_main_menu, add="+")
        self.after_idle(self._resize_main_menu)

    def _resize_main_menu(self, _event=None):
        """Keep the menu column and its visual balance tied to the window."""
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        left_width = min(620, max(380, int(width * 0.46)))
        side_pad = min(52, max(22, int(width * 0.04)))
        vertical_pad = min(48, max(20, int(height * 0.055)))
        self.left_frame.configure(width=left_width)
        self.left_frame.pack_configure(padx=(side_pad, max(14, side_pad // 2)),
                                       pady=vertical_pad)

    # ---- Navigasyon (lazy import) ----

    def _git_ayarlar(self):
        from mathix.alistirmalar.alistirmalar import SettingsFrame
        self.parent.show_frame(SettingsFrame)

    def _git_oyunlar(self):
        self.parent.show_frame(GamesMenuFrame)

    def _git_ai(self):
        from mathix.ai.ai_ogretmen import AIOgretmenFrame
        self.parent.show_frame(AIOgretmenFrame)

    # ---- Dekoratif canvas ----

    def draw_decorative_canvas(self):
        right_frame = tk.Frame(self, bg=BG_COLOR)
        right_frame.pack(side="right", fill="both", expand=True)
        self.decorative_canvas = tk.Canvas(
            right_frame, bg=BG_COLOR, highlightthickness=0,
        )
        self.decorative_canvas.pack(fill="both", expand=True)
        self.decorative_canvas.bind("<Configure>", self._draw_menu_art)

    def _draw_menu_art(self, event=None):
        canvas = self.decorative_canvas
        width = max(1, event.width if event else canvas.winfo_width())
        height = max(1, event.height if event else canvas.winfo_height())
        canvas.delete("menu_art")

        layout_scale = min(width / 560, height / 560)
        tk_scale = max(0.85, getattr(self.parent, "_current_ui_factor", 1.0))
        # main.py point fontlarını ayrıca ölçekliyor; resmi ikinci kez
        # büyütmemek için Canvas yazılarına bu katsayıyı dengeli uygula.
        scale = max(0.65, min(1.55, layout_scale / tk_scale))
        canvas.create_oval(width * .12, -height * .12,
                           width * .90, height * .58,
                           fill="#101826", outline="", tags="menu_art")
        canvas.create_oval(-width * .15, height * .48,
                           width * .48, height * 1.10,
                           fill="#101826", outline="", tags="menu_art")
        symbols = [
            ("∑", .22, .24, 56, SECONDARY_TEXT),
            ("∫", .66, .18, 63, BLUE_ACTIVE),
            ("π", .78, .48, 72, GREEN),
            ("∞", .30, .65, 77, RED),
            ("x²", .58, .80, 49, TEXT_COLOR),
            ("Δ", .48, .35, 42, YELLOW),
        ]
        for text, x_ratio, y_ratio, size, color in symbols:
            canvas.create_text(
                width * x_ratio, height * y_ratio, text=text,
                font=("Arial", max(20, int(size * scale)), "bold"),
                fill=color, tags="menu_art",
            )

    def show_info(self):
        messagebox.showinfo(
            "Nasıl Oynanır?",
            "📚  MATEMATİK ALIŞTIRMALARI\n"
            "Sınıf seviyesi, soru sayısı ve zorluğu seçerek sorular çöz.\n"
            "Klasik (kutulu) veya test (şıklı) modda pratik yap.\n\n"
            "🏃  EULER'ÜN MACERASI (Mario)\n"
            "← → veya A/D ile hareket et, ↑/W/SPACE ile zıpla.\n"
            "Düşmanlara üstten bas, bozuk para topla.\n"
            "Bir düşmana çarparsan matematik sorusu gelir;\n"
            "doğru cevaplayarsan kurtulursun, yanlışta oyun biter.\n\n"
            "🐍  FİBONACCİ'NİN YILANI\n"
            "← → ↑ ↓ veya WASD ile yılanı yönlendir.\n"
            "Elmaları yiyerek büyü ve puan kazan.\n"
            "Duvara çarparsan matematik sorusu gelir;\n"
            "doğru cevaplarsan yılan karşı duvardan çıkar,\n"
            "yanlış cevapta 1 can kaybedersin (3 canın var).\n"
            "SPACE ile oyunu duraklat.\n\n"
            "🤖  AI ÖĞRETMEN\n"
            "Takıldığın sorular için gerçek zamanlı yardım al."
        )


# ==============================================================================
# OYUNLAR MENÜSÜ
# ==============================================================================
class GamesMenuFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self._game_cards = []
        self._card_scale_job = None

        self.title_label = tk.Label(
            self, text="🎮 OYUNLAR",
            font=("Segoe UI", 26, "bold"),
            fg=TEXT_COLOR, bg=BG_COLOR,
        )
        self.title_label.pack(pady=(14, 2))

        self.subtitle_label = tk.Label(
            self, text="Matematiksel maceraya hangi dahiyle çıkmak istersin?",
            font=FONT_SUBTITLE, fg=SECONDARY_TEXT, bg=BG_COLOR,
        )
        self.subtitle_label.pack(pady=(0, 8))

        # ---- Üst sıra ----
        row1 = tk.Frame(self, bg=BG_COLOR)
        row1.pack(pady=(4, 6))

        self._kart(
            row1, BLUE, "🏃", "Euler'ün Macerası",
            "(Leonhard Euler, 1707–1783)",
            "Düşmanlara üstten bas, bozuk para\ntopla! Yakalanırsan soruyu çöz,\nyoksa oyun biter.",
            BLUE, BLUE_ACTIVE, self._git_mario,
        )
        self._kart(
            row1, GREEN, "🐍", "Fibonacci'nin Yılanı",
            "(Leonardo Fibonacci, 1170–1250)",
            "Yılanı yönlendir, elmaları ye!\nDuvara çarparsan soruyu çöz.\nAI ipucu alabilirsin. 3 can.",
            GREEN, GREEN_ACTIVE, self._git_yilan,
        )
        self._kart(
            row1, ORANGE, "⚡", "Ramanujan'ın Yarışı",
            "(Srinivasa Ramanujan, 1887–1920)",
            "Süre dolmadan çok soru çöz!\nSeri doğrular combo çarpar,\nen yüksek skoru kır.",
            ORANGE, ORANGE_ACTIVE, self._git_yaris,
        )

        # ---- Alt sıra (uzay, ortalı) ----
        row2 = tk.Frame(self, bg=BG_COLOR)
        row2.pack(pady=(0, 6))
        self._kart(
            row2, "#AA44FF", "🚀", "Newton'un İntikamı",
            "(Isaac Newton, 1643–1727)",
            "Uzay gemini yönlendir, düşman gemilerini\nimha et! Vurulursan soruyu çöz,\nAI ipucu alabilirsin.",
            "#7722CC", "#9933EE", self._git_uzay,
            cw=320, ch=228,
        )

        # ---- Geri ----
        btn_box = tk.Frame(self, bg=BG_COLOR)
        btn_box.pack(pady=4)
        HoverButton(
            btn_box, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
            text="← Ana Menü", command=self._git_ana_menu,
            width=18, height=1,
        ).pack()

        self.bind("<Configure>", self._resize_game_cards, add="+")
        self.after_idle(self._resize_game_cards)

    def _resize_game_cards(self, _event=None):
        """Scale game cards with available screen space without changing resolution."""
        if self._card_scale_job is not None:
            try:
                self.after_cancel(self._card_scale_job)
            except tk.TclError:
                pass
        try:
            # Let MathixApp apply its global Tk font scaling first.
            self._card_scale_job = self.after(180, self._apply_game_card_scale)
        except tk.TclError:
            self._card_scale_job = None

    def _apply_game_card_scale(self):
        self._card_scale_job = None
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        factor = max(0.85, min(1.55, min(width / 1000, height / 650)))
        for card, base_width, base_height, font_items in self._game_cards:
            card.configure(width=int(base_width * factor),
                           height=int(base_height * factor))
            card.pack_configure(padx=max(7, int(10 * factor)))
        self._apply_card_font_size()

    def _apply_card_font_size(self):
        """Keep game-card text at a fixed 11-point size in window mode."""
        size = 11
        for _card, _base_width, _base_height, font_items in self._game_cards:
            for widget, base_size, style in font_items:
                widget_size = base_size if base_size > 15 else size
                widget.configure(font=("Segoe UI", widget_size, *style))

    # ---- Kart yardımcı ----
    def _kart(self, parent_f, border_col, emoji, title, alt, desc,
              btn_col, btn_ac, cmd, cw=295, ch=228):
        f = tk.Frame(
            parent_f, bg=CARD_COLOR, width=cw, height=ch,
            highlightbackground=border_col, highlightthickness=2,
        )
        f.pack(side="left", padx=10)
        f.pack_propagate(False)
        font_items = []

        emoji_label = tk.Label(f, text=emoji, font=("Segoe UI", 32), bg=CARD_COLOR)
        emoji_label.pack(pady=(10, 0))
        font_items.append((emoji_label, 32, ()))
        title_label = tk.Label(f, text=title, font=("Segoe UI", 11, "bold"),
                               fg=TEXT_COLOR, bg=CARD_COLOR)
        title_label.pack(pady=(2, 0))
        font_items.append((title_label, 11, ("bold",)))
        alt_label = tk.Label(f, text=alt, font=("Segoe UI", 11, "italic"),
                             fg=SECONDARY_TEXT, bg=CARD_COLOR)
        alt_label.pack()
        font_items.append((alt_label, 11, ("italic",)))
        desc_label = tk.Label(f, text=desc, font=("Segoe UI", 11),
                              fg=SECONDARY_TEXT, bg=CARD_COLOR, justify="center")
        desc_label.pack(pady=3)
        font_items.append((desc_label, 11, ()))

        play_button = HoverButton(
            f, bg_color=btn_col, active_bg=btn_ac,
            text="OYNA ➔", command=cmd, width=13, height=1,
        )
        play_button.configure(font=("Segoe UI", 11, "bold"))
        play_button.pack(pady=(2, 0))
        font_items.append((play_button, 11, ("bold",)))
        self._game_cards.append((f, cw, ch, font_items))

    # ---- Navigasyon ----
    def _git_ana_menu(self):
        self.parent.show_frame(MainMenuFrame)

    def _git_mario(self):
        from mathix.oyunlar.mario import MarioSetupFrame
        self.parent.show_frame(MarioSetupFrame)

    def _git_yilan(self):
        from mathix.oyunlar.yilan import SnakeSetupFrame
        self.parent.show_frame(SnakeSetupFrame)

    def _git_yaris(self):
        from mathix.oyunlar.yaris import HizliIslemSetupFrame
        self.parent.show_frame(HizliIslemSetupFrame)

    def _git_uzay(self):
        from mathix.oyunlar.uzay_roketi import SpaceSetupFrame
        self.parent.show_frame(SpaceSetupFrame)
