"""MATHİX — Ana giriş noktası."""
import tkinter as tk

from mathix.config import BG_COLOR
from mathix.database import init_db
from mathix.auth import LoginFrame


class MathixApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MATHİX - Gelişmiş Matematik Platformu")
        self.geometry("1000x650")
        self.center_window(1000, 650)
        self.minsize(850, 550)
        self.resizable(True, True)
        self.configure(bg=BG_COLOR)
        self._base_tk_scaling = float(self.tk.call("tk", "scaling"))
        self._current_ui_factor = 1.0
        self._scale_job = None
        self.bind("<Configure>", self._schedule_ui_scale, add="+")

        self.oyun_ayarlari = {
            "soru_sayisi": 10,
            "sure_limiti": 0,
            "zorluk": "Orta",
            "sinif": 5,
            "mod": "Klasik",
        }
        self.current_frame = None
        self.active_student = None
        self.show_frame(LoginFrame)

    def _schedule_ui_scale(self, _event=None):
        if self._scale_job:
            try:
                self.after_cancel(self._scale_job)
            except tk.TclError:
                pass
        try:
            self._scale_job = self.after(140, self._apply_ui_scale)
        except tk.TclError:
            self._scale_job = None

    def _apply_ui_scale(self):
        self._scale_job = None
        if not self.winfo_exists():
            return
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        # Keep the interface proportional when the regular window is resized.
        factor = min(width / 1000, height / 650)
        factor = max(0.85, min(1.55, factor))
        if abs(factor - self._current_ui_factor) < 0.015:
            return
        self._current_ui_factor = factor
        self.tk.call("tk", "scaling", self._base_tk_scaling * factor)

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.geometry(f"{width}x{height}+{x}+{y-30}")

    def show_frame(self, frame_class, **kwargs):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_class(self, **kwargs)
        self.current_frame.pack(fill="both", expand=True)


if __name__ == "__main__":
    init_db()
    app = MathixApp()
    app.mainloop()
