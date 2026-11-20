"""MATHİX — Ortak Tkinter widget'ları."""
import tkinter as tk

from mathix.config import TEXT_COLOR, FONT_BTN


class HoverButton(tk.Button):
    """Üzerine gelince rengi değişen düğme.

    Orijinal `oyun-test.py` içindeki HoverButton ile aynı davranış.
    """

    def __init__(self, master, bg_color, active_bg, **kwargs):
        super().__init__(master, **kwargs)
        self.bg_color = bg_color
        self.active_bg = active_bg
        self.configure(
            bg=self.bg_color,
            activebackground=self.active_bg,
            fg=TEXT_COLOR,
            activeforeground=TEXT_COLOR,
            font=FONT_BTN,
            relief="flat",
            cursor="hand2",
            bd=0,
        )
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, _event):
        self["background"] = self.active_bg

    def on_leave(self, _event):
        self["background"] = self.bg_color