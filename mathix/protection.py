"""Recognize distracting apps and pause games until the learner resumes."""
import os
import re
import signal
import subprocess
import sys
import time
import tkinter as tk

from mathix import database as db
from mathix.config import CARD_COLOR, TEXT_COLOR, SECONDARY_TEXT, RED


_APP_NAMES = {
    "chrome": "Google Chrome", "google-chrome": "Google Chrome",
    "google-chrome-stable": "Google Chrome", "chromium": "Chromium",
    "chromium-browser": "Chromium", "firefox": "Firefox",
    "firefox-esr": "Firefox", "firefox-bin": "Firefox", "brave": "Brave",
    "brave-browser": "Brave", "msedge": "Microsoft Edge",
    "microsoftedge": "Microsoft Edge", "microsoft-edge": "Microsoft Edge",
    "opera": "Opera", "vivaldi": "Vivaldi", "safari": "Safari",
    "tor": "Tor Browser", "tor-browser": "Tor Browser",
    "yandex-browser": "Yandex Browser", "waterfox": "Waterfox",
    "librewolf": "LibreWolf", "floorp": "Floorp", "zen": "Zen Browser",
    "epiphany": "GNOME Web", "falkon": "Falkon", "qutebrowser": "qutebrowser",
    "midori": "Midori", "netsurf": "NetSurf", "konqueror": "Konqueror",
    "opera-gx": "Opera GX", "duckduckgo": "DuckDuckGo Browser",
    "arc": "Arc Browser", "mullvad-browser": "Mullvad Browser",
    "calculatorapp": "Windows Hesap Makinesi", "win32calc": "Windows Hesap Makinesi",
    "calc": "Hesap Makinesi", "calculator": "Hesap Makinesi",
    "gnome-calculator": "GNOME Hesap Makinesi", "org.gnome.calculator": "GNOME Hesap Makinesi",
    "kcalc": "KCalc", "org.kde.kcalc": "KCalc", "galculator": "Galculator",
    "mate-calc": "MATE Hesap Makinesi", "qalculate-gtk": "Qalculate",
    "qalculate-qt": "Qalculate", "speedcrunch": "SpeedCrunch",
    "deepin-calculator": "Deepin Hesap Makinesi",
}
_BROWSER_WORDS = {
    "browser", "chrome", "chromium", "firefox", "brave", "msedge", "edge",
    "opera", "vivaldi", "safari", "tor", "waterfox", "librewolf", "floorp",
    "zen", "epiphany", "falkon", "qutebrowser", "midori", "netsurf",
    "konqueror", "duckduckgo", "mullvad", "yandex", "palemoon", "helium",
    "sidekick", "orbitum",
}


def _normalize(name):
    return os.path.basename(name.replace("\\", "/").strip()).lower().removesuffix(".exe")


def _classify(name):
    normalized = _normalize(name)
    if normalized in _APP_NAMES:
        return _APP_NAMES[normalized]
    words = set(re.findall(r"[a-z0-9]+", normalized))
    if "calculator" in normalized or "calc" in words or normalized.startswith("calc"):
        return f"Benzer hesap makinesi ({normalized})"
    if words & _BROWSER_WORDS:
        return f"Benzer tarayıcı ({normalized})"
    return None


def _processes():
    """Yield process IDs and executable/script names without reading user data."""
    if sys.platform.startswith("linux") and os.path.isdir("/proc"):
        found = []
        try:
            for entry in os.scandir("/proc"):
                if not entry.name.isdigit():
                    continue
                pid = int(entry.name)
                try:
                    with open(f"/proc/{entry.name}/stat", encoding="utf-8") as f:
                        if f.read().rsplit(")", 1)[-1].split()[0] in {"Z", "X"}:
                            continue
                    with open(f"/proc/{entry.name}/comm", encoding="utf-8") as f:
                        found.append((pid, f.read().strip()))
                    with open(f"/proc/{entry.name}/cmdline", "rb") as f:
                        args = [p.decode(errors="ignore") for p in f.read().split(b"\0") if p]
                    if args:
                        found.append((pid, args[0]))
                    for arg in args[1:]:
                        candidate = os.path.basename(arg)
                        if candidate.lower().endswith((".py", ".pyw", ".asar", ".appimage")):
                            found.append((pid, candidate))
                    found.append((pid, os.readlink(f"/proc/{entry.name}/exe")))
                except (OSError, UnicodeError):
                    continue
        except OSError:
            return []
        return found

    if sys.platform == "win32":
        try:
            import csv
            from io import StringIO
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                text=True, timeout=2, check=False,
            )
            return [(int(row[1]), row[0]) for row in csv.reader(StringIO(result.stdout))
                    if len(row) > 1 and row[1].isdigit()]
        except (OSError, subprocess.TimeoutExpired):
            return []
    try:
        result = subprocess.run(
            ["ps", "-A", "-o", "pid=,comm="], capture_output=True,
            text=True, timeout=2, check=False,
        )
        result_rows = []
        for line in result.stdout.splitlines():
            fields = line.strip().split(maxsplit=1)
            if len(fields) == 2 and fields[0].isdigit():
                result_rows.append((int(fields[0]), fields[1]))
        return result_rows
    except (OSError, subprocess.TimeoutExpired):
        return []


def _matching_processes():
    matches = {}
    for pid, name in _processes():
        app = _classify(name)
        if app:
            matches.setdefault(pid, (app, name))
    return matches


def scan_disallowed_apps():
    return sorted({app for app, _name in _matching_processes().values()})


def close_disallowed_apps():
    """Close recognized processes after the visible countdown."""
    matches = _matching_processes()
    closed = set()
    if sys.platform == "win32":
        images = {}
        for _pid, (app, name) in matches.items():
            image = os.path.basename(name.replace("\\", "/"))
            if not image.lower().endswith(".exe"):
                image += ".exe"
            images[image.lower()] = app
        for image, app in images.items():
            try:
                result = subprocess.run(
                    ["taskkill", "/IM", image, "/T", "/F"],
                    capture_output=True, text=True, timeout=2, check=False,
                )
                if result.returncode == 0:
                    closed.add(app)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return closed

    signalled = []
    for pid, (app, _name) in matches.items():
        try:
            os.kill(pid, signal.SIGTERM)
            signalled.append((pid, app))
        except OSError:
            pass
    if signalled:
        time.sleep(0.15)
    for pid, app in signalled:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            closed.add(app)
            continue
        except PermissionError:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            closed.add(app)
        except OSError:
            pass
    return closed


class GameProtection:
    POLL_MS = 1000

    def __init__(self, parent, game_name, on_pause, on_resume, student_id=None):
        self.parent = parent
        self.game_name = game_name
        self.student_id = student_id
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.active_apps = set()
        self.window = self.label = self.status = self.button = None
        self.locked = self.stopped = False
        self.deadline = self.last_close = None
        self.close_attempted = False
        self.close_id = None
        parent.bind("<Destroy>", self._parent_destroyed, add="+")
        self.after_id = parent.after(300, self._poll)

    def _parent_destroyed(self, event):
        if event.widget is self.parent:
            self.stop()

    def _poll(self):
        if self.stopped:
            return
        apps = set(scan_disallowed_apps())
        for name in sorted(apps - self.active_apps):
            try:
                db.koruma_olayi_kaydet(self.game_name, name, self.student_id)
            except Exception:
                pass
        if apps and not self.active_apps:
            self.locked = True
            self.deadline = time.monotonic() + 3
            self.close_attempted = False
            self.last_close = None
            self.on_pause()
            self._show_window(apps)
            # Keep monitoring lightweight at 1 Hz, but honor the 3-second
            # deadline precisely instead of waiting for the next poll tick.
            self.close_id = self.parent.after(3000, self._deadline_close)
        elif not apps and self.active_apps:
            self.deadline = None
            if self.close_id:
                try:
                    self.parent.after_cancel(self.close_id)
                except tk.TclError:
                    pass
                self.close_id = None
            self._set_status("Uygulamalar kapandı. Düğmeye basınca oyun devam eder.")

        self.active_apps = apps
        now = time.monotonic()
        retry = self.close_attempted and self.last_close and now - self.last_close >= 1
        if apps and self.deadline and now >= self.deadline and (not self.close_attempted or retry):
            closed = close_disallowed_apps()
            self.close_attempted = True
            self.last_close = time.monotonic()
            self._set_status("Kapatma isteği yinelendi." if retry and closed else
                             "Uygulama kapatılıyor…" if closed else
                             "Otomatik kapatılamadı; elle kapatın.")
        if self.locked and self.window and self.window.winfo_exists():
            if apps:
                remain = max(0, int((self.deadline or now) - now + .999))
                self.label.config(text=self._message(apps, remain))
                self.button.config(state="disabled")
                if not self.close_attempted:
                    self._set_status(f"{remain} saniye içinde kapatılacak.")
            else:
                self.label.config(text=self._message(set()))
                self.button.config(state="normal")
        self.after_id = self.parent.after(self.POLL_MS, self._poll)

    def _deadline_close(self):
        self.close_id = None
        if self.stopped or not self.locked:
            return
        apps = set(scan_disallowed_apps())
        if not apps:
            return
        self.active_apps = apps
        closed = close_disallowed_apps()
        self.close_attempted = True
        self.last_close = time.monotonic()
        self._set_status("Kapatma isteği gönderildi." if closed else
                         "Otomatik kapatılamadı; uygulamayı elle kapatın.")

    def _message(self, apps, remaining=None):
        if not apps:
            return ("UYGULAMALAR KAPANDI\n\nDevam etmek için aşağıdaki düğmeye bas.\n"
                    "Hesap makinesi yerine MATHİX AI Koçu'nu kullanabilirsin.")
        names = sorted(apps)
        listed = "\n".join(f"• {name}" for name in names[:4])
        if len(names) > 4:
            listed += f"\n• +{len(names) - 4} uygulama"
        return ("OYUN DURAKLATILDI\n\nAçık uygulamalar kapatılacak:\n" + listed +
                (f"\n\n{remaining} saniye içinde kapatılacak." if remaining is not None
                 and not self.close_attempted else "") +
                "\n\nHesap makinesi yerine MATHİX AI Koçu'nu kullanabilirsin.")

    def _show_window(self, apps):
        if self.window and self.window.winfo_exists():
            return
        self.window = tk.Toplevel(self.parent)
        self.window.title("Oyun Koruması")
        self.window.configure(bg=CARD_COLOR)
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(self.window, text="⛨  OYUN KORUMASI",
                 font=("Segoe UI", 16, "bold"), fg=RED, bg=CARD_COLOR
                 ).pack(anchor="w", padx=20, pady=(15, 8))
        self.label = tk.Label(self.window, text=self._message(apps, 3),
                              font=("Segoe UI", 10), fg=TEXT_COLOR,
                              bg=CARD_COLOR, justify="left", wraplength=410)
        self.label.pack(fill="both", expand=True, padx=20, pady=5)
        self.status = tk.Label(self.window, text="3 saniye içinde kapatılacak.",
                               font=("Segoe UI", 9, "bold"),
                               fg=SECONDARY_TEXT, bg=CARD_COLOR)
        self.status.pack(anchor="w", padx=20, pady=(5, 10))
        self.button = tk.Button(
            self.window, text="Pencereyi Kapat ve Devam Et",
            command=self._dismiss, state="disabled", relief="flat",
            cursor="hand2", fg="white", bg="#26834A",
            activebackground="#35A85F", font=("Segoe UI", 10, "bold"),
        )
        self.button.pack(anchor="e", padx=20, pady=(0, 15))
        self.window.update_idletasks()
        w = min(470, self.window.winfo_screenwidth() - 24)
        h = min(300, self.window.winfo_screenheight() - 48)
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        x = max(12, min(self.parent.winfo_rootx() + (self.parent.winfo_width() - w) // 2, sw - w - 12))
        y = max(12, min(self.parent.winfo_rooty() + (self.parent.winfo_height() - h) // 2, sh - h - 12))
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.minsize(min(w, 300), min(h, 180))
        self.window.lift()
        self.window.attributes("-topmost", True)

    def _set_status(self, text):
        if self.status and self.status.winfo_exists():
            self.status.config(text=text)

    def _dismiss(self):
        if not self.locked or scan_disallowed_apps():
            if self.button and self.button.winfo_exists():
                self.button.config(state="disabled")
            return
        self.locked = False
        self._close_window()
        self.on_resume()

    def _close_window(self):
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = self.label = self.status = self.button = None

    def stop(self):
        self.stopped = True
        self.locked = False
        if self.after_id:
            try:
                self.parent.after_cancel(self.after_id)
            except tk.TclError:
                pass
        if self.close_id:
            try:
                self.parent.after_cancel(self.close_id)
            except tk.TclError:
                pass
        self._close_window()
