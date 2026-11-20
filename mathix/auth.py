"""Student login screen for the MATHİX desktop app."""
import tkinter as tk

from mathix import database as db
from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, RED,
)
from mathix.ui.widgets import HoverButton


class LoginFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        card = tk.Frame(self, bg=CARD_COLOR, highlightbackground=CARD_LIGHT,
                        highlightthickness=1)
        card.place(relx=0.5, rely=0.48, anchor="center", width=430, height=440)

        tk.Label(card, text="MATHİX", font=("Segoe UI", 32, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(pady=(30, 2))
        tk.Label(card, text="Öğrenci hesabınla giriş yap",
                 font=("Segoe UI", 12), fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).pack(pady=(0, 22))

        form = tk.Frame(card, bg=CARD_COLOR)
        form.pack(fill="x", padx=42)
        tk.Label(form, text="İsim", font=("Segoe UI", 10, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(anchor="w")
        self.name_entry = tk.Entry(
            form, font=("Segoe UI", 13), bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat",
        )
        self.name_entry.pack(fill="x", ipady=9, pady=(5, 16))

        tk.Label(form, text="Şifre", font=("Segoe UI", 10, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(anchor="w")
        self.password_entry = tk.Entry(
            form, font=("Segoe UI", 13), show="●", bg=CARD_LIGHT,
            fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat",
        )
        self.password_entry.pack(fill="x", ipady=9, pady=(5, 8))
        self.error_label = tk.Label(form, text="", font=("Segoe UI", 9),
                                    fg=RED, bg=CARD_COLOR, wraplength=330)
        self.error_label.pack(anchor="w", pady=(0, 5))

        HoverButton(card, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="GİRİŞ YAP", command=self.login,
                    width=24, height=2).pack(pady=(8, 12))
        tk.Label(card, text="Hesabını öğretmen panelinden iste.",
                 font=("Segoe UI", 9), fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).pack()

        self.bind_all("<Return>", self._enter_key, add="+")
        self.name_entry.focus_set()

    def _enter_key(self, _event=None):
        self.login()
        return "break"

    def login(self):
        name = self.name_entry.get().strip()
        password = self.password_entry.get()
        if not name or not password:
            self.error_label.config(text="İsim ve şifre alanlarını doldur.")
            return
        student = db.ogrenci_giris(name, password)
        if not student:
            self.error_label.config(text="İsim veya şifre hatalı. Hesabın yoksa öğretmenine danış.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus_set()
            return

        self.parent.active_student = student
        self.parent.oyun_ayarlari["sinif"] = student["sinif"]
        self.unbind_all("<Return>")
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)
