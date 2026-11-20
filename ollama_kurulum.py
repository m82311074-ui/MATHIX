"""
MATHİX Ollama Manager - Tkinter Arayüzü
Orijinal komut satırı programının işlevleri grafik arayüze taşınmıştır.
"""

import os
import platform
import queue
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

VERSION = "0.6"
LINUX_LIKE = ("Arch Linux", "Debian", "Fedora", "Linux")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Renkler
BG = "#1e2130"
PANEL = "#272b3f"
ACCENT = "#4f8cff"
TEXT = "#e8eaf2"
MUTED = "#9aa0b8"
GREEN = "#4ade80"
RED = "#f87171"
YELLOW = "#fbbf24"


# ─────────────────────────────────────────
# SİSTEM TESPİTİ
# ─────────────────────────────────────────

def detect_os():
    system = platform.system()
    if system == "Windows":
        return "Windows"
    if system == "Darwin":
        return "macOS"
    if system == "Linux":
        try:
            data = platform.freedesktop_os_release()
            distro = data.get("ID", "").lower()
            like = data.get("ID_LIKE", "").lower()
            if distro in ("arch", "cachyos", "manjaro") or "arch" in like:
                return "Arch Linux"
            if distro in ("debian", "ubuntu", "linuxmint", "kali") or "debian" in like:
                return "Debian"
            if distro in ("fedora", "rhel", "centos") or "fedora" in like:
                return "Fedora"
        except Exception:
            pass
        return "Linux"
    return "Unknown"


OS_NAME = detect_os()


def command_exists(name):
    return shutil.which(name) is not None


def is_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


# ─────────────────────────────────────────
# DONANIM TESPİTİ VE MODEL ÖNERİSİ
# ─────────────────────────────────────────

def _m(name, size, family, kind, desc):
    return {"name": name, "size": size, "family": family, "kind": kind, "desc": desc}


# size: yaklaşık indirme boyutu (GB). kind: genel / kod / mantik
CATALOG = [
    _m("qwen3:0.6b", 0.5, "qwen", "genel", "Çok küçük ve hızlı; eski bilgisayarlarda basit işler için."),
    _m("gemma3:1b", 0.8, "gemma", "genel", "Hafif ve hızlı; kısa sorular ve özetler için."),
    _m("llama3.2:1b", 1.3, "llama", "genel", "Hafif, genel amaçlı model."),
    _m("qwen3:1.7b", 1.4, "qwen", "genel", "Küçük ama yetenekli; düşük bellekli bilgisayarlar için."),
    _m("llama3.2:3b", 2.0, "llama", "genel", "Hızlı; günlük sohbet ve özet için dengeli."),
    _m("qwen3:4b", 2.6, "qwen", "genel", "Boyutuna göre güçlü; çok dilli, Türkçe desteği iyi."),
    _m("gemma3:4b", 3.3, "gemma", "genel", "Çok dilli, Türkçe desteği iyi; görselleri de anlayabilir."),
    _m("llama3.1:8b", 4.9, "llama", "genel", "Popüler ve dengeli genel amaçlı model."),
    _m("qwen3:8b", 5.2, "qwen", "genel", "Güçlü genel model; çok dilli, mantık yürütmede iyi."),
    _m("gemma3:12b", 8.1, "gemma", "genel", "Kaliteli yanıtlar; çok dilli, görselleri de anlayabilir."),
    _m("qwen3:14b", 9.3, "qwen", "genel", "Yüksek kaliteli genel amaçlı model."),
    _m("gemma3:27b", 17.0, "gemma", "genel", "Çok yüksek kalite; güçlü donanım gerektirir."),
    _m("qwen3:32b", 20.0, "qwen", "genel", "Üst düzey genel model; güçlü donanım gerektirir."),
    _m("llama3.3:70b", 43.0, "llama", "genel", "En yüksek kalite; çok güçlü donanım gerektirir."),
    _m("qwen2.5-coder:1.5b", 1.0, "qwen-coder", "kod", "Hafif kod yardımcısı."),
    _m("qwen2.5-coder:3b", 1.9, "qwen-coder", "kod", "Küçük kod asistanı."),
    _m("qwen2.5-coder:7b", 4.7, "qwen-coder", "kod", "Kod yazma ve hata ayıklama için çok iyi."),
    _m("qwen2.5-coder:14b", 9.0, "qwen-coder", "kod", "Güçlü kod asistanı."),
    _m("qwen2.5-coder:32b", 20.0, "qwen-coder", "kod", "Çok güçlü kod asistanı."),
    _m("deepseek-r1:1.5b", 1.1, "deepseek", "mantik", "Adım adım düşünen küçük model."),
    _m("deepseek-r1:8b", 5.2, "deepseek", "mantik", "Adım adım düşünerek mantık ve matematik problemleri çözer."),
    _m("deepseek-r1:14b", 9.0, "deepseek", "mantik", "Daha derin muhakeme; mantık ve matematik için."),
    _m("deepseek-r1:32b", 20.0, "deepseek", "mantik", "Üst düzey muhakeme modeli; güçlü donanım gerektirir."),
]

MEM_OVERHEAD = 1.25  # model boyutu x 1.25 ≈ çalışırken gereken bellek


def detect_hardware():
    """RAM, GPU/VRAM ve boş disk bilgisini toplar; hata verirse varsayılan döner."""
    ram = 0.0
    gpu_name, vram = "", 0.0
    disk = 0.0
    win_kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

    # RAM
    try:
        if OS_NAME == "Windows":
            import ctypes

            class MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            s = MemStatus()
            s.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            ram = s.ullTotalPhys / 1024 ** 3
        elif OS_NAME == "macOS":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=5)
            ram = int(out.strip()) / 1024 ** 3
        else:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        ram = int(line.split()[1]) / 1024 ** 2
                        break
    except Exception:
        pass

    # NVIDIA GPU
    try:
        if command_exists("nvidia-smi"):
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8, **win_kwargs)
            for line in out.stdout.strip().splitlines():
                name, _, mem = line.rpartition(",")
                mem_gb = float(mem.strip()) / 1024
                if mem_gb > vram:
                    gpu_name, vram = name.strip(), mem_gb
    except Exception:
        pass

    # AMD GPU (Linux)
    if vram == 0 and OS_NAME in LINUX_LIKE:
        try:
            for p in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
                gb = int(p.read_text().strip()) / 1024 ** 3
                if gb >= 4 and gb > vram:
                    gpu_name, vram = "AMD GPU", gb
        except Exception:
            pass

    # Boş disk
    try:
        disk = shutil.disk_usage(Path.home()).free / 1024 ** 3
    except Exception:
        disk = 50.0

    apple = OS_NAME == "macOS" and platform.machine() == "arm64"
    ram_known = ram > 0
    if not ram_known:
        ram = 8.0  # bilinmiyorsa temkinli varsayım

    if apple:
        budget, mode = ram * 0.7, "Apple Silicon (birleşik bellek)"
        gpu_name = "Apple Silicon"
    elif vram >= 4:
        budget, mode = vram, "Ekran kartı belleği"
    else:
        budget, mode = max((ram - 3) * 0.6, ram * 0.45), "İşlemci + RAM"

    return {"ram": ram, "ram_known": ram_known, "gpu": gpu_name or "Yok / algılanamadı",
            "vram": vram, "disk": disk, "budget": budget, "mode": mode}


def recommend_models(hw, installed=()):
    """Donanıma uygun, birbirinden farklı en fazla 5 model döndürür: [(model, rozet), ...]"""
    fits = [m for m in CATALOG
            if m["name"] not in installed
            and m["size"] * MEM_OVERHEAD <= hw["budget"]
            and m["size"] + 2 <= hw["disk"]]
    picks = []
    badges = {}

    def take(cands, badge):
        for m in cands:
            if m["name"] not in badges:
                picks.append(m)
                badges[m["name"]] = badge
                return m
        return None

    def biggest(kind):
        return sorted((m for m in fits if m["kind"] == kind), key=lambda m: -m["size"])

    general = biggest("genel")
    first = take(general, "★ En iyi genel")
    if first:
        take([m for m in general if m["family"] != first["family"]], "Alternatif genel")
    take(biggest("kod"), "💻 Kod yazımı")
    take(biggest("mantik"), "🧠 Muhakeme")
    if first:
        fast = [m for m in general if m["size"] <= 0.4 * first["size"]]
        take(fast or sorted(general, key=lambda m: m["size"]), "⚡ Hızlı")
    for m in sorted(fits, key=lambda m: -m["size"]):
        if len(picks) >= 5:
            break
        take([m], "Diğer seçenek")
    return [(m, badges[m["name"]]) for m in picks[:5]]


# ─────────────────────────────────────────
# ANA UYGULAMA
# ─────────────────────────────────────────

class OllamaManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"MATHİX Ollama Manager v{VERSION}")
        self.geometry("980x640")
        self.minsize(820, 540)
        self.configure(bg=BG)

        self.q = queue.Queue()
        self.busy = False
        self.sudo_pw = None
        self._last_progress = 0.0
        self.buttons = []
        self.hw = None

        self._setup_style()
        self._build_ui()
        self.after(100, self._poll_queue)
        self.refresh_status()
        threading.Thread(target=self._load_hw, daemon=True).start()

        self.log("MATHİX Ollama Manager'a hoş geldiniz.", "info")
        self.log(f"Algılanan sistem: {OS_NAME} ({platform.machine()})", "info")

    # ── Stil ────────────────────────────────
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Value.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("Side.TButton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10),
                        padding=(14, 10), anchor="w", borderwidth=0)
        style.map("Side.TButton",
                  background=[("active", ACCENT), ("disabled", PANEL)],
                  foreground=[("disabled", "#5b617a")])
        style.configure("Danger.TButton", background="#4a2a33", foreground=TEXT,
                        font=("Segoe UI", 10), padding=(14, 10), anchor="w", borderwidth=0)
        style.map("Danger.TButton",
                  background=[("active", "#c2415a"), ("disabled", PANEL)],
                  foreground=[("disabled", "#5b617a")])
        style.configure("Small.TButton", background=PANEL, foreground=TEXT, padding=(10, 4))
        style.map("Small.TButton", background=[("active", ACCENT)])
        style.configure("TProgressbar", troughcolor=PANEL, background=ACCENT, borderwidth=0)

    # ── Arayüz ──────────────────────────────
    def _build_ui(self):
        # Başlık
        head = ttk.Frame(self)
        head.pack(fill="x", padx=20, pady=(16, 8))
        ttk.Label(head, text="MATHİX Ollama Manager", style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text=f"Sürüm {VERSION}  •  Ollama kurulum ve yönetim aracı",
                  style="Sub.TLabel").pack(anchor="w")

        # Durum kartları
        cards = ttk.Frame(self)
        cards.pack(fill="x", padx=20, pady=(4, 10))
        self.var_os = tk.StringVar(value=OS_NAME)
        self.var_arch = tk.StringVar(value=platform.machine())
        self.var_status = tk.StringVar(value="Kontrol ediliyor...")
        self.var_ver = tk.StringVar(value="—")
        self.status_label = None
        for i, (title, var) in enumerate([
            ("İşletim sistemi", self.var_os),
            ("Mimari", self.var_arch),
            ("Ollama durumu", self.var_status),
            ("Ollama sürümü", self.var_ver),
        ]):
            card = ttk.Frame(cards, style="Panel.TFrame", padding=(14, 10))
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            cards.columnconfigure(i, weight=1)
            ttk.Label(card, text=title, style="Muted.TLabel").pack(anchor="w")
            lbl = ttk.Label(card, textvariable=var, style="Value.TLabel")
            lbl.pack(anchor="w")
            if title == "Ollama durumu":
                self.status_label = lbl

        # Gövde
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Kenar çubuğu
        side = ttk.Frame(body, style="Panel.TFrame", padding=8)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 12))

        items = [
            ("⬇  Ollama Kur", self.on_install, "Side.TButton"),
            ("ℹ  Sürüm Bilgisi", self.on_version, "Side.TButton"),
            ("📋  Model Listesi", self.on_list_models, "Side.TButton"),
            ("➕  Model İndir", self.on_pull_model, "Side.TButton"),
            ("➖  Model Sil", self.on_remove_model, "Side.TButton"),
            ("⚙  Servis Yönetimi", self.on_service, "Side.TButton"),
            ("🔄  Durumu Yenile", self.refresh_status, "Side.TButton"),
            ("🗑  Ollama Kaldır", self.on_uninstall, "Danger.TButton"),
        ]
        for text, cmd, sty in items:
            b = ttk.Button(side, text=text, command=cmd, style=sty, width=22)
            b.pack(fill="x", pady=3)
            self.buttons.append(b)

        ttk.Button(side, text="Çıkış", command=self.destroy, style="Side.TButton",
                   width=22).pack(fill="x", pady=(14, 3))

        # Günlük paneli
        right = ttk.Frame(body, style="Panel.TFrame", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        top = ttk.Frame(right, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(top, text="İşlem Günlüğü", style="Panel.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(top, text="Temizle", style="Small.TButton",
                   command=self.clear_log).pack(side="right")

        self.logbox = ScrolledText(right, bg="#14172a", fg=TEXT, insertbackground=TEXT,
                                   font=("Consolas", 10), relief="flat", wrap="word",
                                   state="disabled", padx=10, pady=8)
        self.logbox.grid(row=1, column=0, sticky="nsew")
        self.logbox.tag_config("info", foreground=ACCENT)
        self.logbox.tag_config("ok", foreground=GREEN)
        self.logbox.tag_config("warn", foreground=YELLOW)
        self.logbox.tag_config("err", foreground=RED)
        self.logbox.tag_config("raw", foreground=TEXT)

        # Alt çubuk
        foot = ttk.Frame(self)
        foot.pack(fill="x", padx=20, pady=(0, 12))
        self.var_foot = tk.StringVar(value="Hazır")
        ttk.Label(foot, textvariable=self.var_foot, style="Sub.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(foot, mode="indeterminate", length=180)
        self.progress.pack(side="right")

    # ── Günlük ve kuyruk ───────────────────
    def log(self, msg, tag="raw"):
        """Her iş parçacığından güvenle çağrılabilir."""
        self.q.put(("log", (msg, tag)))

    def _append(self, msg, tag):
        self.logbox.config(state="normal")
        prefix = {"info": "[BİLGİ] ", "ok": "[TAMAM] ", "warn": "[UYARI] ", "err": "[HATA] "}.get(tag, "")
        self.logbox.insert("end", prefix + msg + "\n", tag)
        self.logbox.see("end")
        self.logbox.config(state="disabled")

    def clear_log(self):
        self.logbox.config(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.config(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._append(*data)
                elif kind == "call":
                    data()
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def call_main(self, fn):
        self.q.put(("call", fn))

    # ── Görev yönetimi ─────────────────────
    def start_task(self, title, func):
        if self.busy:
            messagebox.showinfo("Meşgul", "Devam eden bir işlem var, lütfen bekleyin.")
            return
        self.busy = True
        self.var_foot.set(f"{title}...")
        self.progress.start(12)
        for b in self.buttons:
            b.state(["disabled"])

        def worker():
            try:
                func()
            except Exception as e:  # noqa: BLE001
                self.log(f"Beklenmeyen hata: {e}", "err")
            finally:
                self.call_main(self._task_done)

        threading.Thread(target=worker, daemon=True).start()

    def _task_done(self):
        self.busy = False
        self.progress.stop()
        self.var_foot.set("Hazır")
        for b in self.buttons:
            b.state(["!disabled"])
        self.refresh_status()

    # ── Komut çalıştırma ───────────────────
    def run_stream(self, command, stdin_text=None):
        self.last_lines = []  # son komutun çıktısı (hata ayıklama için)
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            p = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if stdin_text else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                **kwargs,
            )
        except FileNotFoundError:
            self.log(f"Komut bulunamadı: {command[0]}", "err")
            return None
        except Exception as e:  # noqa: BLE001
            self.log(str(e), "err")
            return None

        if stdin_text:
            try:
                p.stdin.write(stdin_text)
                p.stdin.flush()
                p.stdin.close()
            except Exception:
                pass

        for line in p.stdout:
            line = ANSI_RE.sub("", line).rstrip()
            if not line.strip():
                continue
            self.last_lines.append(line)
            # İlerleme çubuğu satırlarını seyrelt
            if "%" in line:
                now = time.time()
                if now - self._last_progress < 0.4:
                    continue
                self._last_progress = now
            self.log(line)
        p.wait()
        return p.returncode

    def run_priv(self, command):
        """Linux'ta gerektiğinde sudo ile çalıştırır (parola önceden alınır)."""
        if is_root() or OS_NAME not in LINUX_LIKE:
            return self.run_stream(command)
        if not command_exists("sudo"):
            self.log("sudo bulunamadı.", "err")
            return None
        rc = self.run_stream(["sudo", "-S", "-p", ""] + command,
                             stdin_text=(self.sudo_pw or "") + "\n")
        return rc

    def ensure_sudo(self):
        """Ana iş parçacığında, gerekirse yönetici parolasını sorar."""
        if OS_NAME not in LINUX_LIKE or is_root():
            return True
        if self.sudo_pw:
            return True
        pw = simpledialog.askstring("Yönetici yetkisi",
                                    "Bu işlem için sudo parolanız gerekiyor:",
                                    show="•", parent=self)
        if not pw:
            return False
        self.sudo_pw = pw
        return True

    def ask_sudo_threadsafe(self):
        """Arka plan görevinden çağrılır; parola penceresini ana iş parçacığında açar."""
        if OS_NAME not in LINUX_LIKE or is_root() or self.sudo_pw:
            return True
        done = threading.Event()
        result = {"ok": False}

        def ask():
            result["ok"] = self.ensure_sudo()
            done.set()

        self.call_main(ask)
        done.wait()
        return result["ok"]

    # ── Durum ──────────────────────────────
    def refresh_status(self):
        def work():
            installed = command_exists("ollama")
            version = "—"
            if installed:
                try:
                    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
                    out = subprocess.run(["ollama", "--version"], capture_output=True,
                                         text=True, timeout=10, **kwargs)
                    text = (out.stdout + out.stderr).strip().splitlines()
                    version = text[-1] if text else "—"
                except Exception:
                    version = "okunamadı"

            def apply():
                self.var_status.set("● Kurulu" if installed else "● Kurulu değil")
                self.status_label.configure(foreground=GREEN if installed else RED)
                self.var_ver.set(version)
            self.call_main(apply)

        threading.Thread(target=work, daemon=True).start()

    def require_ollama(self):
        if not command_exists("ollama"):
            messagebox.showwarning("Ollama bulunamadı", "Önce Ollama kurulmalı.")
            return False
        return True

    # ── Basit komutlar ─────────────────────
    def on_version(self):
        if not self.require_ollama():
            return

        def work():
            self.log("Sürüm bilgisi alınıyor...", "info")
            self.run_stream(["ollama", "--version"])
        self.start_task("Sürüm bilgisi alınıyor", work)

    def on_list_models(self):
        if not self.require_ollama():
            return

        def work():
            self.log("Yüklü modeller:", "info")
            self.run_stream(["ollama", "list"])
        self.start_task("Modeller listeleniyor", work)

    def _load_hw(self):
        try:
            self.hw = detect_hardware()
        except Exception:
            self.hw = None

    def _list_installed(self):
        """`ollama list` çıktısından [(ad, boyut), ...] döndürür."""
        models = []
        try:
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            out = subprocess.run(["ollama", "list"], capture_output=True, text=True,
                                 timeout=8, **kwargs)
            for line in out.stdout.splitlines()[1:]:
                parts = line.split()
                if not parts:
                    continue
                m = re.match(r"^(\S+)\s+\S+\s+([\d.]+\s*[KMGT]?B)\b", line)
                models.append((parts[0], m.group(2) if m else "?"))
        except Exception:
            pass
        return models

    def _installed_models(self):
        names = set()
        for name, _ in self._list_installed():
            names.add(name)
            if name.endswith(":latest"):
                names.add(name[:-7])
        return names

    def _pull_model(self, name):
        def work():
            self.log(f"'{name}' indiriliyor...", "info")
            rc = self.run_stream(["ollama", "pull", name])
            if rc == 0:
                self.log(f"'{name}' indirildi. Kullanmak için terminalde: ollama run {name}", "ok")
            else:
                if "permission denied" in "\n".join(self.last_lines).lower():
                    self.log("Model klasöründe izin hatası var. Çözüm için terminalde: "
                             "sudo chown -R ollama:ollama /var/lib/ollama", "warn")
                self.log("Model indirilemedi. Model adını ve Ollama servisinin "
                         "çalıştığını kontrol edin.", "err")
        self.start_task(f"{name} indiriliyor", work)

    def on_pull_model(self):
        if not self.require_ollama():
            return

        hw = self.hw or detect_hardware()
        picks = recommend_models(hw, self._installed_models())

        dlg = tk.Toplevel(self)
        dlg.title("Model İndir")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=18)
        frm.pack()
        ttk.Label(frm, text="Bilgisayarınıza uygun modeller",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")

        # Donanım özeti
        summ = ttk.Frame(frm, style="Panel.TFrame", padding=(12, 8))
        summ.pack(fill="x", pady=(8, 10))
        ram_txt = f"{hw['ram']:.0f} GB" if hw["ram_known"] else "algılanamadı (8 GB varsayıldı)"
        ttk.Label(summ, style="Panel.TLabel",
                  text=f"RAM: {ram_txt}   •   Ekran kartı: {hw['gpu']}"
                       + (f" ({hw['vram']:.0f} GB)" if hw["vram"] >= 1 else "")
                       + f"   •   Boş disk: {hw['disk']:.0f} GB").pack(anchor="w")
        ttk.Label(summ, style="Muted.TLabel",
                  text=f"Öneriler için kullanılan bellek payı: ~{hw['budget']:.0f} GB "
                       f"({hw['mode']})").pack(anchor="w")

        choice = tk.StringVar(value=picks[0][0]["name"] if picks else "__custom__")

        def radio(parent, text, value, bold=True):
            return tk.Radiobutton(parent, text=text, variable=choice, value=value,
                                  bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL,
                                  activeforeground=TEXT, anchor="w",
                                  font=("Segoe UI", 10, "bold" if bold else "normal"))

        if picks:
            for m, badge in picks:
                card = ttk.Frame(frm, style="Panel.TFrame", padding=(10, 6))
                card.pack(fill="x", pady=3)
                radio(card, f"{m['name']}    {badge}", m["name"]).pack(anchor="w")
                ttk.Label(card, style="Muted.TLabel", wraplength=560, justify="left",
                          text=f"İndirme boyutu ≈ {m['size']:.1f} GB  •  {m['desc']}"
                          ).pack(anchor="w", padx=22)
        else:
            ttk.Label(frm, wraplength=580, justify="left",
                      text="Bu bilgisayar için hazır öneri bulunamadı (bellek veya disk "
                           "yetersiz olabilir). Aşağıya model adını yazabilirsiniz."
                      ).pack(anchor="w", pady=6)

        # Elle model adı
        custom = ttk.Frame(frm, style="Panel.TFrame", padding=(10, 8))
        custom.pack(fill="x", pady=(8, 3))
        radio(custom, "Model adını kendim yazacağım:", "__custom__", bold=False).pack(side="left")
        custom_var = tk.StringVar()
        entry = tk.Entry(custom, textvariable=custom_var, width=22, bg="#14172a", fg=TEXT,
                         insertbackground=TEXT, relief="flat")
        entry.pack(side="left", padx=8, ipady=3)
        entry.bind("<Key>", lambda e: choice.set("__custom__"))

        ttk.Label(frm, style="Sub.TLabel", wraplength=580, justify="left",
                  text="Boyutlar yaklaşıktır. Tüm modelleri ollama.com/library adresinde "
                       "görebilirsiniz. Zaten yüklü olan modeller öneriden çıkarılır."
                  ).pack(anchor="w", pady=(8, 0))

        def go():
            name = custom_var.get().strip() if choice.get() == "__custom__" else choice.get()
            if not name:
                messagebox.showwarning("Model adı", "Lütfen bir model seçin veya adını yazın.",
                                       parent=dlg)
                return
            dlg.destroy()
            self._pull_model(name)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(14, 0))
        ttk.Button(btns, text="⬇ İndir", style="Small.TButton", command=go).pack(side="right")
        ttk.Button(btns, text="Vazgeç", style="Small.TButton",
                   command=dlg.destroy).pack(side="right", padx=8)

    def _remove_model_worker(self, name):
        self.log(f"'{name}' siliniyor...", "info")
        rc = self.run_stream(["ollama", "rm", name])
        if rc == 0:
            self.log(f"'{name}' silindi.", "ok")
            return

        output = "\n".join(self.last_lines)
        m = re.search(r"remove (/.+?): permission denied", output)
        if m and OS_NAME in LINUX_LIKE:
            self._force_remove_manifest(name, m.group(1))
            return
        self.log("Model silinemedi. Hata ayrıntısı için yukarıdaki çıktıya bakın.", "err")

    def _force_remove_manifest(self, name, path):
        """Servis dosyaya yazamıyorsa (sahiplik hatası) manifest'i yönetici yetkisiyle siler."""
        if not (re.fullmatch(r"/[\w.@+:/-]+", path) and "/manifests" in path and ".." not in path):
            self.log("Beklenmeyen dosya yolu; güvenlik nedeniyle işlem yapılmadı.", "err")
            return

        self.log("Model dosyaları Ollama servisinin yazamadığı bir sahiplikte (izin hatası). "
                 "Yönetici yetkisiyle kaldırılıyor...", "warn")
        if not self.ask_sudo_threadsafe():
            self.log("Yönetici parolası girilmedi, işlem iptal edildi.", "warn")
            return

        if self.run_priv(["rm", "-f", path]) != 0:
            self.sudo_pw = None
            self.log("Model dosyası kaldırılamadı. Parolayı kontrol edip tekrar deneyin.", "err")
            return
        self.run_priv(["rmdir", "--ignore-fail-on-non-empty", os.path.dirname(path)])
        self.log(f"'{name}' silindi.", "ok")

        self.log("Kullanılmayan model katmanlarının temizlenmesi için servis "
                 "yeniden başlatılıyor...", "info")
        self.run_priv(["systemctl", "restart", "ollama"])
        self.log("Kalıcı çözüm için model klasörünün sahipliğini servis kullanıcısına "
                 "verebilirsiniz: sudo chown -R ollama:ollama /var/lib/ollama", "info")

    def on_remove_model(self):
        if not self.require_ollama():
            return

        models = self._list_installed()
        if not models:
            messagebox.showinfo("Model bulunamadı",
                                "Yüklü model bulunamadı.\n\n"
                                "Henüz model indirmemiş olabilirsiniz ya da Ollama "
                                "servisi çalışmıyor olabilir.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Model Sil")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=18)
        frm.pack()
        ttk.Label(frm, text="Silinecek modeli seçin",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frm, style="Sub.TLabel",
                  text=f"Yüklü {len(models)} model bulundu. Silinen model tekrar "
                       "indirilmedikçe kullanılamaz."
                  ).pack(anchor="w", pady=(2, 10))

        # Kaydırılabilir liste
        holder = ttk.Frame(frm)
        holder.pack(fill="x")
        canvas = tk.Canvas(holder, bg=BG, highlightthickness=0, width=470,
                           height=min(len(models), 6) * 50)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        if len(models) > 6:
            scroll.pack(side="right", fill="y")

        def wheel(event):
            if len(models) > 6:
                up = getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4
                canvas.yview_scroll(-1 if up else 1, "units")

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            dlg.bind(seq, wheel)

        choice = tk.StringVar(value="")  # bilerek boş: yanlışlıkla silmeyi önler
        for name, size in models:
            card = ttk.Frame(inner, style="Panel.TFrame", padding=(10, 8))
            card.pack(fill="x", pady=3, padx=(0, 4))
            tk.Radiobutton(card, text=name, variable=choice, value=name, bg=PANEL, fg=TEXT,
                           selectcolor=BG, activebackground=PANEL, activeforeground=TEXT,
                           anchor="w", width=34,
                           font=("Segoe UI", 10, "bold")).pack(side="left")
            ttk.Label(card, text=size, style="Muted.TLabel").pack(side="right", padx=6)

        def go():
            name = choice.get()
            if not name:
                messagebox.showwarning("Model seçilmedi",
                                       "Lütfen silmek istediğiniz modeli seçin.", parent=dlg)
                return
            if not messagebox.askyesno("Onay", f"'{name}' modeli silinsin mi?",
                                       icon="warning", parent=dlg):
                return
            dlg.destroy()

            self.start_task(f"{name} siliniyor", lambda: self._remove_model_worker(name))

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(14, 0))
        ttk.Button(btns, text="🗑 Seçileni Sil", style="Danger.TButton", command=go
                   ).pack(side="right")
        ttk.Button(btns, text="Vazgeç", style="Small.TButton",
                   command=dlg.destroy).pack(side="right", padx=8)

    # ── Kurulum ────────────────────────────
    def on_install(self):
        if command_exists("ollama"):
            messagebox.showinfo("Bilgi", "Ollama zaten kurulu.")
            return

        if OS_NAME == "Windows":
            if not command_exists("powershell.exe"):
                messagebox.showerror("Hata", "PowerShell bulunamadı.")
                return
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-Command", "irm https://ollama.com/install.ps1 | iex"]
        elif OS_NAME == "macOS":
            if not command_exists("brew"):
                messagebox.showerror("Hata", "Homebrew bulunamadı.\nhttps://brew.sh")
                return
            command = ["brew", "install", "ollama"]
        elif OS_NAME in LINUX_LIKE:
            if not command_exists("curl"):
                messagebox.showerror("Hata", "curl bulunamadı.")
                return
            command = ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
        else:
            messagebox.showerror("Hata", "İşletim sistemi desteklenmiyor.")
            return

        if not messagebox.askyesno("Kurulum",
                                   "Ollama resmî kurulum yöntemi kullanılacak.\n\n"
                                   "Kurulumu başlatmak istiyor musunuz?"):
            self.log("Kurulum iptal edildi.", "warn")
            return
        if not self.ensure_sudo():
            self.log("Yönetici parolası girilmedi, kurulum iptal edildi.", "warn")
            return

        def work():
            self.log("Kurulum başlatılıyor...", "info")
            rc = self.run_priv(command) if OS_NAME in LINUX_LIKE else self.run_stream(command)
            if rc != 0:
                if OS_NAME in LINUX_LIKE:
                    self.sudo_pw = None  # yanlış parola olasılığı
                self.log("Kurulum başarısız oldu.", "err")
                return
            if command_exists("ollama"):
                self.log("Ollama kuruldu!", "ok")
            else:
                self.log("Kurulum tamamlandı fakat komut henüz bulunamadı. "
                         "Uygulamayı yeniden başlatıp tekrar deneyin.", "warn")
        self.start_task("Ollama kuruluyor", work)

    # ── Kaldırma ───────────────────────────
    def on_uninstall(self):
        if not command_exists("ollama"):
            messagebox.showwarning("Ollama bulunamadı",
                                   "Ollama komutu bulunamadı.\n"
                                   "Bilinen kurulum dosyalarını işletim sisteminizin "
                                   "uygulama kaldırma aracıyla kontrol edebilirsiniz.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Ollama Kaldırma")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()

        mode = tk.StringVar(value="normal")
        frm = ttk.Frame(dlg, padding=20)
        frm.pack()
        ttk.Label(frm, text="Kaldırma türünü seçin", style="Title.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 10))

        for value, title, desc in [
            ("normal", "Normal kaldırma", "Ollama kaldırılır, modeller korunur."),
            ("full", "Tam kaldırma", "Ollama ve bilinen model dizinleri silinir."),
        ]:
            f = ttk.Frame(frm, style="Panel.TFrame", padding=10)
            f.pack(fill="x", pady=4)
            tk.Radiobutton(f, text=title, variable=mode, value=value, bg=PANEL, fg=TEXT,
                           selectcolor=BG, activebackground=PANEL, activeforeground=TEXT,
                           font=("Segoe UI", 10, "bold"), anchor="w").pack(anchor="w")
            ttk.Label(f, text=desc, style="Muted.TLabel").pack(anchor="w", padx=22)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(14, 0))

        def go():
            choice = mode.get()
            dlg.destroy()
            self._confirm_uninstall(choice)

        ttk.Button(btns, text="Devam", style="Danger.TButton", command=go).pack(side="right")
        ttk.Button(btns, text="Vazgeç", style="Small.TButton",
                   command=dlg.destroy).pack(side="right", padx=8)

    def _confirm_uninstall(self, choice):
        msg = "Ollama kaldırılsın mı?"
        if choice == "full":
            msg += "\n\nDİKKAT: İndirdiğiniz tüm modeller de silinecek!"
        if not messagebox.askyesno("Onay", msg, icon="warning"):
            self.log("İşlem iptal edildi.", "warn")
            return
        if not self.ensure_sudo():
            self.log("Yönetici parolası girilmedi, işlem iptal edildi.", "warn")
            return

        def work():
            if OS_NAME in LINUX_LIKE:
                removed = self._remove_linux()
            elif OS_NAME == "Windows":
                removed = self._remove_windows()
            elif OS_NAME == "macOS":
                removed = self._remove_macos()
            else:
                self.log("İşletim sistemi desteklenmiyor.", "err")
                removed = False

            if not removed:
                self.log("Kaldırma işlemi tamamlanamadı.", "err")
                return
            if choice == "full":
                self._delete_model_data()
            self.log("Kaldırma işlemi tamamlandı!", "ok")
        self.start_task("Ollama kaldırılıyor", work)

    def _remove_linux(self):
        self.log("Linux Ollama kaldırma işlemi başlatılıyor...", "info")
        self.run_priv(["systemctl", "stop", "ollama"])
        self.run_priv(["systemctl", "disable", "ollama"])
        paths = [
            "/usr/local/bin/ollama",
            "/usr/bin/ollama",
            "/usr/local/lib/ollama",
            "/etc/systemd/system/ollama.service",
            "/etc/systemd/system/ollama.service.d",
        ]
        rc = self.run_priv(["rm", "-rf"] + paths)
        if rc != 0:
            self.log("Bazı Ollama dosyaları kaldırılamadı.", "err")
            self.sudo_pw = None
            return False
        self.run_priv(["systemctl", "daemon-reload"])
        self.run_priv(["systemctl", "reset-failed", "ollama"])
        return True

    def _remove_windows(self):
        if not command_exists("winget"):
            self.log("winget bulunamadı. Ayarlar > Uygulamalar bölümünden "
                     "Ollama'yı kaldırabilirsiniz.", "err")
            return False
        rc = self.run_stream(["winget", "uninstall", "--id", "Ollama.Ollama", "--exact"])
        return rc == 0

    def _remove_macos(self):
        if not command_exists("brew"):
            self.log("Homebrew bulunamadı. Ollama'yı Uygulamalar klasöründen "
                     "kaldırmanız gerekebilir.", "err")
            return False
        self.run_stream(["brew", "services", "stop", "ollama"])
        return self.run_stream(["brew", "uninstall", "ollama"]) == 0

    def _delete_model_data(self):
        """Yalnızca bilinen Ollama model dizinlerini hedefler."""
        paths = [Path.home() / ".ollama"]
        if OS_NAME in LINUX_LIKE:
            paths += [Path("/usr/share/ollama/.ollama"),
                      Path("/var/lib/ollama"),
                      Path("/usr/local/share/ollama/.ollama")]
        for path in paths:
            try:
                if not path.exists():
                    continue
                if OS_NAME in LINUX_LIKE:
                    ok = self.run_priv(["rm", "-rf", str(path)]) == 0
                else:
                    shutil.rmtree(path)
                    ok = True
                self.log(f"Silindi: {path}" if ok else f"Dizin silinemedi: {path}",
                         "ok" if ok else "warn")
            except Exception as e:  # noqa: BLE001
                self.log(f"{path} silinemedi: {e}", "warn")

    # ── Servis yönetimi ────────────────────
    def on_service(self):
        if not self.require_ollama():
            return

        if OS_NAME in LINUX_LIKE:
            actions = [("▶ Başlat", "start"), ("■ Durdur", "stop"),
                       ("↻ Yeniden başlat", "restart"), ("ℹ Durumu göster", "status")]

            def make(action):
                def work():
                    self.log(f"systemctl {action} ollama", "info")
                    if action == "status":
                        self.run_stream(["systemctl", "status", "ollama", "--no-pager"])
                    else:
                        rc = self.run_priv(["systemctl", action, "ollama"])
                        if rc == 0:
                            self.log("İşlem tamamlandı.", "ok")
                        else:
                            self.sudo_pw = None
                            self.log("İşlem başarısız oldu.", "err")
                return work
        elif OS_NAME == "macOS":
            if not command_exists("brew"):
                messagebox.showwarning("Uyarı", "Homebrew bulunamadı.")
                return
            actions = [("▶ Başlat", "start"), ("■ Durdur", "stop")]

            def make(action):
                def work():
                    self.run_stream(["brew", "services", action, "ollama"])
                return work
        else:
            messagebox.showinfo("Bilgi", "Bu işletim sisteminde servis yönetimi "
                                         "otomatik desteklenmiyor.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Servis Yönetimi")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=20)
        frm.pack()
        ttk.Label(frm, text="Ollama servisi", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", pady=(0, 10))

        def run_action(action):
            dlg.destroy()
            if action != "status" and not self.ensure_sudo():
                self.log("Yönetici parolası girilmedi.", "warn")
                return
            self.start_task("Servis işlemi", make(action))

        for text, action in actions:
            ttk.Button(frm, text=text, style="Side.TButton", width=24,
                       command=lambda a=action: run_action(a)).pack(fill="x", pady=3)
        ttk.Button(frm, text="Kapat", style="Small.TButton",
                   command=dlg.destroy).pack(anchor="e", pady=(10, 0))


if __name__ == "__main__":
    app = OllamaManager()
    app.mainloop()