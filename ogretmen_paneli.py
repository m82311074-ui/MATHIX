"""MATHİX — Öğretmen Paneli.

Öğrenci ve sınıf bazlı istatistikleri görüntüler.
- Genel Bakış: sistem çapında özet + sınıf/zorluk/mod tabloları
- Öğrenciler: öğrenci seç → detaylı analiz + AI önerisi + Ekle/Düzenle/Sil
"""
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN, GREEN_ACTIVE, RED, YELLOW,
    PURPLE, PURPLE_ACT,
    FONT_TITLE, FONT_SUBTITLE, FONT_HEADING, FONT_BODY,
)
from mathix.ui.widgets import HoverButton
from mathix import database as db
from mathix.oyun_kayıtları.kayit import KAYIT_DIZINI
from mathix.ai.ollama_client import ai_stream_chat


PURPLE_BG = "#6A1B9A"
PURPLE_HOVER = "#8E24AA"
DELETE_RED = "#B71C1C"
DELETE_RED_HOVER = "#D32F2F"


# ==============================================================================
# ANA PANEL
# ==============================================================================
class OgretmenPaneli(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MATHİX — Öğretmen Paneli")
        self.geometry("1200x760")
        self.minsize(1100, 700)
        self.configure(bg=BG_COLOR)
        self.center_window(1200, 760)

        db.init_db()
        self._setup_styles()
        self._build_header()
        self._build_notebook()

    def center_window(self, width, height):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = int((sw / 2) - (width / 2))
        y = int((sh / 2) - (height / 2))
        self.geometry(f"{width}x{height}+{x}+{y-30}")

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TNotebook", background=BG_COLOR,
                        borderwidth=0, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background=CARD_COLOR,
                        foreground=TEXT_COLOR, padding=[15, 9],
                        font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BLUE), ("active", CARD_LIGHT)],
                  foreground=[("selected", "white")])

        style.configure("Treeview", background=CARD_COLOR,
                        foreground=TEXT_COLOR, fieldbackground=CARD_COLOR,
                        borderwidth=0, rowheight=28,
                        font=("Segoe UI", 10))
        style.map("Treeview",
                  background=[("selected", BLUE)],
                  foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background=CARD_LIGHT,
                        foreground=TEXT_COLOR, borderwidth=0,
                        font=("Segoe UI", 10, "bold"), padding=[8, 6])
        style.map("Treeview.Heading",
                  background=[("active", BLUE_ACTIVE)])

    def _build_header(self):
        header = tk.Frame(self, bg=CARD_COLOR, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=CARD_COLOR)
        title_box.pack(side="left", padx=24, pady=10)
        tk.Label(title_box, text="MATHİX  /  ÖĞRETMEN PANELİ",
                 font=("Segoe UI", 17, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(anchor="w")
        tk.Label(title_box, text="Öğrenci takibi ve öğrenme kayıtları",
                 font=("Segoe UI", 10), fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).pack(anchor="w", pady=(2, 0))

        HoverButton(header, bg_color=RED, active_bg="#9B111E",
                    text="Kapat", command=self.destroy,
                    width=10, height=1).pack(side="right", padx=16, pady=18)

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_genel = GenelBakisSekmesi(self.nb)
        self.tab_ogrenci = OgrencilerSekmesi(self.nb)
        self.tab_koruma = KorumaKayitlariSekmesi(self.nb)
        self.tab_oyun_kayitlari = OyunKayitlariSekmesi(self.nb)

        self.nb.add(self.tab_genel, text="Genel Bakış")
        self.nb.add(self.tab_ogrenci, text="Öğrenciler")
        self.nb.add(self.tab_oyun_kayitlari, text="Tüm Oyun Kayıtları")
        self.nb.add(self.tab_koruma, text="Tüm Koruma Kayıtları")

        # Sekme değişince verileri yenile
        self.nb.bind("<<NotebookTabChanged>>", self._tab_degisti)

    def _tab_degisti(self, event=None):
        secili = self.nb.index(self.nb.select())
        if secili == 0:
            self.tab_genel._yukle()
        elif secili == 1:
            self.tab_ogrenci._ogrencileri_yukle()
        elif secili == 2:
            self.tab_oyun_kayitlari.yenile()
        elif secili == 3:
            self.tab_koruma.yenile()


# ==============================================================================
# SEKME: KORUMA KAYITLARI
# ==============================================================================
class OyunKayitlariSekmesi(tk.Frame):
    """Öğrencilerin JSON dosyalarındaki tamamlanmış oyun oturumları."""
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        bar = tk.Frame(self, bg=BG_COLOR)
        bar.pack(fill="x", padx=18, pady=14)
        title_box = tk.Frame(bar, bg=BG_COLOR)
        title_box.pack(side="left")
        tk.Label(title_box, text="Oyun kayıtları", font=FONT_HEADING,
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w")
        tk.Label(title_box, text="Öğrencilerin tamamlanan veya yarım bıraktığı oturumlar",
                 font=("Segoe UI", 9), fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(anchor="w", pady=(2, 0))
        HoverButton(bar, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="Yenile", command=self.yenile, width=10).pack(side="right")

        columns = ("zaman", "ogrenci", "oyun", "puan", "sonuc")
        outer = tk.Frame(self, bg=BG_COLOR)
        outer.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self.table = ttk.Treeview(outer, columns=columns, show="headings")
        for col, title, width in (
            ("zaman", "Tarih / Saat", 165), ("ogrenci", "Öğrenci", 220),
            ("oyun", "Oyun", 270), ("puan", "Puan", 90),
            ("sonuc", "Sonuç", 150),
        ):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, anchor="w",
                              stretch=(col in ("ogrenci", "oyun")))
        yscroll = ttk.Scrollbar(outer, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=yscroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        details = tk.Frame(self, bg=CARD_COLOR,
                           highlightbackground=CARD_LIGHT, highlightthickness=1)
        details.pack(fill="x", padx=18, pady=(0, 16))
        tk.Label(details, text="Seçili kayıt ayrıntısı",
                 font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR,
                 bg=CARD_COLOR).pack(anchor="w", padx=12, pady=(8, 2))
        self.detail_label = tk.Label(details, text="Bir kayıt seçerek oyun istatistiklerini görün.",
                                     font=("Segoe UI", 10), fg=SECONDARY_TEXT,
                                     bg=CARD_COLOR, anchor="w", justify="left",
                                     wraplength=1050)
        self.detail_label.pack(fill="x", padx=12, pady=(0, 10))
        self._detaylar = {}
        self.table.bind("<<TreeviewSelect>>", self._secili_kaydi_goster)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        self.yenile()

    def yenile(self):
        self.table.delete(*self.table.get_children())
        self._detaylar = {}
        self.detail_label.config(text="Bir kayıt seçerek oyun istatistiklerini görün.")
        try:
            KAYIT_DIZINI.mkdir(parents=True, exist_ok=True)
            dosyalar = sorted(KAYIT_DIZINI.glob("ogrenci_*.json"))
        except OSError:
            dosyalar = []

        kayitlar = []
        for dosya in dosyalar:
            try:
                with dosya.open("r", encoding="utf-8") as f:
                    belge = json.load(f)
                if not isinstance(belge, dict):
                    continue
                ogrenci = str(belge.get("ogrenci_adi") or
                              f"Öğrenci {belge.get('ogrenci_id', '')}")
                for oyun in belge.get("oyunlar", []):
                    if not isinstance(oyun, dict):
                        continue
                    kayitlar.append((
                        str(oyun.get("zaman", "")).replace("T", " ")[:19],
                        ogrenci, str(oyun.get("oyun", "—")),
                        oyun.get("puan", "—"), str(oyun.get("sonuc", "—")),
                        oyun.get("ayrintilar", {}),
                    ))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue

        kayitlar.sort(key=lambda row: row[0], reverse=True)
        for zaman, ogrenci, oyun, puan, sonuc, ayrinti in kayitlar:
            iid = self.table.insert("", "end", values=(zaman, ogrenci, oyun, puan, sonuc))
            self._detaylar[iid] = ayrinti
        if not kayitlar:
            self.table.insert("", "end", values=(
                "—", "Henüz oyun kaydı yok", "—", "—", "—"))

    def _secili_kaydi_goster(self, _event=None):
        secim = self.table.selection()
        if not secim:
            return
        iid = secim[0]
        ayrinti = self._detaylar.get(iid, {})
        if isinstance(ayrinti, dict) and ayrinti:
            metin = "   •   ".join(
                f"{k.replace('_', ' ').capitalize()}: {v}"
                for k, v in ayrinti.items())
        else:
            metin = "Bu kayıtta ek istatistik bulunmuyor."
        self.detail_label.config(text=metin)


class KorumaKayitlariSekmesi(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        bar = tk.Frame(self, bg=BG_COLOR)
        bar.pack(fill="x", padx=18, pady=14)
        tk.Label(bar, text="Oyun sırasında algılanan koruma olayları",
                 font=FONT_HEADING, fg=TEXT_COLOR, bg=BG_COLOR).pack(side="left")
        HoverButton(bar, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="Yenile", command=self.yenile,
                    width=10).pack(side="right")
        HoverButton(bar, bg_color=RED, active_bg="#9B111E",
                    text="Kayıtları Temizle", command=self.kayitlari_temizle,
                    width=16).pack(side="right", padx=(0, 8))
        columns = ("ne_yapti", "oyun", "ogrenci")
        self.table = ttk.Treeview(self, columns=columns, show="headings")
        for col, title, width in (
            ("ne_yapti", "Ne yaptı", 360),
            ("oyun", "Hangi oyunda", 300),
            ("ogrenci", "Öğrenci ismi", 240),
        ):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, anchor="w")
        self.table.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self.yenile()

    def yenile(self):
        for item in self.table.get_children():
            self.table.delete(item)
        try:
            rows = db.koruma_kayitlari()
        except Exception:
            rows = []
        for row in rows:
            self.table.insert(
                "", "end",
                values=(f"{row['uygulama']} uygulaması açıldı",
                        row["oyun"], row["ogrenci_isim"]),
            )

    def kayitlari_temizle(self):
        if not messagebox.askyesno(
            "Koruma kayıtlarını temizle",
            "Tüm koruma kayıtları kalıcı olarak silinsin mi?",
            parent=self,
        ):
            return
        try:
            db.koruma_kayitlarini_temizle()
            self.yenile()
        except Exception as exc:
            messagebox.showerror("Hata", f"Kayıtlar temizlenemedi:\n{exc}", parent=self)


# SEKME 1: GENEL BAKIŞ
# ==============================================================================
class GenelBakisSekmesi(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self._build()
        self._yukle()

    def _build(self):
        baslik = tk.Frame(self, bg=BG_COLOR)
        baslik.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(baslik, text="Genel durum", font=FONT_HEADING,
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(side="left")
        HoverButton(baslik, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="Yenile", command=self._yukle, width=10).pack(side="right")

        self.kart_satiri = tk.Frame(self, bg=BG_COLOR)
        self.kart_satiri.pack(fill="x", pady=(8, 14), padx=8)

        self.kartlar = {}
        for key, lbl, renk in [
            ("ogrenci_sayisi", "👥 Öğrenci", BLUE_ACTIVE),
            ("oturum_sayisi", "📚 Oturum", GREEN_ACTIVE),
            ("cevap_sayisi", "✏️ Cevap", YELLOW),
            ("dogru_sayisi", "✓ Doğru", GREEN),
            ("ort_sure", "⏱ Ort. Süre", PURPLE),
        ]:
            f = tk.Frame(self.kart_satiri, bg=CARD_COLOR,
                         highlightbackground=CARD_LIGHT, highlightthickness=2)
            f.pack(side="left", padx=6, fill="x", expand=True)
            tk.Label(f, text=lbl, font=("Segoe UI", 10),
                     fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(pady=(14, 2))
            val_lbl = tk.Label(f, text="—", font=("Segoe UI", 22, "bold"),
                                fg=renk, bg=CARD_COLOR)
            val_lbl.pack(pady=(0, 14))
            self.kartlar[key] = val_lbl

        tablolar = tk.Frame(self, bg=BG_COLOR)
        tablolar.pack(fill="both", expand=True, padx=8)

        self.sinif_tree = self._tablo(
            tablolar, "Sınıf Bazlı Başarı",
            [("sinif", "Sınıf", 60), ("toplam", "Toplam", 80),
             ("dogru", "Doğru", 80), ("basari_yuzde", "Başarı %", 90)],
        )
        self.zorluk_tree = self._tablo(
            tablolar, "Zorluk Bazlı Başarı",
            [("zorluk", "Zorluk", 70), ("toplam", "Toplam", 70),
             ("basari_yuzde", "Başarı %", 80), ("ort_sure", "Ort. Sn", 80)],
        )
        self.mod_tree = self._tablo(
            tablolar, "Mod Bazlı Başarı",
            [("mod", "Mod", 90), ("toplam", "Toplam", 70),
             ("basari_yuzde", "Başarı %", 80)],
        )

    def _tablo(self, parent, baslik, kolonlar):
        outer = tk.Frame(parent, bg=CARD_COLOR,
                         highlightbackground=CARD_LIGHT, highlightthickness=1)
        outer.pack(side="left", padx=6, fill="both", expand=True)

        tk.Label(outer, text=baslik, font=("Segoe UI", 12, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(pady=10)

        cols = [k[0] for k in kolonlar]
        tree = ttk.Treeview(outer, columns=cols, show="headings",
                             height=8, style="Treeview")
        for k, lbl, w in kolonlar:
            tree.heading(k, text=lbl)
            tree.column(k, width=w, anchor="center")

        scroll = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)

        tree.pack(side="left", fill="both", expand=True,
                  padx=(6, 0), pady=(0, 8))
        scroll.pack(side="right", fill="y", pady=(0, 8), padx=(0, 6))
        return tree

    def _yukle(self):
        g = db.genel_istatistik()
        self.kartlar["ogrenci_sayisi"].config(text=str(g["ogrenci_sayisi"]))
        self.kartlar["oturum_sayisi"].config(text=str(g["oturum_sayisi"]))
        self.kartlar["cevap_sayisi"].config(text=str(g["cevap_sayisi"]))
        self.kartlar["dogru_sayisi"].config(text=str(g["dogru_sayisi"]))
        self.kartlar["ort_sure"].config(text=f"{g['ort_sure']:.1f} sn")

        for tree, data, cols in [
            (self.sinif_tree, db.sinif_bazli_basari(),
             ["sinif", "toplam", "dogru", "basari_yuzde"]),
            (self.zorluk_tree, db.zorluk_bazli_basari(),
             ["zorluk", "toplam", "basari_yuzde", "ort_sure"]),
            (self.mod_tree, db.mod_bazli_basari(),
             ["mod", "toplam", "basari_yuzde"]),
        ]:
            for item in tree.get_children():
                tree.delete(item)
            for row in data:
                vals = [row.get(c, "—") if row.get(c) is not None else "—"
                        for c in cols]
                tree.insert("", "end", values=vals)


# ==============================================================================
# SEKME 2: ÖĞRENCİLER
# ==============================================================================
class OgrencilerSekmesi(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.secilen_ogrenci_id = None
        self.ai_stream_aktif = False
        self.ai_stop_event = None
        self._ogrenci_kayitlari = {}
        self._build()
        self._ogrencileri_yukle()

    # -------------------------------------------------------------- UI --
    def _build(self):
        paned = tk.Frame(self, bg=BG_COLOR)
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        # SOL panel
        sol = tk.Frame(paned, bg=CARD_COLOR, width=340,
                       highlightbackground=CARD_LIGHT, highlightthickness=1)
        sol.pack(side="left", fill="y")
        sol.pack_propagate(False)

        tk.Label(sol, text="👥 ÖĞRENCİLER",
                 font=("Segoe UI", 12, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(pady=(14, 8))

        # ---- Aksiyon butonları ----
        aksiyon = tk.Frame(sol, bg=CARD_COLOR)
        aksiyon.pack(fill="x", padx=14, pady=(0, 10))

        HoverButton(aksiyon, bg_color=GREEN, active_bg=GREEN_ACTIVE,
                    text="➕ Ekle", command=self._ogrenci_ekle,
                    width=9, height=1).pack(side="left", padx=(0, 3))
        HoverButton(aksiyon, bg_color=BLUE, active_bg=BLUE_ACTIVE,
                    text="✏️ Düzenle", command=self._ogrenci_duzenle,
                    width=9, height=1).pack(side="left", padx=3)
        HoverButton(aksiyon, bg_color=DELETE_RED, active_bg=DELETE_RED_HOVER,
                    text="🗑️ Sil", command=self._ogrenci_sil,
                    width=9, height=1).pack(side="left", padx=(3, 0))

        # ---- Filtre ----
        filtre = tk.Frame(sol, bg=CARD_COLOR)
        filtre.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(filtre, text="Sınıf:", font=("Segoe UI", 10),
                 fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(side="left")

        self.sinif_var = tk.StringVar(value="Tümü")
        secenekler = ["Tümü"] + [f"{i}. Sınıf" for i in range(1, 13)]
        m = tk.OptionMenu(filtre, self.sinif_var, *secenekler,
                          command=lambda _: self._ogrencileri_yukle())
        m.config(font=("Segoe UI", 10), bg=CARD_LIGHT, fg=TEXT_COLOR,
                 bd=0, highlightthickness=0, width=10,
                 activebackground=BLUE)
        m["menu"].config(bg=CARD_LIGHT, fg=TEXT_COLOR)
        m.pack(side="right")

        # ---- Arama ----
        arama = tk.Frame(sol, bg=CARD_COLOR)
        arama.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(arama, text="🔍", font=("Segoe UI", 11),
                 fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(side="left")
        self.arama_var = tk.StringVar()
        self.arama_var.trace("w", lambda *a: self._ogrencileri_yukle())
        tk.Entry(arama, textvariable=self.arama_var,
                 font=("Segoe UI", 10),
                 bg=CARD_LIGHT, fg=TEXT_COLOR,
                 insertbackground=TEXT_COLOR, relief="flat").pack(
                     side="left", fill="x", expand=True, padx=(6, 0), ipady=4)

        # ---- Liste ----
        list_frame = tk.Frame(sol, bg=CARD_COLOR)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.ogrenci_tree = ttk.Treeview(
            list_frame, columns=("isim", "sinif", "hesap", "puan"),
            show="headings", style="Treeview",
        )
        self.ogrenci_tree.heading("isim", text="İsim")
        self.ogrenci_tree.heading("sinif", text="Sınıf")
        self.ogrenci_tree.heading("hesap", text="Giriş")
        self.ogrenci_tree.heading("puan", text="Puan")
        self.ogrenci_tree.column("isim", width=150, minwidth=110, anchor="w")
        self.ogrenci_tree.column("sinif", width=58, minwidth=52, anchor="center")
        self.ogrenci_tree.column("hesap", width=76, minwidth=70, anchor="center")
        self.ogrenci_tree.column("puan", width=66, minwidth=58, anchor="center")

        scroll = ttk.Scrollbar(list_frame, orient="vertical",
                                command=self.ogrenci_tree.yview)
        self.ogrenci_tree.configure(yscrollcommand=scroll.set)
        self.ogrenci_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.ogrenci_tree.bind("<<TreeviewSelect>>", self._ogrenci_secildi)
        self.ogrenci_tree.bind("<Double-1>",
                                lambda e: self._ogrenci_duzenle())

        # SAĞ panel
        self.sag = tk.Frame(paned, bg=BG_COLOR)
        self.sag.pack(side="right", fill="both", expand=True, padx=(12, 0))

        self._bos_ekran_goster()

    def _bos_ekran_goster(self):
        for w in self.sag.winfo_children():
            w.destroy()
        tk.Label(self.sag, text="👈  Soldan bir öğrenci seçin",
                 font=("Segoe UI", 14, "italic"),
                 fg=SECONDARY_TEXT, bg=BG_COLOR).pack(expand=True)

    # -------------------------------------------------------- liste yükleme --
    def _ogrencileri_yukle(self):
        for item in self.ogrenci_tree.get_children():
            self.ogrenci_tree.delete(item)

        secim = self.sinif_var.get()
        arama = self.arama_var.get().strip().lower()

        if secim == "Tümü":
            kayitlar = db.tum_ogrenciler()
        else:
            sinif = int(secim.split(".")[0])
            kayitlar = db.sinif_ogrencileri(sinif)

        self._ogrenci_kayitlari = {}
        for k in kayitlar:
            if arama and arama not in k["isim"].lower():
                continue
            iid = self.ogrenci_tree.insert(
                "", "end",
                values=(k["isim"], f"{k['sinif']}. sn",
                        "Hazır" if k.get("hesap_var") else "Kurulacak",
                        k.get("toplam_puan", 0)),
            )
            self._ogrenci_kayitlari[iid] = k["id"]

    def _ogrenci_secildi(self, event=None):
        secim = self.ogrenci_tree.selection()
        if not secim:
            return
        iid = secim[0]
        oid = self._ogrenci_kayitlari.get(iid)
        if oid is None:
            return
        self.secilen_ogrenci_id = oid
        self._detay_goster(oid)

    # ============================================================
    # ÖĞRENCİ EKLE
    # ============================================================
    def _ogrenci_ekle(self):
        dlg = OgrenciFormDialog(self, baslik="➕ Yeni Öğrenci Ekle")
        self.wait_window(dlg)
        if dlg.sonuc:
            isim, sinif, sifre = dlg.sonuc
            try:
                db.ogrenci_ekle(isim, sinif, sifre)
            except Exception as exc:
                messagebox.showerror("Hesap oluşturulamadı", str(exc), parent=self)
                return
            self._ogrencileri_yukle()
            messagebox.showinfo(
                "Başarılı",
                f"'{isim}' ({sinif}. sınıf) eklendi.",
                parent=self,
            )

    # ============================================================
    # ÖĞRENCİ DÜZENLE
    # ============================================================
    def _ogrenci_duzenle(self):
        if self.secilen_ogrenci_id is None:
            messagebox.showwarning(
                "Seçim Yok",
                "Lütfen önce bir öğrenci seçin.",
                parent=self,
            )
            return

        ozet = db.ogrenci_ozet(self.secilen_ogrenci_id)
        if not ozet:
            return

        dlg = OgrenciFormDialog(
            self,
            baslik="✏️ Öğrenciyi Düzenle",
            isim=ozet["isim"],
            sinif=ozet["sinif"],
            sifre_zorunlu=not bool(ozet.get("hesap_var")),
        )
        self.wait_window(dlg)
        if dlg.sonuc:
            yeni_isim, yeni_sinif, sifre = dlg.sonuc
            try:
                db.ogrenci_hesabi_guncelle(
                    self.secilen_ogrenci_id, yeni_isim, yeni_sinif, sifre or None)
            except Exception as exc:
                messagebox.showerror("Hesap güncellenemedi", str(exc), parent=self)
                return
            self._ogrencileri_yukle()
            self._detay_goster(self.secilen_ogrenci_id)
            messagebox.showinfo(
                "Başarılı",
                f"'{yeni_isim}' olarak güncellendi.",
                parent=self,
            )

    # ============================================================
    # ÖĞRENCİ SİL
    # ============================================================
    def _ogrenci_sil(self):
        if self.secilen_ogrenci_id is None:
            messagebox.showwarning(
                "Seçim Yok",
                "Lütfen önce bir öğrenci seçin.",
                parent=self,
            )
            return

        ozet = db.ogrenci_ozet(self.secilen_ogrenci_id)
        if not ozet:
            return

        ist = db.ogrenci_istatistik_topla(self.secilen_ogrenci_id)

        onay = messagebox.askyesno(
            "🗑️ Silme Onayı",
            f"'{ozet['isim']}' ({ozet['sinif']}. sınıf) silinsin mi?\n\n"
            f"Bu işlem GERİ ALINAMAZ!\n\n"
            f"Silinecek kayıtlar:\n"
            f"  • {ist['oturum']} oturum\n"
            f"  • {ist['cevap']} cevap\n\n"
            f"Emin misiniz?",
            icon="warning",
            parent=self,
        )
        if not onay:
            return

        db.ogrenci_sil(self.secilen_ogrenci_id)
        self.secilen_ogrenci_id = None
        self._bos_ekran_goster()
        self._ogrencileri_yukle()
        messagebox.showinfo(
            "Silindi",
            f"'{ozet['isim']}' ve tüm verileri silindi.",
            parent=self,
        )

    # ------------------------------------------------------------- detay --
    def _detay_goster(self, ogrenci_id):
        for w in self.sag.winfo_children():
            w.destroy()

        ozet = db.ogrenci_ozet(ogrenci_id)
        if not ozet:
            self._bos_ekran_goster()
            return

        # Başlık
        baslik = tk.Frame(self.sag, bg=CARD_COLOR, height=70)
        baslik.pack(fill="x")
        baslik.pack_propagate(False)

        tk.Label(baslik, text=f"👤 {ozet['isim']}",
                 font=("Segoe UI", 18, "bold"),
                 fg=TEXT_COLOR, bg=CARD_COLOR).pack(side="left",
                                                     padx=20, pady=16)
        tk.Label(baslik, text=f"{ozet['sinif']}. sınıf",
                 font=("Segoe UI", 11, "italic"),
                 fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(side="left", pady=22)

        # Özet kartları
        kart_satiri = tk.Frame(self.sag, bg=BG_COLOR)
        kart_satiri.pack(fill="x", pady=10)

        for lbl, val, renk in [
            ("OTURUM", ozet["oturum_sayisi"], BLUE_ACTIVE),
            ("SORU", ozet["cevap_sayisi"], YELLOW),
            ("DOĞRU", ozet["dogru"], GREEN_ACTIVE),
            ("YANLIŞ", ozet["yanlis"], RED),
            ("ORT. SÜRE", f"{ozet['ort_sure'] or 0:.1f} sn", PURPLE),
            ("PUAN", ozet["toplam_puan"], YELLOW),
        ]:
            f = tk.Frame(kart_satiri, bg=CARD_COLOR,
                         highlightbackground=CARD_LIGHT, highlightthickness=1)
            f.pack(side="left", padx=4, fill="x", expand=True)
            tk.Label(f, text=lbl, font=("Segoe UI", 8),
                     fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(pady=(8, 0))
            tk.Label(f, text=str(val), font=("Segoe UI", 15, "bold"),
                     fg=renk, bg=CARD_COLOR).pack(pady=(0, 8))

        # Alt notebook
        nb = ttk.Notebook(self.sag)
        nb.pack(fill="both", expand=True, pady=(10, 0))

        cevap_frame = tk.Frame(nb, bg=BG_COLOR)
        nb.add(cevap_frame, text="📝  Cevaplar")
        self._cevaplar_sekmesi(cevap_frame, ogrenci_id)

        zor_frame = tk.Frame(nb, bg=BG_COLOR)
        nb.add(zor_frame, text="⚠️  Zorlandığı Sorular")
        self._zor_sorular_sekmesi(zor_frame, ogrenci_id)

        koruma_frame = tk.Frame(nb, bg=BG_COLOR)
        nb.add(koruma_frame, text="🛡  Koruma Geçmişi")
        self._ogrenci_koruma_gecmisi(koruma_frame, ogrenci_id)

        oyun_frame = tk.Frame(nb, bg=BG_COLOR)
        nb.add(oyun_frame, text="🎮  Oyun Kayıtları")
        self._ogrenci_oyun_kayitlari(oyun_frame, ogrenci_id)

        ai_frame = tk.Frame(nb, bg=BG_COLOR)
        nb.add(ai_frame, text="🤖  AI Önerisi")
        self._ai_sekmesi(ai_frame, ogrenci_id, ozet)

    def _ogrenci_oyun_kayitlari(self, parent, ogrenci_id):
        """Seçili öğrencinin oyun bazında son ve en yüksek skorlarını göster."""
        columns = ("oyun", "son_skor", "rekor_skor")
        outer = tk.Frame(parent, bg=CARD_COLOR)
        outer.pack(fill="both", expand=True, padx=10, pady=10)
        table = ttk.Treeview(outer, columns=columns, show="headings")
        for col, title, width in (("oyun", "Oyun", 360),
                                  ("son_skor", "En Son Skor", 150),
                                  ("rekor_skor", "Rekor Skor", 150)):
            table.heading(col, text=title)
            table.column(col, width=width, anchor="w" if col == "oyun" else "center")
        scroll = ttk.Scrollbar(outer, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        dosya = KAYIT_DIZINI / f"ogrenci_{ogrenci_id}.json"
        try:
            with dosya.open("r", encoding="utf-8") as f:
                belge = json.load(f)
            oturumlar = belge.get("oyunlar", []) if isinstance(belge, dict) else []
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            oturumlar = []

        oyun_ozetleri = {}
        for oturum in oturumlar:
            if not isinstance(oturum, dict):
                continue
            oyun = str(oturum.get("oyun", "")).strip()
            try:
                puan = int(oturum.get("puan", 0))
            except (TypeError, ValueError):
                continue
            if not oyun:
                continue
            zaman = str(oturum.get("zaman", ""))
            ozet = oyun_ozetleri.setdefault(oyun, {
                "son_zaman": "", "son_skor": puan, "rekor": puan,
            })
            if zaman >= ozet["son_zaman"]:
                ozet["son_zaman"] = zaman
                ozet["son_skor"] = puan
            ozet["rekor"] = max(ozet["rekor"], puan)

        for oyun, ozet in sorted(oyun_ozetleri.items(), key=lambda item: item[0].casefold()):
            table.insert("", "end", values=(oyun, ozet["son_skor"], ozet["rekor"]))
        if not oyun_ozetleri:
            table.insert("", "end", values=("Henüz oyun kaydı yok", "—", "—"))

    def _ogrenci_koruma_gecmisi(self, parent, ogrenci_id):
        columns = ("zaman", "oyun", "uygulama")
        table = ttk.Treeview(parent, columns=columns, show="headings")
        for col, title, width in (("zaman", "Zaman", 180),
                                  ("oyun", "Oyun / Bölüm", 230),
                                  ("uygulama", "Algılanan uygulama", 300)):
            table.heading(col, text=title)
            table.column(col, width=width, anchor="w")
        table.pack(fill="both", expand=True, padx=8, pady=8)
        try:
            rows = db.ogrenci_koruma_kayitlari(ogrenci_id)
        except Exception:
            rows = []
        for row in rows:
            table.insert("", "end", values=(row["zaman"], row["oyun"], row["uygulama"]))
        if not rows:
            tk.Label(parent, text="Bu öğrenci için henüz koruma olayı kaydedilmedi.",
                     font=FONT_BODY, fg=SECONDARY_TEXT, bg=BG_COLOR).pack(pady=8)

    def _cevaplar_sekmesi(self, parent, ogrenci_id):
        cols = ("zaman", "mod", "zorluk", "soru",
                "verilen", "dogru_cevap", "durum")
        basliklar = [
            ("zaman", "Zaman", 130), ("mod", "Mod", 70),
            ("zorluk", "Zorluk", 70), ("soru", "Soru", 260),
            ("verilen", "Verdiği", 100), ("dogru_cevap", "Doğrusu", 100),
            ("durum", "Durum", 60),
        ]

        outer = tk.Frame(parent, bg=CARD_COLOR)
        outer.pack(fill="both", expand=True, padx=6, pady=6)

        tree = ttk.Treeview(outer, columns=cols, show="headings",
                             style="Treeview")
        for k, lbl, w in basliklar:
            tree.heading(k, text=lbl)
            tree.column(k, width=w,
                        anchor="center" if k != "soru" else "w")

        tree.tag_configure("dogru", foreground="#7FE8A0")
        tree.tag_configure("yanlis", foreground="#FF8B8B")

        scroll = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        kayitlar = db.ogrenci_cevaplari(ogrenci_id, limit=300)
        for r in kayitlar:
            zaman = (r["zaman"] or "").replace("T", " ")[:16]
            durum = "✓" if r["dogru_mu"] else "✗"
            tag = "dogru" if r["dogru_mu"] else "yanlis"
            tree.insert("", "end", values=(
                zaman, r["mod"], r["zorluk"], r["soru_metni"],
                r["verilen_cevap"], r["dogru_cevap"], durum,
            ), tags=(tag,))

        if not kayitlar:
            tk.Label(parent, text="Henüz cevap kaydı yok.",
                     font=("Segoe UI", 12, "italic"),
                     fg=SECONDARY_TEXT, bg=BG_COLOR).pack(pady=40)

    def _zor_sorular_sekmesi(self, parent, ogrenci_id):
        outer = tk.Frame(parent, bg=CARD_COLOR)
        outer.pack(fill="both", expand=True, padx=6, pady=6)

        tk.Label(outer, text="Bu öğrencinin en çok yanlış yaptığı sorular:",
                 font=("Segoe UI", 11, "italic"),
                 fg=SECONDARY_TEXT, bg=CARD_COLOR).pack(pady=(10, 6))

        cols = ("soru", "dogru_cevap", "tekrar")
        tree = ttk.Treeview(outer, columns=cols, show="headings",
                             style="Treeview")
        tree.heading("soru", text="Soru")
        tree.heading("dogru_cevap", text="Doğru Cevap")
        tree.heading("tekrar", text="Yanlış Sayısı")
        tree.column("soru", width=520, anchor="w")
        tree.column("dogru_cevap", width=120, anchor="center")
        tree.column("tekrar", width=120, anchor="center")

        scroll = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True,
                  padx=(6, 0), pady=(0, 6))
        scroll.pack(side="right", fill="y", pady=(0, 6), padx=(0, 6))

        kayitlar = db.ogrenci_zorlandigi_sorular(ogrenci_id, limit=30)
        for r in kayitlar:
            tree.insert("", "end", values=(
                r["soru_metni"], r["dogru_cevap"], r["tekrar"],
            ))

        if not kayitlar:
            tk.Label(parent, text="Bu öğrencinin hiç yanlışı yok. 🎉",
                     font=("Segoe UI", 12, "italic"),
                     fg=GREEN_ACTIVE, bg=BG_COLOR).pack(pady=20)

    def _ai_sekmesi(self, parent, ogrenci_id, ozet):
        top = tk.Frame(parent, bg=BG_COLOR)
        top.pack(fill="x", pady=10)

        HoverButton(top, bg_color=PURPLE_BG, active_bg=PURPLE_HOVER,
                    text="🤖  AI ÖNERİSİ ÜRET",
                    command=lambda: self._ai_oneri_uret(ogrenci_id, ozet),
                    width=24, height=2).pack(side="left", padx=10)

        self.ai_durum_lbl = tk.Label(top, text="",
                                      font=("Segoe UI", 10, "bold"),
                                      fg=SECONDARY_TEXT, bg=BG_COLOR)
        self.ai_durum_lbl.pack(side="left", padx=10)

        outer = tk.Frame(parent, bg=CARD_COLOR)
        outer.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.ai_text = tk.Text(
            outer, font=("Segoe UI", 11),
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat", wrap="word",
            padx=16, pady=12, spacing1=3, spacing3=3,
        )
        scroll = ttk.Scrollbar(outer, orient="vertical",
                                command=self.ai_text.yview)
        self.ai_text.configure(yscrollcommand=scroll.set)
        self.ai_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.ai_text.config(state="disabled")
        self.ai_text.insert(
            "end",
            "Bu öğrenci için kişiselleştirilmiş AI değerlendirmesi almak "
            "için yukarıdaki butona basın.\n\n"
            "AI, öğrencinin tüm cevap geçmişini analiz ederek:\n"
            "  • Güçlü ve zayıf yönlerini belirler\n"
            "  • Somut çalışma önerileri sunar\n"
            "  • Bir sonraki adım için hedef önerir",
        )
        self.ai_text.config(state="disabled")

    # ---------------------------------------------------------- AI öneri --
    def _ai_oneri_uret(self, ogrenci_id, ozet):
        if self.ai_stream_aktif:
            return

        cevaplar = db.ogrenci_cevaplari(ogrenci_id, limit=80)
        if not cevaplar:
            self.ai_durum_lbl.config(text="⚠ Veri yok", fg=RED)
            return

        dogru = sum(1 for c in cevaplar if c["dogru_mu"])
        yanlis = len(cevaplar) - dogru
        isabet = (dogru / len(cevaplar) * 100) if cevaplar else 0

        satirlar = [
            f"Öğrenci: {ozet['isim']}",
            f"Sınıf: {ozet['sinif']}. sınıf",
            f"Toplam cevap: {len(cevaplar)}",
            f"Doğru: {dogru}  |  Yanlış: {yanlis}  |  İsabet: %{isabet:.1f}",
            f"Ortalama cevap süresi: {ozet['ort_sure'] or 0:.2f} sn",
            "",
            "SON 30 CEVAP:",
        ]
        for c in cevaplar[:30]:
            durum = "✓" if c["dogru_mu"] else "✗"
            satirlar.append(
                f"{durum} [{c['zorluk']}] {c['soru_metni']} "
                f"→ Öğrenci: {c['verilen_cevap']} | Doğru: {c['dogru_cevap']}"
            )

        satirlar += [
            "",
            "Görev: Bu öğrenciye öğretmen gözüyle değil, ona doğrudan "
            "hitap eden sıcak bir kişisel geri bildirim yaz. İçersin:",
            "1) Kısa motivasyon cümlesi",
            "2) Güçlü olduğu konular",
            "3) Zayıf olduğu konular (somut örnekle)",
            "4) 3 somut çalışma önerisi",
            "5) Cesaretlendirici kapanış",
        ]

        mesajlar = [
            {
                "role": "system",
                "content": (
                    "Sen MATHİX eğitim platformunun AI Öğretmenisin. "
                    "Bir öğretmenin panelinde, öğretmene bir öğrenci "
                    "hakkında profesyonel pedagojik değerlendirme "
                    "yazıyorsun. Türkçe yaz. Başlıklar ve madde işaretleri "
                    "kullan. 200 kelimeyi geçme. Öğretmene 'şu öğrenci için "
                    "şunları yapabilirsiniz' tarzında somut öneriler ver."
                ),
            },
            {"role": "user", "content": "\n".join(satirlar)},
        ]

        self.ai_stream_aktif = True
        self.ai_stop_event = threading.Event()
        self.ai_durum_lbl.config(text="● AI yazıyor...", fg=BLUE_ACTIVE)

        self.ai_text.config(state="normal")
        self.ai_text.delete("1.0", "end")
        self.ai_text.config(state="disabled")

        def on_chunk(token):
            if not self.winfo_exists():
                return
            try:
                self.after(0, lambda: self._ai_ekle(token))
            except Exception:
                pass

        def on_done(_text, stopped):
            self.ai_stream_aktif = False
            try:
                if stopped:
                    self.after(0, lambda: self.ai_durum_lbl.config(
                        text="■ Durduruldu", fg=YELLOW))
                else:
                    self.after(0, lambda: self.ai_durum_lbl.config(
                        text="✓ Tamamlandı", fg=GREEN_ACTIVE))
            except Exception:
                pass

        def on_error(err):
            self.ai_stream_aktif = False
            try:
                self.after(0, lambda: self._ai_hata(err))
            except Exception:
                pass

        ai_stream_chat(
            "ogretmen:latest", mesajlar,
            on_chunk, on_done, on_error, self.ai_stop_event,
        )

    def _ai_ekle(self, token):
        if not self.ai_text.winfo_exists():
            return
        self.ai_text.config(state="normal")
        self.ai_text.insert("end", token)
        self.ai_text.see("end")
        self.ai_text.config(state="disabled")

    def _ai_hata(self, err):
        self.ai_durum_lbl.config(text="⚠ Ollama hatası", fg=RED)
        if not self.ai_text.winfo_exists():
            return
        self.ai_text.config(state="normal")
        self.ai_text.insert(
            "end",
            f"\n\n⚠️ AI'ya bağlanılamadı:\n{err}\n\n"
            "Ollama'nın çalıştığından ve 'ogretmen:latest' modelinin "
            "yüklü olduğundan emin ol.",
        )
        self.ai_text.config(state="disabled")


# ==============================================================================
# ÖĞRENCİ FORMU (Ekle / Düzenle için ortak dialog)
# ==============================================================================
class OgrenciFormDialog(tk.Toplevel):
    """Modal student account dialog — login name, password, and class."""

    def __init__(self, parent, baslik="Öğrenci", isim="", sinif=5,
                 sifre_zorunlu=True):
        super().__init__(parent)
        self.title(baslik)
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)
        self.sonuc = None
        self.sifre_zorunlu = sifre_zorunlu

        # Merkeze konumlandır
        self.update_idletasks()
        w, h = 400, 390
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Modal
        self.transient(parent)
        self.grab_set()

        # Başlık
        tk.Label(self, text=baslik,
                 font=("Segoe UI", 16, "bold"),
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(pady=(20, 16))

        # Form
        form = tk.Frame(self, bg=BG_COLOR)
        form.pack(fill="x", padx=30)

        # İsim
        tk.Label(form, text="Giriş adı / Öğrenci ismi:",
                 font=("Segoe UI", 11), fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(anchor="w")
        self.entry_isim = tk.Entry(
            form, font=("Segoe UI", 13),
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat",
        )
        self.entry_isim.pack(fill="x", pady=(4, 12), ipady=8)
        self.entry_isim.insert(0, isim)

        tk.Label(form, text="Şifre" if sifre_zorunlu else "Yeni şifre (değiştirmek için doldur):",
                 font=("Segoe UI", 11), fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(anchor="w")
        self.entry_sifre = tk.Entry(
            form, font=("Segoe UI", 13), show="●",
            bg=CARD_LIGHT, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat",
        )
        self.entry_sifre.pack(fill="x", pady=(4, 12), ipady=8)

        # Sınıf
        tk.Label(form, text="Sınıf:",
                 font=("Segoe UI", 11), fg=SECONDARY_TEXT,
                 bg=BG_COLOR).pack(anchor="w")
        self.var_sinif = tk.StringVar(value=f"{sinif}. Sınıf")
        m = tk.OptionMenu(form, self.var_sinif,
                          *[f"{i}. Sınıf" for i in range(1, 13)])
        m.config(font=("Segoe UI", 12), bg=CARD_LIGHT, fg=TEXT_COLOR,
                 bd=0, highlightthickness=0, anchor="w", width=15)
        m["menu"].config(bg=CARD_LIGHT, fg=TEXT_COLOR,
                         font=("Segoe UI", 11))
        m.pack(fill="x", pady=(4, 14))

        # Butonlar
        btn_row = tk.Frame(self, bg=BG_COLOR)
        btn_row.pack(fill="x", padx=30, pady=(0, 20))

        HoverButton(btn_row, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                    text="İptal", command=self._iptal,
                    width=10, height=1).pack(side="left")
        HoverButton(btn_row, bg_color=GREEN, active_bg=GREEN_ACTIVE,
                    text="Kaydet", command=self._kaydet,
                    width=10, height=1).pack(side="right")

        # Enter → kaydet
        self.bind("<Return>", lambda e: self._kaydet())
        self.bind("<Escape>", lambda e: self._iptal())

        self.entry_isim.focus_set()
        self.entry_isim.select_range(0, "end")

    def _kaydet(self):
        isim = self.entry_isim.get().strip()
        sifre = self.entry_sifre.get()
        if not isim:
            messagebox.showwarning(
                "Eksik Bilgi",
                "Lütfen bir isim girin.",
                parent=self,
            )
            return

        if len(isim) > 60:
            messagebox.showwarning(
                "Çok Uzun",
                "İsim 60 karakterden uzun olamaz.",
                parent=self,
            )
            return

        if self.sifre_zorunlu and len(sifre) < 6:
            messagebox.showwarning(
                "Şifre gerekli", "Şifre en az 6 karakter olmalı.", parent=self)
            self.entry_sifre.focus_set()
            return
        if sifre and len(sifre) < 6:
            messagebox.showwarning(
                "Şifre çok kısa", "Şifre en az 6 karakter olmalı.", parent=self)
            self.entry_sifre.focus_set()
            return

        try:
            sinif = int(self.var_sinif.get().split(".")[0])
        except Exception:
            sinif = 5

        self.sonuc = (isim, sinif, sifre)
        self.destroy()

    def _iptal(self):
        self.sonuc = None
        self.destroy()


# ==============================================================================
# ÇALIŞTIRMA
# ==============================================================================
if __name__ == "__main__":
    app = OgretmenPaneli()
    app.mainloop()
