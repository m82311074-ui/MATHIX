"""MATHİX — Ramanujan'ın Yarışı.

Süre bazlı matematik hız oyunu. Combo sistemi + renk geçişli timer.
AI değerlendirme ekranı (canlı stream) içerir.
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
    ORANGE, ORANGE_ACTIVE,
    FONT_TITLE, FONT_SUBTITLE, FONT_HEADING, FONT_BODY,
)
from mathix.ui.widgets import HoverButton
from mathix.soru.uretici import soru_uret
from mathix.ai.ollama_client import ai_stream_chat
from mathix.oyun_kayıtları import oyun_kaydi_ekle


# ==============================================================================
# ⚡ RAMANUJAN'IN YARIŞI — KURULUM EKRANI
# ==============================================================================
class HizliIslemSetupFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        tk.Label(self, text="⚡ RAMANUJAN'IN YARIŞI",
                 font=("Segoe UI", 30, "bold"),
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(pady=(50, 6))
        tk.Label(self,
                 text="Süre dolmadan mümkün olduğunca çok soru çöz!",
                 font=FONT_SUBTITLE, fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(pady=(0, 22))

        card = tk.Frame(self, bg=CARD_COLOR,
                        highlightbackground=CARD_LIGHT, highlightthickness=1)
        card.pack(padx=140, pady=6, fill="x")

        self.var_sinif = tk.StringVar(value=f"{parent.active_student['sinif']}. Sınıf")
        self.var_zorluk = tk.StringVar(value="Orta")
        self.var_sure = tk.StringVar(value="60 saniye")

        def satir(parent_f, etiket, var, secenekler):
            r = tk.Frame(parent_f, bg=CARD_COLOR)
            r.pack(fill="x", padx=40, pady=13)
            tk.Label(r, text=etiket, font=FONT_BODY,
                     fg=TEXT_COLOR, bg=CARD_COLOR).pack(side="left")
            m = tk.OptionMenu(r, var, *secenekler)
            m.config(font=FONT_BODY, bg=CARD_LIGHT, fg=TEXT_COLOR,
                     bd=0, highlightthickness=0, width=15)
            m.pack(side="right")

        satir(card, "SINIF SEVİYESİ", self.var_sinif,
              ["Rastgele"] + [f"{i}. Sınıf" for i in range(1, 13)])
        satir(card, "SORU ZORLUĞU", self.var_zorluk,
              ["Rastgele", "Kolay", "Orta", "Zor"])
        satir(card, "SÜRE", self.var_sure,
              ["30 saniye", "60 saniye", "90 saniye", "120 saniye"])

        info = tk.Frame(self, bg=CARD_COLOR,
                        highlightbackground=ORANGE, highlightthickness=1)
        info.pack(padx=140, pady=12, fill="x")
        tk.Label(info,
                 text="🔥  3 seri doğru → 1.5×  |  5 seri doğru → 2×  |  8 seri doğru → 3× combo\n"
                      "✓  Her doğru = 10 puan × combo  |  ✗  Yanlış = combo sıfırlanır",
                 font=("Segoe UI", 10), fg=SECONDARY_TEXT, bg=CARD_COLOR,
                 justify="center").pack(pady=10)

        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=140, pady=24)
        HoverButton(btn_frame, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="← Geri", command=self._geri,
                    width=15).pack(side="left")
        HoverButton(btn_frame, bg_color=ORANGE, active_bg=ORANGE_ACTIVE,
                    text="BAŞLAT ➔", command=self.oyunu_baslat,
                    width=15).pack(side="right")

    def _geri(self):
        from mathix.menu.menu import GamesMenuFrame
        self.parent.show_frame(GamesMenuFrame)

    def oyunu_baslat(self):
        s = self.var_sinif.get()
        z = self.var_zorluk.get()
        t = self.var_sure.get()
        sinif = random.randint(1, 12) if s == "Rastgele" else int(s.split(".")[0])
        zorluk = random.choice(["Kolay", "Orta", "Zor"]) if z == "Rastgele" else z
        sure = int(t.split()[0])
        self.parent.oyun_ayarlari.update(
            {"sinif": sinif, "zorluk": zorluk, "sure": sure}
        )
        self.parent.show_frame(HizliIslemGameFrame)


# ==============================================================================
# ⚡ RAMANUJAN'IN YARIŞI — OYUN EKRANI
# ==============================================================================
class HizliIslemGameFrame(tk.Frame):
    COMBO_LEVELS = [
        (8, 3.0, "#FF00FF"),
        (5, 2.0, "#FF6600"),
        (3, 1.5, "#FFD700"),
        (0, 1.0, TEXT_COLOR),
    ]

    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.sinif = parent.oyun_ayarlari["sinif"]
        self.zorluk = parent.oyun_ayarlari["zorluk"]
        self.sure_toplam = parent.oyun_ayarlari.get("sure", 60)

        self.score = 0
        self.dogru = 0
        self.yanlis = 0
        self.streak = 0
        self.max_streak = 0
        self.combo_mult = 1.0
        self.toplam_q = 0

        self.sure_kalan = float(self.sure_toplam)
        self.running = False
        self.bitti = False
        self.after_id = None
        self.flash_id = None
        self.dogru_ans = None
        self.answer_locked = False

        self._build_ui()
        self._bind_keys()
        self._geri_sayim(3)
        self.protection = GameProtection(self, "Hızlı İşlem Yarışı",
                                         self._koruma_duraklat, self._koruma_devam,
                                         student_id=self.parent.active_student["id"])
        self.music = GameMusic("race")
        self.music.attach(self)

    def _koruma_duraklat(self):
        if hasattr(self, "music"):
            self.music.pause()
        self._koruma_onceki_durum = self.running
        self.running = False
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def _koruma_devam(self):
        if getattr(self, "_koruma_onceki_durum", False) and not self.bitti:
            self.running = True
            if self.answer_locked:
                self.music.resume()
            self._timer_tick()

    # ----------------------------------------------------------------- UI --
    def _build_ui(self):
        # ── Timer çubuğu ────────────────────────────────────────
        self.timer_canvas = tk.Canvas(self, height=14, bg=BG_COLOR,
                                       highlightthickness=0)
        self.timer_canvas.pack(fill="x")
        self.timer_bar = self.timer_canvas.create_rectangle(
            0, 0, 0, 14, fill="#00CC44", outline=""
        )
        self.timer_canvas.bind("<Configure>",
                                lambda e: self._redraw_timer())

        # ── Üst bilgi şeridi ────────────────────────────────────
        top = tk.Frame(self, bg=CARD_COLOR, height=64)
        top.pack(fill="x")
        top.pack_propagate(False)

        sure_frame = tk.Frame(top, bg=CARD_COLOR)
        sure_frame.pack(side="left", padx=20, pady=10)
        self.lbl_sure = tk.Label(
            sure_frame, text=f"⏱ {self.sure_toplam}s",
            font=("Segoe UI", 22, "bold"),
            fg=YELLOW, bg=CARD_COLOR,
        )
        self.lbl_sure.pack()


        combo_frame = tk.Frame(top, bg=CARD_COLOR)
        combo_frame.pack(side="left", padx=20, pady=10)
        self.lbl_combo = tk.Label(
            combo_frame, text="COMBO 1×",
            font=("Segoe UI", 15, "bold"),
            fg=TEXT_COLOR, bg=CARD_COLOR,
        )
        self.lbl_combo.pack()

        puan_frame = tk.Frame(top, bg=CARD_COLOR)
        puan_frame.pack(side="left", expand=True, pady=10)
        tk.Label(puan_frame, text="PUAN",
                 font=("Segoe UI", 9), fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).pack()
        self.lbl_score = tk.Label(
            puan_frame, text="0",
            font=("Segoe UI", 26, "bold"),
            fg=ORANGE, bg=CARD_COLOR,
        )
        self.lbl_score.pack()

        dy_frame = tk.Frame(top, bg=CARD_COLOR)
        dy_frame.pack(side="right", padx=20, pady=10)
        self.lbl_dogru = tk.Label(
            dy_frame, text="✓ 0",
            font=("Segoe UI", 15, "bold"),
            fg=GREEN_ACTIVE, bg=CARD_COLOR,
        )
        self.lbl_dogru.pack(anchor="e")
        self.lbl_yanlis = tk.Label(
            dy_frame, text="✗ 0",
            font=("Segoe UI", 15, "bold"),
            fg=RED, bg=CARD_COLOR,
        )
        self.lbl_yanlis.pack(anchor="e")

        tk.Label(top, text=f"{self.sinif}. Sınıf • {self.zorluk}",
                 font=("Segoe UI", 9), fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).pack(side="right", padx=10)

        # ── Orta alan ───────────────────────────────────────────
        mid = tk.Frame(self, bg=BG_COLOR)
        mid.pack(expand=True, fill="both")

        self.lbl_q_no = tk.Label(mid, text="",
                                  font=("Segoe UI", 11),
                                  fg=SECONDARY_TEXT, bg=BG_COLOR)
        self.lbl_q_no.pack(pady=(30, 0))

        # Soru akışındaki ilerlemeyi yarış pisti üzerinde göster.
        self.track = tk.Canvas(mid, width=520, height=64, bg=BG_COLOR,
                               highlightthickness=0)
        self.track.pack(pady=(4, 2))
        self.track.create_line(24, 42, 496, 42, fill="#38506C", width=14,
                               capstyle="round")
        self.track.create_line(24, 42, 496, 42, fill="#DCE7F2", width=2,
                               dash=(12, 10))
        self.track.create_oval(12, 30, 36, 54, fill="#45D483", outline="white",
                               width=2)
        self.track.create_oval(484, 30, 508, 54, fill="#FFB547", outline="white",
                               width=2)
        self.racer = self.track.create_polygon(0, 0, 0, 0, 0, 0,
                                               fill=ORANGE, outline="#FFE1A6",
                                               width=2)
        self.track.create_text(24, 12, text="START", fill=SECONDARY_TEXT,
                               font=("Segoe UI", 8, "bold"))
        self.track.create_text(496, 12, text="FINISH", fill=SECONDARY_TEXT,
                               font=("Segoe UI", 8, "bold"))

        self.flash_frame = tk.Frame(
            mid, bg=BG_COLOR,
            highlightthickness=4, highlightbackground=BG_COLOR,
        )
        self.flash_frame.pack(pady=10, ipadx=40, ipady=18)

        self.lbl_soru = tk.Label(
            self.flash_frame, text="",
            font=("Segoe UI", 40, "bold"),
            fg=TEXT_COLOR, bg=BG_COLOR,
            wraplength=800, justify="center",
        )
        self.lbl_soru.pack(padx=30, pady=8)

        self.lbl_feedback = tk.Label(
            mid, text="", font=("Segoe UI", 14, "bold"),
            fg=BG_COLOR, bg=BG_COLOR,
        )
        self.lbl_feedback.pack(pady=(0, 6))

        ans_row = tk.Frame(mid, bg=BG_COLOR)
        ans_row.pack(pady=14)

        self.entry = tk.Entry(
            ans_row, font=("Segoe UI", 24, "bold"),
            width=12, justify="center",
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat", disabledbackground=CARD_COLOR,
        )
        self.entry.pack(side="left", ipady=10, padx=(0, 12))
        self.entry.bind("<Return>", lambda e: self._cevapla())
        self.entry.bind("<Button-1>", lambda _e: self.entry.focus_set())

        self.btn_gonder = HoverButton(
            ans_row, bg_color=ORANGE, active_bg=ORANGE_ACTIVE,
            text="CEVAPLA", command=self._cevapla,
            width=12, height=2,
        )
        self.btn_gonder.pack(side="left")

        self.lbl_streak = tk.Label(
            self, text="", font=("Segoe UI", 12, "bold"),
            fg=SECONDARY_TEXT, bg=BG_COLOR,
        )
        self.lbl_streak.pack(pady=(0, 10))

        for widget in (self.flash_frame, self.lbl_soru, self.lbl_q_no,
                       self.lbl_feedback):
            widget.bind("<Button-1>", lambda _e: self.entry.focus_set())

    # ------------------------------------------------------- tuş bağları --
    def _bind_keys(self):
        self.parent.bind("<Escape>", lambda e: self._cikis())

    # ---------------------------------------------------------- geri sayım --
    def _geri_sayim(self, n):
        if getattr(getattr(self, "protection", None), "locked", False):
            self.after(250, lambda: self._geri_sayim(n))
            return
        if n <= 0:
            self.lbl_soru.config(text="")
            self.lbl_q_no.config(text="")
            self.running = True
            self._yeni_soru()
            self._timer_tick()
            self.entry.focus_set()
            return

        self.lbl_soru.config(
            text=str(n),
            font=("Segoe UI", 90, "bold"),
            fg=YELLOW,
        )
        self.lbl_q_no.config(text="Hazırlan…")
        self.lbl_feedback.config(text="", fg=BG_COLOR, bg=BG_COLOR)
        self.entry.config(state="disabled")
        self.after(800, lambda: self._geri_sayim(n - 1))

    # ---------------------------------------------------------------- timer --
    def _timer_tick(self):
        if not self.running or self.bitti:
            return
        self.sure_kalan -= 0.1
        if self.sure_kalan <= 0:
            self.sure_kalan = 0
            self._redraw_timer()
            self._oyun_bitti()
            return
        self._redraw_timer()
        self._update_hud()
        self.after_id = self.after(100, self._timer_tick)

    def _redraw_timer(self):
        w = self.timer_canvas.winfo_width() or 1000
        ratio = max(0.0, self.sure_kalan / self.sure_toplam)
        bar_w = int(w * ratio)

        if ratio > 0.5:
            t = (1 - ratio) * 2
            r = int(255 * t)
            g = 204
        elif ratio > 0.25:
            t = (0.5 - ratio) * 4
            r = 255
            g = int(204 * (1 - t))
        else:
            r, g = 255, 0
            if int(self.sure_kalan * 10) % 2 == 0:
                r, g = 200, 0

        bar_color = f"#{r:02X}{g:02X}00"
        self.timer_canvas.coords(self.timer_bar, 0, 0, bar_w, 14)
        self.timer_canvas.itemconfig(self.timer_bar, fill=bar_color)
        if hasattr(self, "track"):
            # Tur süresi azaldıkça araç bitiş çizgisine ilerler.
            progress = 1.0 - ratio
            x = 38 + progress * 438
            bob = 2 if int(self.sure_kalan * 5) % 2 else 0
            self.track.coords(self.racer, x-15, 26+bob, x+12, 26+bob,
                              x+18, 38+bob, x+5, 38+bob,
                              x+5, 48+bob, x-10, 48+bob,
                              x-10, 38+bob, x-18, 38+bob)

    def _update_hud(self):
        kalan = max(0, self.sure_kalan)
        self.lbl_sure.config(text=f"⏱ {kalan:.1f}s")

        if kalan > self.sure_toplam * 0.5:
            self.lbl_sure.config(fg=YELLOW)
        elif kalan > self.sure_toplam * 0.25:
            self.lbl_sure.config(fg=ORANGE)
        else:
            self.lbl_sure.config(fg=RED)

        self.lbl_score.config(text=str(self.score))
        self.lbl_dogru.config(text=f"✓ {self.dogru}")
        self.lbl_yanlis.config(text=f"✗ {self.yanlis}")

        mult_text, mult_col = "1×", TEXT_COLOR
        for min_s, mult, col in self.COMBO_LEVELS:
            if self.streak >= min_s:
                mult_text, mult_col = f"{mult}×", col
                break
        self.lbl_combo.config(text=f"COMBO {mult_text}", fg=mult_col)

        if self.streak >= 3:
            bar = "🔥" * min(self.streak, 10)
            self.lbl_streak.config(
                text=f"SERİ: {self.streak}  {bar}", fg=YELLOW
            )
        else:
            self.lbl_streak.config(text="")

    # --------------------------------------------------------- soru üretimi --
    def _yeni_soru(self):
        if self.bitti:
            return
        self.answer_locked = False
        self.music.pause()
        self.toplam_q += 1
        self.lbl_q_no.config(text=f"Soru #{self.toplam_q}")
        soru_metni, self.dogru_ans = soru_uret(
            self.sinif, self.zorluk, kullan_bank=False
        )

        uzunluk = len(soru_metni)
        if uzunluk <= 15:
            f = 44
        elif uzunluk <= 25:
            f = 36
        elif uzunluk <= 40:
            f = 28
        else:
            f = 22

        self.lbl_soru.config(text=soru_metni, fg=TEXT_COLOR,
                              font=("Segoe UI", f, "bold"))
        self.flash_frame.config(highlightbackground=BG_COLOR)
        self.lbl_feedback.config(text="", fg=BG_COLOR, bg=BG_COLOR)
        self.entry.config(state="normal")
        self.entry.delete(0, "end")
        self.entry.focus_set()

    # ---------------------------------------------------------- cevaplama --
    def _cevapla(self):
        if getattr(getattr(self, "protection", None), "locked", False):
            return
        if not self.running or self.bitti or self.answer_locked:
            return
        raw = self.entry.get().strip()
        if not raw:
            return
        self.answer_locked = True
        self.entry.config(state="disabled")
        self.lbl_soru.config(text="")
        self.music.resume()

        correct = False
        try:
            user_val = float(raw.replace(",", "."))
            ans_val = (float(self.dogru_ans)
                       if self.dogru_ans is not None else None)
            if ans_val is not None and math.isclose(
                user_val, ans_val, rel_tol=1e-6, abs_tol=1e-6
            ):
                correct = True
        except (ValueError, TypeError):
            pass

        if correct:
            self.streak += 1
            self.max_streak = max(self.max_streak, self.streak)
            for min_s, mult, _ in self.COMBO_LEVELS:
                if self.streak >= min_s:
                    self.combo_mult = mult
                    break
            pts = int(10 * self.combo_mult)
            self.score += pts
            self.dogru += 1
            self._flash(True, f"+{pts}  ✓ Doğru!")
        else:
            self.streak = 0
            self.combo_mult = 1.0
            self.yanlis += 1
            ans_str = (str(self.dogru_ans)
                       if self.dogru_ans is not None else "?")
            self._flash(False, f"✗ Yanlış!  Doğru: {ans_str}")

        self._update_hud()

    def _flash(self, dogru, mesaj):
        renk = GREEN_ACTIVE if dogru else RED
        self.flash_frame.config(highlightbackground=renk)
        self.lbl_feedback.config(text=mesaj, fg=renk, bg=BG_COLOR)

        if self.flash_id:
            try:
                self.after_cancel(self.flash_id)
            except Exception:
                pass
        self.flash_id = self.after(420, self._yeni_soru)

    # --------------------------------------------------------- oyun sonu --
    def _oyun_bitti(self):
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        if self.bitti:
            return
        self.bitti = True
        self.running = False
        toplam = self.dogru + self.yanlis
        oyun_kaydi_ekle(
            self.parent.active_student, "Ramanujan'ın Yarışı", self.score,
            "tamamlandı",
            {"dogru": self.dogru, "yanlis": self.yanlis,
             "isabet_yuzdesi": round(self.dogru / toplam * 100, 1) if toplam else 0,
             "cozulen_soru": self.toplam_q, "en_uzun_seri": self.max_streak,
             "sure_saniye": self.sure_toplam},
        )

        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
        if self.flash_id:
            try:
                self.after_cancel(self.flash_id)
            except Exception:
                pass
        try:
            self.parent.unbind("<Escape>")
        except Exception:
            pass

        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        self.configure(bg=BG_COLOR)

        # ---- Sonuç ----
        isabet = (self.dogru / toplam * 100) if toplam else 0
        derece, derece_renk = self._derece(isabet)

        tk.Label(self, text="⚡ SÜRE DOLDU!",
                 font=("Segoe UI", 36, "bold"),
                 fg=ORANGE, bg=BG_COLOR).pack(pady=(30, 4))
        tk.Label(self, text="Ramanujan'ın Yarışı bitti.",
                 font=("Segoe UI", 13),
                 fg=SECONDARY_TEXT, bg=BG_COLOR).pack()

        rozet = tk.Frame(self, bg=derece_renk, width=140, height=140)
        rozet.pack(pady=14)
        rozet.pack_propagate(False)
        tk.Label(rozet, text=derece,
                 font=("Segoe UI", 48, "bold"),
                 fg="white", bg=derece_renk).pack(expand=True)

        card = tk.Frame(self, bg=CARD_COLOR,
                        highlightbackground=ORANGE, highlightthickness=2)
        card.pack(padx=180, pady=8, fill="x")

        stats = [
            ("🏆 Toplam Puan", str(self.score), ORANGE),
            ("✓  Doğru", str(self.dogru), GREEN_ACTIVE),
            ("✗  Yanlış", str(self.yanlis), RED),
            ("🎯 İsabet", f"%{isabet:.1f}", YELLOW),
            ("🔥 Max Seri", str(self.max_streak), "#FF6600"),
            ("❓ Çözülen", str(self.toplam_q), TEXT_COLOR),
        ]
        grid = tk.Frame(card, bg=CARD_COLOR)
        grid.pack(pady=16, padx=20)
        for i, (lbl, val, col) in enumerate(stats):
            r, c = divmod(i, 3)
            tk.Label(grid, text=lbl, font=("Segoe UI", 10),
                     fg=SECONDARY_TEXT, bg=CARD_COLOR,
                     width=14, anchor="e").grid(
                         row=r * 2, column=c, padx=10, pady=(4, 0))
            tk.Label(grid, text=val,
                     font=("Segoe UI", 18, "bold"),
                     fg=col, bg=CARD_COLOR, width=8).grid(
                         row=r * 2 + 1, column=c, padx=10, pady=(0, 8))

        # ---- AI Değerlendirmesi Butonu ----
        HoverButton(
            self, bg_color="#6A1B9A", active_bg="#8E24AA",
            text="🤖 AI DEĞERLENDİRMESİ GÖR",
            command=self._ai_degerlendirme_ac,
            width=28, height=2,
        ).pack(pady=10)

        btn_box = tk.Frame(self, bg=BG_COLOR)
        btn_box.pack(pady=14)
        HoverButton(btn_box, bg_color=ORANGE, active_bg=ORANGE_ACTIVE,
                    text="Tekrar Oyna",
                    command=lambda: self.parent.show_frame(
                        HizliIslemSetupFrame
                    ),
                    width=15, height=2).pack(side="left", padx=10)
        HoverButton(btn_box, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="Ana Menü", command=self._ana_menu,
                    width=15, height=2).pack(side="left", padx=10)

    def _derece(self, isabet):
        if isabet >= 90:
            return "A+", "#00AA44"
        if isabet >= 80:
            return "A", "#00CC55"
        if isabet >= 70:
            return "B", "#4488FF"
        if isabet >= 60:
            return "C", "#BB8800"
        if isabet >= 50:
            return "D", ORANGE
        return "F", RED

    # ---------------------------------------------------------- çıkış --
    def _cikis(self):
        if not self.bitti:
            toplam = self.dogru + self.yanlis
            oyun_kaydi_ekle(
                self.parent.active_student, "Ramanujan'ın Yarışı", self.score,
                "yarıda bırakıldı",
                {"dogru": self.dogru, "yanlis": self.yanlis,
                 "isabet_yuzdesi": round(self.dogru / toplam * 100, 1) if toplam else 0,
                 "cozulen_soru": self.toplam_q, "en_uzun_seri": self.max_streak,
                 "sure_saniye": self.sure_toplam},
            )
            self.bitti = True
        if hasattr(self, "protection"):
            self.protection.stop()
        if hasattr(self, "music"):
            self.music.stop()
        self.bitti = True
        self.running = False
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
        if self.flash_id:
            try:
                self.after_cancel(self.flash_id)
            except Exception:
                pass
        try:
            self.parent.unbind("<Escape>")
        except Exception:
            pass
        self._ana_menu()

    def _ana_menu(self):
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)

    def _ai_degerlendirme_ac(self):
        self.parent.show_frame(
            AIYarisFrame,
            ozet={
                "sinif": self.sinif,
                "zorluk": self.zorluk,
                "sure": self.sure_toplam,
                "score": self.score,
                "dogru": self.dogru,
                "yanlis": self.yanlis,
                "toplam": self.toplam_q,
                "max_streak": self.max_streak,
            },
        )


# ==============================================================================
# ⚡ YARIŞ — AI DEĞERLENDİRME EKRANI (canlı stream)
# ==============================================================================
class AIYarisFrame(tk.Frame):
    """Ramanujan'ın Yarışı sonuçlarını AI'ya gönderir, kişisel öneri stream eder."""

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
            text="Ramanujan'ın Yarışı sonuçların analiz ediliyor...  (ESC = geri)",
            font=("Segoe UI", 11),
            fg=SECONDARY_TEXT, bg=BG_COLOR,
        ).pack(padx=24, anchor="w")

        # Özet kartı
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

        mini_istat("PUAN", self.ozet["score"], ORANGE)
        mini_istat("DOĞRU", self.ozet["dogru"], GREEN_ACTIVE)
        mini_istat("YANLIŞ", self.ozet["yanlis"], RED)
        mini_istat("MAX SERİ", self.ozet["max_streak"], YELLOW)
        mini_istat("SÜRE", f"{self.ozet['sure']}s", TEXT_COLOR)
        mini_istat("SEVİYE",
                   f"{self.ozet['sinif']}. sn / {self.ozet['zorluk']}",
                   SECONDARY_TEXT)

        # Metin alanı
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
                    "Bir öğrencinin 'Ramanujan'ın Yarışı' adlı süreli "
                    "matematik hız oyunundaki performansını analiz edip "
                    "kişiselleştirilmiş, sıcak ve motive edici bir geri "
                    "bildirim yazacaksın. Türkçe yaz. Başlıklar ve madde "
                    "işaretleri kullan. 180 kelimeyi geçme. Puanlama "
                    "bilgisi: her doğru 10 puan × combo çarpanı, yanlış "
                    "combo'yu sıfırlar. Doğru hızı (saniye başına soru) ve "
                    "seri (streak) önemlidir."
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
        toplam = o["toplam"] or 1
        isabet = o["dogru"] / toplam * 100
        soru_hizi = toplam / max(o["sure"], 1)

        return (
            f"Oyun: Ramanujan'ın Yarışı (süreli matematik hız testi)\n"
            f"Öğrenci: {o['sinif']}. sınıf  •  Zorluk: {o['zorluk']}\n"
            f"Toplam süre: {o['sure']} saniye\n"
            f"Çözülen soru: {o['toplam']}\n"
            f"Doğru: {o['dogru']}  |  Yanlış: {o['yanlis']}\n"
            f"İsabet: %{isabet:.1f}\n"
            f"Soru hızı: saniyede {soru_hizi:.2f} soru\n"
            f"En uzun doğru serisi: {o['max_streak']}\n"
            f"Toplam puan: {o['score']}\n\n"
            "Görev: Öğrenciye kişisel geri bildirim yaz:\n"
            "1) Kısa ve sıcak bir motivasyon cümlesi\n"
            "2) Hız ve doğruluk analizi (hangi yönü daha güçlü?)\n"
            "3) 2-3 somut geliştirme önerisi (zihinsel matematik, "
            "çarpım tablosu, işlem önceliği vb.)\n"
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
        self.parent.show_frame(HizliIslemSetupFrame)

    def _yeniden_baslat(self):
        if self.streaming:
            return
        self._analiz_baslat()
