"""MATHİX — Alıştırma modu: ayarlar, quiz motoru, sonuç ve AI öneri ekranları.

Akış:
  1) SettingsFrame → ayarlar
  2) QuizFrame → sorular (prosedürel anında, banka sorusu kaydedilir)
  3) ResultFrame → statik sonuçlar + "AI ÖNERİSİ GÖR" butonu
  4) AIOneriFrame → kişiselleştirilmiş canlı AI önerisi (stream)
"""
import math
import random
import threading
import time
import tkinter as tk
from mathix.protection import GameProtection

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN, GREEN_ACTIVE, RED, YELLOW,
    PLAYER_DARK,
    FONT_TITLE, FONT_SUBTITLE, FONT_HEADING, FONT_BODY, FONT_QUESTION,
)
from mathix.ui.widgets import HoverButton
from mathix.soru import uretici
from mathix.ai.ollama_client import ai_stream_chat
from mathix import database as db


# ==============================================================================
# EKRAN: ALIŞTIRMA AYARLARI
# ==============================================================================
class SettingsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent

        title_frame = tk.Frame(self, bg=BG_COLOR)
        title_frame.pack(fill="x", padx=60, pady=(40, 15))
        tk.Label(title_frame, text="Alıştırma Ayarları",
                 font=FONT_TITLE, fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w")
        tk.Label(title_frame,
                 text="Parametreleri özelleştirerek çözmeye başlayın.",
                 font=FONT_SUBTITLE, fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(anchor="w")

        card = tk.Frame(self, bg=CARD_COLOR, bd=1, relief="flat",
                        highlightbackground=CARD_LIGHT, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=60, pady=(0, 25))

        self.var_soru = tk.StringVar(value="10 Soru")
        self.var_sure = tk.StringVar(value="Sınırsız")
        self.var_zorluk = tk.StringVar(value="Orta")
        self.var_mod = tk.StringVar(value="Klasik (Kutulu)")

        student = parent.active_student
        tk.Label(card, text=f"Öğrenci: {student['isim']}   •   Sınıf: {student['sinif']}",
                 font=FONT_BODY, fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(
                     anchor="w", padx=40, pady=(18, 6))
        self._dropdown(card, "Soru Sayısı", self.var_soru,
                       ["5 Soru", "10 Soru", "15 Soru", "20 Soru",
                        "30 Soru", "50 Soru"])
        self._dropdown(card, "Zaman Sınırı", self.var_sure,
                       ["Sınırsız", "1 Dakika", "2 Dakika",
                        "5 Dakika", "10 Dakika"])
        self._dropdown(card, "Zorluk Derecesi", self.var_zorluk,
                       ["Kolay", "Orta", "Zor"])
        self._dropdown(card, "Cevaplama Modu", self.var_mod,
                       ["Klasik (Kutulu)", "Test Modu (Şıklı)"])

        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=60, pady=(0, 40))
        HoverButton(btn_frame, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="← GERİ DÖN", command=self._geri,
                    width=15, height=2).pack(side="left")
        HoverButton(btn_frame, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="BAŞLAT ➤", command=self.start_game,
                    width=20, height=2).pack(side="right")

    def _geri(self):
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)

    def _dropdown(self, parent, label, variable, options):
        row = tk.Frame(parent, bg=CARD_COLOR)
        row.pack(fill="x", padx=40, pady=10)
        tk.Label(row, text=label, font=FONT_BODY,
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(side="left")
        menu = tk.OptionMenu(row, variable, *options)
        menu.config(font=FONT_BODY, bg=CARD_LIGHT, fg=TEXT_COLOR,
                    activebackground=BLUE, activeforeground=TEXT_COLOR,
                    bd=0, highlightthickness=0, width=18, cursor="hand2")
        menu["menu"].config(bg=CARD_LIGHT, fg=TEXT_COLOR, font=FONT_BODY)
        menu.pack(side="right")

    def start_game(self):
        cls = self.parent.active_student["sinif"]
        s_sayisi = int(self.var_soru.get().split()[0])
        s_sure = 0
        if self.var_sure.get() != "Sınırsız":
            s_sure = int(self.var_sure.get().split()[0]) * 60
        mod = "Klasik" if "Klasik" in self.var_mod.get() else "Test"

        self.parent.oyun_ayarlari.update({
            "sinif": cls,
            "soru_sayisi": s_sayisi,
            "sure_limiti": s_sure,
            "zorluk": self.var_zorluk.get(),
            "mod": mod,
        })
        self.parent.show_frame(QuizFrame)


# ==============================================================================
# EKRAN: QUIZ MOTORU
# ==============================================================================
class QuizFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.ayarlar = parent.oyun_ayarlari
        self.mevcut_soru = 1
        self.puan = 0
        self.dogru_sayisi = 0
        self.yanlis_sayisi = 0
        self.kalan_sure = self.ayarlar["sure_limiti"]
        self.timer_id = None
        self.baslangic_zamani = time.time()
        self.tiklanabilir = True
        self.dogru_cevap = None
        self.soru_meta = {"bank": False}
        self.cevap_entry = None
        self.cevap_btn = None

        self.bekleyen_ai = []      # AI değerlendirmesi sona bırakılan banka soruları
        self.cevap_gecmisi = []    # Tüm cevaplar (AI analizi için)

        # DB
        db.init_db()
        self.ogrenci_id = parent.active_student["id"]
        self.oturum_id = db.oturum_baslat(
            self.ogrenci_id, "quiz",
            self.ayarlar["sinif"], self.ayarlar["zorluk"],
        )
        self.soru_baslangic = time.time()

        self.setup_ui()
        self.yeni_soru()
        self.protection = GameProtection(self, "Alıştırmalar",
                                         self._koruma_duraklat, self._koruma_devam,
                                         student_id=self.ogrenci_id)

    def _koruma_duraklat(self):
        self._koruma_tiklanabilir = self.tiklanabilir
        self.tiklanabilir = False
        if self.timer_id:
            try:
                self.after_cancel(self.timer_id)
            except tk.TclError:
                pass
            self.timer_id = None

    def _koruma_devam(self):
        self.tiklanabilir = getattr(self, "_koruma_tiklanabilir", True)
        if self.ayarlar["sure_limiti"] > 0 and self.kalan_sure > 0:
            self.timer_id = self.after(1000, self.update_global_timer)

    # --------------------------------------------------------------- UI --
    def setup_ui(self):
        top_bar = tk.Frame(self, bg=CARD_COLOR, height=60)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        self.lbl_soru_no = tk.Label(top_bar, text="", font=FONT_BODY,
                                     fg=SECONDARY_TEXT, bg=CARD_COLOR)
        self.lbl_soru_no.pack(side="left", padx=20, pady=15)

        self.lbl_puan = tk.Label(top_bar, text="Puan: 0",
                                  font=("Segoe UI", 14, "bold"),
                                  fg=GREEN_ACTIVE, bg=CARD_COLOR)
        self.lbl_puan.pack(side="right", padx=20, pady=15)

        self.lbl_sure = tk.Label(top_bar, text="",
                                  font=("Segoe UI", 14, "bold"),
                                  fg=TEXT_COLOR, bg=CARD_COLOR)
        if self.ayarlar["sure_limiti"] > 0:
            self.lbl_sure.pack(side="right", padx=20, pady=15)

        self.canvas_prog = tk.Canvas(self, bg=CARD_LIGHT, height=4,
                                      highlightthickness=0)
        self.canvas_prog.pack(fill="x")
        self.prog_rect = self.canvas_prog.create_rectangle(
            0, 0, 0, 4, fill=BLUE, outline=""
        )

        self.soru_frame = tk.Frame(self, bg=BG_COLOR)
        self.soru_frame.pack(fill="both", expand=True, pady=(30, 0))

        self.lbl_soru = tk.Label(self.soru_frame, text="",
                                  font=FONT_QUESTION, fg=TEXT_COLOR,
                                  bg=BG_COLOR, wraplength=850, justify="center")
        self.lbl_soru.pack(expand=True)

        self.interaktif_alan = tk.Frame(self, bg=BG_COLOR)
        self.interaktif_alan.pack(fill="both", expand=True,
                                   padx=80, pady=(0, 40))

        self.lbl_sonuc = tk.Label(self, text="", font=("Segoe UI", 14, "bold"),
                                   fg=TEXT_COLOR, bg=BG_COLOR)
        self.lbl_sonuc.pack(pady=5)

        footer = tk.Frame(self, bg=BG_COLOR)
        footer.pack(fill="x", padx=40, pady=(0, 20))
        HoverButton(footer, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="← Alıştırmalardan Çık",
                    command=self.guvenli_cikis, width=22).pack(side="left")

    # ----------------------------------------------------------- soru akışı --
    def yeni_soru(self):
        if self.mevcut_soru > self.ayarlar["soru_sayisi"]:
            self.oyunu_bitir()
            return

        self.tiklanabilir = True
        self.lbl_sonuc.config(text="")

        soru_metni, self.dogru_cevap = uretici.soru_uret(
            self.ayarlar["sinif"], self.ayarlar["zorluk"], kullan_bank=True
        )
        self.soru_meta = dict(uretici.SON_SORU_META)
        self.soru_baslangic = time.time()

        if self.soru_meta.get("bank"):
            no = self.soru_meta.get("no")
            kaynak = f" • Soru Bankası #{no}" if no is not None else " • Soru Bankası"
            self.lbl_soru_no.config(
                text=f"Soru: {self.mevcut_soru} / {self.ayarlar['soru_sayisi']}{kaynak}"
            )
        else:
            self.lbl_soru_no.config(
                text=f"Soru: {self.mevcut_soru} / {self.ayarlar['soru_sayisi']}"
            )
        self.lbl_soru.config(text=soru_metni)

        uzunluk = len(soru_metni)
        boyut = 36 if uzunluk <= 18 else (28 if uzunluk <= 28
                else (22 if uzunluk <= 48 else 16))
        self.lbl_soru.config(font=("Segoe UI", boyut, "bold"))

        width = 1000 * (self.mevcut_soru - 1) / self.ayarlar["soru_sayisi"]
        self.canvas_prog.coords(self.prog_rect, 0, 0, width, 4)
        for w in self.interaktif_alan.winfo_children():
            w.destroy()

        if self.soru_meta.get("bank"):
            self.setup_klasik_input(bank_modu=True)
        elif self.ayarlar["mod"] == "Klasik":
            self.setup_klasik_input()
        else:
            self.setup_test_input()

        if self.ayarlar["sure_limiti"] > 0 and self.timer_id is None:
            self.update_global_timer()

    def setup_klasik_input(self, bank_modu=False):
        box = tk.Frame(self.interaktif_alan, bg=BG_COLOR)
        box.pack(expand=True)

        self.cevap_entry = tk.Entry(
            box, font=("Arial", 18 if bank_modu else 20, "bold"),
            width=34 if bank_modu else 15, justify="center",
            bg=CARD_LIGHT, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat",
        )
        self.cevap_entry.pack(side="left", padx=10, ipady=8)
        self.cevap_entry.focus_set()
        self.cevap_entry.bind("<Return>",
                              lambda e: (self.cevabi_kontrol_et_klasik(), "break"))

        self.cevap_btn = HoverButton(
            box, bg_color=BLUE, active_bg=BLUE_ACTIVE,
            text="KAYDET" if bank_modu else "CEVAPLA",
            command=self.cevabi_kontrol_et_klasik,
            width=14 if bank_modu else 12, height=2,
        )
        self.cevap_btn.pack(side="left", padx=10)

        if bank_modu:
            tk.Label(self.interaktif_alan,
                     text="Bu soru sonuç ekranındaki AI önerisinde değerlendirilecek.",
                     font=("Segoe UI", 9), fg=SECONDARY_TEXT,
                     bg=BG_COLOR).pack(pady=(8, 0))

    def setup_test_input(self):
        self.interaktif_alan.columnconfigure(0, weight=1)
        self.interaktif_alan.columnconfigure(1, weight=1)

        ans = self.dogru_cevap
        secenekler = {ans}
        while len(secenekler) < 4:
            sahte = ans + (random.randint(1, 10) * random.choice([-1, 1]))
            if isinstance(ans, int):
                sahte = int(sahte)
            else:
                sahte = round(sahte, 3)
            if sahte >= 0:
                secenekler.add(sahte)

        secenekler = list(secenekler)
        random.shuffle(secenekler)

        self.btn_objeleri = []
        for idx, sec in enumerate(secenekler):
            row, col = divmod(idx, 2)
            btn = tk.Button(
                self.interaktif_alan, text=str(sec),
                font=("Segoe UI", 16, "bold"),
                bg=CARD_COLOR, fg=TEXT_COLOR,
                activebackground=CARD_LIGHT, activeforeground=TEXT_COLOR,
                relief="flat", cursor="hand2", bd=0,
                command=lambda v=sec, i=idx: self.cevabi_kontrol_et_test(v, i),
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=15, pady=10)
            self.btn_objeleri.append(btn)

    # ---------------------------------------------------------- DB kayıt --
    def _log(self, verilen, dogru, dogru_mu, kaynak):
        sure = round(time.time() - self.soru_baslangic, 2)
        try:
            db.cevap_kaydet(
                self.oturum_id, self.mevcut_soru,
                self.lbl_soru.cget("text"),
                verilen, dogru, dogru_mu, sure, kaynak,
            )
        except Exception:
            pass

        # AI analizi için hafızada tut
        self.cevap_gecmisi.append({
            "soru_no": self.mevcut_soru,
            "soru": self.lbl_soru.cget("text"),
            "verilen": str(verilen),
            "dogru": str(dogru),
            "dogru_mu": bool(dogru_mu),
            "kaynak": kaynak,   # "prosedurel", "test", "banka_bekliyor"
            "zorluk": self.ayarlar["zorluk"],
        })

    # ---------------------------------------------------- cevap kontrolleri --
    def cevabi_kontrol_et_klasik(self):
        if not self.tiklanabilir:
            return
        cevap = self.cevap_entry.get().strip() if self.cevap_entry else ""
        if not cevap:
            self.lbl_sonuc.config(text="Lütfen bir cevap girin!", fg=RED)
            return

        # Banka sorusu → AI öneri ekranına bırakılır
        if self.soru_meta.get("bank"):
            self._bank_sorusu_kaydet(cevap)
            return

        # Prosedürel soru → anında doğrula
        try:
            kullanici = float(cevap.replace(",", "."))
        except ValueError:
            self.lbl_sonuc.config(text="Lütfen geçerli bir sayı girin!", fg=RED)
            return

        self.tiklanabilir = False
        dogru_mu = math.isclose(kullanici, float(self.dogru_cevap),
                                 rel_tol=1e-9, abs_tol=1e-9)

        if dogru_mu:
            self.dogru_sayisi += 1
            self.puan += 10
            self.lbl_sonuc.config(text="✓ DOĞRU!", fg=GREEN_ACTIVE)
        else:
            self.yanlis_sayisi += 1
            self.lbl_sonuc.config(
                text=f"✗ Yanlış! Doğru cevap: {self.dogru_cevap}", fg=RED
            )

        self._log(cevap, self.dogru_cevap, dogru_mu, "prosedurel")
        self.lbl_puan.config(text=f"Puan: {self.puan}")
        self.mevcut_soru += 1
        self.after(700, self.yeni_soru)

    def _bank_sorusu_kaydet(self, cevap):
        """Banka sorusunu kaydet — AI değerlendirmesi sona bırakılır."""
        self.tiklanabilir = False

        self.bekleyen_ai.append({
            "soru_no": self.mevcut_soru,
            "soru": self.soru_meta.get("soru", self.lbl_soru.cget("text")),
            "cevap": cevap,
            "sinif": self.soru_meta.get("sinif", self.ayarlar["sinif"]),
        })

        self._log(cevap, "(AI öneri ekranında değerlendirilecek)", False,
                  "banka_bekliyor")

        self.lbl_sonuc.config(
            text="📝 Cevap kaydedildi — AI önerisinde değerlendirilecek",
            fg=YELLOW,
        )
        self.mevcut_soru += 1
        self.after(450, self.yeni_soru)

    def cevabi_kontrol_et_test(self, secilen_deger, btn_index):
        if not self.tiklanabilir:
            return
        self.tiklanabilir = False

        dogru_mu = math.isclose(float(secilen_deger), float(self.dogru_cevap),
                                 rel_tol=1e-9, abs_tol=1e-9)

        for idx, btn in enumerate(self.btn_objeleri):
            btn.config(cursor="arrow")
            if math.isclose(float(btn.cget("text")), float(self.dogru_cevap),
                            rel_tol=1e-9, abs_tol=1e-9):
                btn.config(bg=GREEN, activebackground=GREEN)
            if idx == btn_index and not dogru_mu:
                btn.config(bg=RED, activebackground=RED)

        if dogru_mu:
            self.dogru_sayisi += 1
            self.puan += 10
            self.lbl_sonuc.config(text="✓ DOĞRU!", fg=GREEN_ACTIVE)
        else:
            self.yanlis_sayisi += 1
            self.lbl_sonuc.config(text="✗ YANLIŞ!", fg=RED)

        self._log(str(secilen_deger), str(self.dogru_cevap), dogru_mu, "test")
        self.lbl_puan.config(text=f"Puan: {self.puan}")
        self.mevcut_soru += 1
        self.after(700, self.yeni_soru)

    # ------------------------------------------------------- zamanlayıcı --
    def update_global_timer(self):
        if self.kalan_sure > 0:
            mins, secs = divmod(self.kalan_sure, 60)
            self.lbl_sure.config(
                text=f"Kalan Süre: {mins:02d}:{secs:02d}",
                fg=TEXT_COLOR if self.kalan_sure > 15 else RED,
            )
            self.kalan_sure -= 1
            self.timer_id = self.after(1000, self.update_global_timer)
        else:
            self.lbl_sure.config(text="Süre Bitti!", fg=RED)
            self.oyunu_bitir()

    def guvenli_cikis(self):
        if hasattr(self, "protection"):
            self.protection.stop()
        if self.timer_id:
            self.after_cancel(self.timer_id)
        try:
            db.oturum_bitir(self.oturum_id, self.puan,
                            self.dogru_sayisi, self.yanlis_sayisi)
        except Exception:
            pass
        self.parent.show_frame(SettingsFrame)

    def oyunu_bitir(self):
        if hasattr(self, "protection"):
            self.protection.stop()
        if self.timer_id:
            self.after_cancel(self.timer_id)
        harcanan = int(time.time() - self.baslangic_zamani)

        try:
            db.oturum_bitir(self.oturum_id, self.puan,
                            self.dogru_sayisi, self.yanlis_sayisi)
        except Exception:
            pass

        sonuclar = {
            "puan": self.puan,
            "dogru": self.dogru_sayisi,
            "yanlis": self.yanlis_sayisi,
            "sure": harcanan,
            "cevap_gecmisi": list(self.cevap_gecmisi),
        }
        self.parent.show_frame(ResultFrame, sonuclar=sonuclar)


# ==============================================================================
# EKRAN: SONUÇ (statik)
# ==============================================================================
class ResultFrame(tk.Frame):
    def __init__(self, parent, sonuclar):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.sonuclar = sonuclar

        self._build_static()
        self._guncelle_ozet()

    def _build_static(self):
        tk.Label(self, text="Alıştırma Tamamlandı!",
                 font=FONT_TITLE, fg=TEXT_COLOR, bg=BG_COLOR).pack(pady=(40, 6))

        self.lbl_mesaj = tk.Label(self, text="", font=FONT_HEADING,
                                   fg=YELLOW, bg=BG_COLOR)
        self.lbl_mesaj.pack()

        self.stats = tk.Frame(self, bg=CARD_COLOR, bd=0,
                              highlightbackground=CARD_LIGHT, highlightthickness=2)
        self.stats.pack(pady=30, padx=100, fill="x")

        self.lbl_stat_puan = self._stat_row(self.stats, "Toplam Puan", YELLOW)
        self.lbl_stat_dogru = self._stat_row(self.stats, "Doğru Sayısı", GREEN_ACTIVE)
        self.lbl_stat_yanlis = self._stat_row(self.stats, "Yanlış Sayısı", RED)
        self.lbl_stat_sure = self._stat_row(self.stats, "Tamamlama Süresi", TEXT_COLOR)

        # ---- AI Önerisi Butonu (yanlış veya banka sorusu varsa) ----
        gecmis = self.sonuclar.get("cevap_gecmisi", [])
        oneri_gerekli = any(
            (not c["dogru_mu"]) or c.get("kaynak") == "banka_bekliyor"
            for c in gecmis
        )
        if oneri_gerekli:
            HoverButton(
                self,
                bg_color="#6A1B9A", active_bg="#8E24AA",
                text="🤖 AI ÖNERİSİ GÖR",
                command=self._ai_oneri_ac,
                width=24, height=2,
            ).pack(pady=14)
        else:
            tk.Label(
                self,
                text="🏆 Hiç yanlışın yok — AI önerisine gerek yok!",
                font=("Segoe UI", 12, "italic"),
                fg=GREEN_ACTIVE, bg=BG_COLOR,
            ).pack(pady=14)

        # Alt butonlar
        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=100, pady=10)
        HoverButton(btn_frame, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="ANA MENÜ", command=self._menu,
                    width=20, height=2).pack(side="left")
        HoverButton(btn_frame, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="TEKRAR ÇÖZ", command=self._tekrar,
                    width=20, height=2).pack(side="right")

    def _stat_row(self, p, lbl, col):
        r = tk.Frame(p, bg=CARD_COLOR)
        r.pack(fill="x", padx=40, pady=10)
        tk.Label(r, text=lbl, font=FONT_HEADING,
                 fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(side="left")
        val_lbl = tk.Label(r, text="0", font=("Segoe UI", 20, "bold"),
                            fg=col, bg=CARD_COLOR)
        val_lbl.pack(side="right")
        return val_lbl

    def _guncelle_ozet(self):
        dogru = self.sonuclar["dogru"]
        yanlis = self.sonuclar["yanlis"]
        puan = self.sonuclar["puan"]
        toplam = self.parent.oyun_ayarlari["soru_sayisi"]
        yuzde = (dogru / toplam * 100) if toplam else 0

        if yuzde == 100:
            msg, renk = "Kusursuz Performans! 🏆", GREEN_ACTIVE
        elif yuzde >= 80:
            msg, renk = "Harika İş Çıkardın! ⭐", BLUE_ACTIVE
        elif yuzde >= 50:
            msg, renk = "Fena Değil, Geliştirilebilir.", YELLOW
        else:
            msg, renk = "Daha Fazla Pratik Yapmalısın. 📚", RED

        self.lbl_mesaj.config(text=msg, fg=renk)
        self.lbl_stat_puan.config(text=str(puan))
        self.lbl_stat_dogru.config(text=str(dogru))
        self.lbl_stat_yanlis.config(text=str(yanlis))
        self.lbl_stat_sure.config(text=f"{self.sonuclar['sure']} sn")

    def _menu(self):
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)

    def _tekrar(self):
        self.parent.show_frame(QuizFrame)

    def _ai_oneri_ac(self):
        self.parent.show_frame(AIOneriFrame, sonuclar=self.sonuclar)


# ==============================================================================
# EKRAN: AI KİŞİSEL ÖNERİ (canlı stream)
# ==============================================================================
class AIOneriFrame(tk.Frame):
    """Yanlış cevapları AI'ya gönderir, kişisel öneri canlı stream eder."""

    def __init__(self, parent, sonuclar):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.sonuclar = sonuclar
        self.streaming = False
        self.stop_event = threading.Event()
        self.screen_alive = True
        self.tam_metin = ""

        self._build_ui()
        # ESC ile çıkış
        self.parent.bind("<Escape>", self._esc_handler)
        self.after(300, self._analiz_baslat)

    def _esc_handler(self, event=None):
        self._geri_sonuclar()

    # -------------------------------------------------------------- UI --
    def _build_ui(self):
        top = tk.Frame(self, bg=BG_COLOR, height=70)
        top.pack(fill="x", padx=24, pady=(18, 4))
        top.pack_propagate(False)

        tk.Label(
            top, text="🤖 AI KİŞİSEL ÖNERİ",
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
            text="Cevapların analiz ediliyor, sana özel öneriler hazırlanıyor...  (ESC = geri)",
            font=("Segoe UI", 11),
            fg=SECONDARY_TEXT, bg=BG_COLOR,
        ).pack(padx=24, anchor="w")

        outer = tk.Frame(self, bg=CARD_COLOR)
        outer.pack(fill="both", expand=True, padx=24, pady=(8, 12))

        self.text = tk.Text(
            outer,
            font=("Segoe UI", 16),
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat", wrap="word",
            padx=18, pady=14,
            spacing1=3, spacing3=3,
        )
        scroll = tk.Scrollbar(outer, orient="vertical",
                              command=self.text.yview,
                              bg=CARD_COLOR, troughcolor=CARD_COLOR,
                              relief="flat", width=10)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.config(state="disabled")

        bottom = tk.Frame(self, bg=BG_COLOR)
        bottom.pack(fill="x", padx=24, pady=(0, 18))

        HoverButton(
            bottom, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
            text="← Sonuçlara Dön",
            command=self._geri_sonuclar,
            width=16, height=1,
        ).pack(side="left")

        HoverButton(
            bottom, bg_color=BLUE, active_bg=BLUE_ACTIVE,
            text="↻ Yeniden Sor",
            command=self._yeniden_baslat,
            width=14, height=1,
        ).pack(side="left", padx=8)

        HoverButton(
            bottom, bg_color=RED, active_bg=PLAYER_DARK,
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
                    "Bir öğrencinin matematik quiz cevaplarını analiz edip "
                    "kişiselleştirilmiş, sıcak ve motive edici bir geri "
                    "bildirim yazacaksın. Türkçe yaz. Başlıklar ve madde "
                    "işaretleri kullan. 200 kelimeyi geçme. Eğer bazı "
                    "soruların doğru cevabı '(AI değerlendirecek)' olarak "
                    "işaretliyse, o soruların doğrusunu sen matematiksel "
                    "olarak hesapla ve öğrencinin cevabını ona göre değerlendir."
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
        gecmis = self.sonuclar.get("cevap_gecmisi", [])
        dogru = sum(1 for c in gecmis if c["dogru_mu"])
        yanlis = sum(1 for c in gecmis if not c["dogru_mu"])
        sinif = self.parent.oyun_ayarlari.get("sinif", "?")
        zorluk = self.parent.oyun_ayarlari.get("zorluk", "Orta")

        satirlar = [
            f"Öğrenci seviyesi: {sinif}. sınıf",
            f"Zorluk: {zorluk}",
            f"Sonuç: {dogru} doğru, {yanlis} yanlış",
            "",
            "TÜM SORULAR VE CEVAPLAR:",
        ]

        for c in gecmis:
            durum = "✓" if c["dogru_mu"] else "✗"
            satirlar.append(
                f"{durum} Soru {c['soru_no']}: {c['soru']}\n"
                f"   Öğrenci: {c['verilen']}\n"
                f"   Doğru: {c['dogru']}"
            )

        satirlar.append("")
        satirlar.append(
            "Görev: Öğrenciye kişisel geri bildirim yaz. Şunları içersin:\n"
            "1) Kısa bir motivasyon cümlesi\n"
            "2) Hangi konularda zorlandığının analizi\n"
            "3) 2-3 somut çalışma önerisi\n"
            "4) Son bir cesaretlendirme"
        )
        return "\n".join(satirlar)

    # ---------------------------------------------------- Navigasyon --
    def _geri_sonuclar(self):
        self.screen_alive = False
        self.stop_event.set()
        try:
            self.parent.unbind("<Escape>")
        except Exception:
            pass
        self.parent.show_frame(ResultFrame, sonuclar=self.sonuclar)

    def _yeniden_baslat(self):
        if self.streaming:
            return
        self._analiz_baslat()
