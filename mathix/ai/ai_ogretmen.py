"""MATHİX — AI Öğretmen sohbet ekranı (gerçek zamanlı stream)."""
import threading
import tkinter as tk
from tkinter import messagebox
from uuid import uuid4

from mathix.config import (
    BG_COLOR, CARD_COLOR, CARD_LIGHT, TEXT_COLOR, SECONDARY_TEXT,
    BLUE, BLUE_ACTIVE, GREEN_ACTIVE, RED,
)
from mathix.ui.widgets import HoverButton
from mathix.ai.ollama_client import ollama_modellerini_al, ai_stream_chat
from mathix.ai.cloud_client import ai_cloud_chat, DEFAULT_MODELS
from mathix.ai import sohbet_gecmisi


# ==============================================================================
# AI ÖĞRETMEN EKRANI
# ==============================================================================
class AIOgretmenFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_COLOR)
        self.parent = parent
        self.student_grade = parent.active_student["sinif"]
        self.screen_alive = True
        self.streaming = False
        self.auto_scroll = False
        self._scroll_bindtag = f"MATHIXChatScroll{id(self)}"
        self._scroll_sequences = ("<MouseWheel>", "<Button-4>", "<Button-5>")
        self.stop_event = threading.Event()
        self.history = []
        self.active_chat_id = None
        self._history_window = None
        self._thinking_widgets = {}
        self.model_var = tk.StringVar(value="ogretmen:latest")
        self.cloud_profiles = {}
        self.active_provider = None

        self.setup_ui()
        self.bind("<Destroy>", self._on_frame_destroy, add="+")
        self.welcome_message()
        threading.Thread(target=self.modelleri_yukle, daemon=True).start()

    # ------------------------------------------------------------------ UI --
    def setup_ui(self):
        top = tk.Frame(self, bg=BG_COLOR, height=58)
        top.pack(fill="x", padx=18, pady=(12, 4))
        top.pack_propagate(False)

        title_frame = tk.Frame(top, bg=BG_COLOR)
        title_frame.pack(side="left", fill="y")
        tk.Label(title_frame, text="MATHİX AI",
                 font=("Arial", 21, "bold"),
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w")
        self.subtitle = tk.Label(
            title_frame,
            text=f"AI Öğretmen  •  {self.student_grade}. Sınıf",
            font=("Arial", 9), fg=SECONDARY_TEXT, bg=BG_COLOR,
        )
        self.subtitle.pack(anchor="w")

        right_top = tk.Frame(top, bg=BG_COLOR)
        right_top.pack(side="right", fill="y")

        self.status_dot = tk.Label(right_top, text="●",
                                    font=("Arial", 12, "bold"),
                                    fg=GREEN_ACTIVE, bg=BG_COLOR)
        self.status_dot.pack(side="left", padx=(0, 4))

        self.status_label = tk.Label(right_top, text="Ollama kontrol ediliyor...",
                                      font=("Arial", 9, "bold"),
                                      fg=SECONDARY_TEXT, bg=BG_COLOR)
        self.status_label.pack(side="left", padx=(0, 10))

        self.model_menu = tk.OptionMenu(right_top, self.model_var, "ogretmen:latest")
        self.model_menu.config(
            font=("Arial", 9, "bold"), bg=CARD_COLOR, fg=TEXT_COLOR,
            activebackground=CARD_LIGHT, activeforeground=TEXT_COLOR,
            relief="flat", highlightthickness=0, width=17, cursor="hand2",
        )
        self.model_menu["menu"].config(
            bg=CARD_COLOR, fg=TEXT_COLOR,
            activebackground=BLUE, font=("Arial", 9),
        )
        self.model_menu.pack(side="left")

        self.api_btn = tk.Button(
            right_top, text="＋ API Ekle", font=("Arial", 9, "bold"),
            bg="#263A52", fg=TEXT_COLOR, activebackground="#385778",
            relief="flat", bd=0, padx=8, cursor="hand2",
            command=self._api_ekle,
        )
        self.api_btn.pack(side="left", padx=(5, 0))

        refresh_btn = tk.Button(
            right_top, text="↻", font=("Arial", 12, "bold"),
            bg=CARD_COLOR, fg=TEXT_COLOR, activebackground=CARD_LIGHT,
            relief="flat", bd=0, width=2, cursor="hand2",
            command=lambda: threading.Thread(
                target=self.modelleri_yukle, daemon=True
            ).start(),
        )
        refresh_btn.pack(side="left", padx=(5, 0))

        # ---- Sohbet alanı ----
        chat_outer = tk.Frame(self, bg=CARD_COLOR)
        chat_outer.pack(fill="both", expand=True, padx=18, pady=(4, 8))

        self.chat_canvas = tk.Canvas(chat_outer, bg=CARD_LIGHT,
                                      highlightthickness=0, bd=0)
        chat_scroll = tk.Scrollbar(
            chat_outer, orient="vertical", command=self._scrollbar_action,
            bg=CARD_COLOR, troughcolor=CARD_COLOR, relief="flat", width=8,
        )
        chat_scroll.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.chat_canvas.configure(yscrollcommand=chat_scroll.set)

        self.messages_frame = tk.Frame(self.chat_canvas, bg=CARD_LIGHT)
        self.canvas_window = self.chat_canvas.create_window(
            (0, 0), window=self.messages_frame, anchor="nw"
        )

        self.messages_frame.bind("<Configure>", self._chat_content_changed)
        self._enable_chat_scrolling(self.chat_canvas)
        self._enable_chat_scrolling(self.messages_frame)
        self.chat_canvas.bind(
            "<Configure>",
            lambda e: self.chat_canvas.itemconfigure(
                self.canvas_window, width=e.width
            ),
        )

        for sequence in self._scroll_sequences:
            self.bind_class(self._scroll_bindtag, sequence, self._mousewheel_scroll)

        # ---- Giriş kutusu ----
        composer = tk.Frame(self, bg=BG_COLOR)
        composer.pack(fill="x", padx=18, pady=(0, 8))

        prompt_box_frame = tk.Frame(
            composer, bg=CARD_COLOR,
            highlightthickness=1, highlightbackground="#2D4053",
        )
        prompt_box_frame.pack(fill="x")

        self.prompt_entry = tk.Text(
            prompt_box_frame, height=3, font=("Arial", 11),
            bg=CARD_LIGHT, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat", wrap="word", padx=10, pady=8,
        )
        self.prompt_entry.pack(side="left", fill="both", expand=True,
                                padx=(2, 0), pady=2)

        action_frame = tk.Frame(prompt_box_frame, bg=CARD_LIGHT)
        action_frame.pack(side="right", fill="y", padx=6, pady=5)

        self.stop_btn = tk.Button(
            action_frame, text="■", font=("Arial", 11, "bold"),
            bg=RED, fg=TEXT_COLOR, relief="flat", width=4,
            state="disabled", cursor="hand2",
            command=lambda: self.stop_event.set(),
        )
        self.stop_btn.pack(pady=(0, 5))

        self.send_btn = tk.Button(
            action_frame, text="➤", font=("Arial", 16, "bold"),
            bg=BLUE, fg=TEXT_COLOR, activebackground=BLUE_ACTIVE,
            relief="flat", width=4, cursor="hand2", command=self.gonder,
        )
        self.send_btn.pack()

        self.prompt_entry.bind("<Return>", self._enter_ile_gonder)
        tk.Label(
            composer, text="Enter: gönder  •  Shift+Enter: yeni satır",
            font=("Arial", 8), fg=SECONDARY_TEXT, bg=BG_COLOR,
        ).pack(anchor="e", pady=(3, 0))

        # ---- Alt butonlar ----
        footer = tk.Frame(self, bg=BG_COLOR)
        footer.pack(fill="x", padx=18, pady=(0, 8))

        HoverButton(
            footer, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
            text="＋ Yeni Sohbet", command=self.temizle, width=13,
        ).pack(side="left", padx=(0, 5))
        HoverButton(
            footer, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
            text="◷ Sohbet Geçmişi", command=self.sohbet_gecmisini_ac, width=16,
        ).pack(side="left", padx=(0, 5))

        for lbl, txt in [
            ("💡 İpucu", "Bu matematik sorusunda nasıl bir yol izlemeliyim? "
                        "Bana sadece ipucu ver."),
            ("📚 Konu Özeti",
             f"{self.student_grade}. sınıf matematik önemli "
             "konularını özetle."),
            ("🧩 Örnek Soru",
             "Bana seviyeme uygun bir matematik sorusu sor ve cevabımı bekle."),
        ]:
            HoverButton(
                footer, bg_color=CARD_COLOR, active_bg=CARD_LIGHT,
                text=lbl, command=lambda t=txt: self.hizli_soru(t),
            ).pack(side="left", padx=3)

        HoverButton(
            footer, bg_color=BG_COLOR, active_bg=CARD_COLOR,
            text="← Ana Menü", command=self.geri_don, width=15,
        ).pack(side="right")

    # --------------------------------------------------------------- kaydırma --
    def _enable_chat_scrolling(self, widget):
        tags = widget.bindtags()
        if self._scroll_bindtag not in tags:
            widget.bindtags((self._scroll_bindtag,) + tags)

    def _mousewheel_scroll(self, event):
        if not self.screen_alive:
            return
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = getattr(event, "delta", 0)
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        self.auto_scroll = False
        self.chat_canvas.yview_scroll(units, "units")
        return "break"

    def _scrollbar_action(self, *args):
        self.auto_scroll = False
        self.chat_canvas.yview(*args)

    def _on_frame_destroy(self, event):
        if event.widget is not self:
            return
        self.screen_alive = False
        self.stop_event.set()
        for sequence in self._scroll_sequences:
            try:
                self.unbind_class(self._scroll_bindtag, sequence)
            except tk.TclError:
                pass

    def _chat_content_changed(self, _event=None):
        if not self.screen_alive:
            return
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self._scroll_chat_to_bottom()

    def _scroll_chat_to_bottom(self, force=False):
        if not self.screen_alive or (not self.auto_scroll and not force):
            return
        try:
            self.chat_canvas.after_idle(
                lambda final=force: self.chat_canvas.yview_moveto(1.0)
                if self.screen_alive and (self.auto_scroll or final) else None
            )
        except tk.TclError:
            pass

    # --------------------------------------------------------- model yükleme --
    def modelleri_yukle(self):
        models = ollama_modellerini_al()
        names = [m.get("name") for m in models if m.get("name")]
        if self.screen_alive:
            self.parent.after(0, lambda: self.update_models_ui(names))

    def _api_ekle(self):
        dialog = tk.Toplevel(self)
        dialog.title("Bulut AI API Ekle")
        dialog.configure(bg=CARD_COLOR)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        tk.Label(dialog, text="ChatGPT veya Gemini API bağlantısı",
                 font=("Arial", 14, "bold"), fg=TEXT_COLOR,
                 bg=CARD_COLOR).pack(anchor="w", padx=20, pady=(18, 10))
        provider_var = tk.StringVar(value="ChatGPT")
        model_var = tk.StringVar(value=DEFAULT_MODELS[provider_var.get()])
        key_var = tk.StringVar()

        def provider_changed(value):
            model_var.set(self.cloud_profiles.get(value, {}).get(
                "model", DEFAULT_MODELS[value]))
            key_var.set(self.cloud_profiles.get(value, {}).get("api_key", ""))

        form = tk.Frame(dialog, bg=CARD_COLOR)
        form.pack(fill="x", padx=20)

        tk.Label(form, text="Sağlayıcı", fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).grid(row=0, column=0, sticky="w", pady=7)
        provider_menu = tk.OptionMenu(
            form, provider_var, "ChatGPT", "Gemini",
            command=provider_changed,
        )
        provider_menu.config(bg="#263A52", fg=TEXT_COLOR, bd=0,
                             highlightthickness=0, width=23)
        provider_menu.grid(row=0, column=1, sticky="ew", pady=7)

        tk.Label(form, text="Model", fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).grid(row=1, column=0, sticky="w", pady=7)
        model_entry = tk.Entry(form, textvariable=model_var, width=34,
                               bg=CARD_LIGHT, fg=TEXT_COLOR,
                               insertbackground=TEXT_COLOR, relief="flat")
        model_entry.grid(row=1, column=1, sticky="ew", ipady=7, pady=7)

        tk.Label(form, text="API anahtarı", fg=SECONDARY_TEXT,
                 bg=CARD_COLOR).grid(row=2, column=0, sticky="w", pady=7)
        key_entry = tk.Entry(form, textvariable=key_var, width=34, show="•",
                             bg=CARD_LIGHT, fg=TEXT_COLOR,
                             insertbackground=TEXT_COLOR, relief="flat")
        key_entry.grid(row=2, column=1, sticky="ew", ipady=7, pady=7)
        form.columnconfigure(1, weight=1)

        saved = self.cloud_profiles.get(provider_var.get())
        if saved:
            key_var.set(saved["api_key"])
        tk.Label(dialog,
                 text="Anahtar yalnızca bu açık oturumda bellekte tutulur; proje dosyasına kaydedilmez.",
                 font=("Arial", 9), fg=SECONDARY_TEXT, bg=CARD_COLOR,
                 wraplength=440, justify="left").pack(anchor="w", padx=20, pady=(6, 12))

        actions = tk.Frame(dialog, bg=CARD_COLOR)
        actions.pack(fill="x", padx=20, pady=(0, 18))

        def save_profile():
            provider = provider_var.get()
            key = key_var.get().strip()
            model = model_var.get().strip()
            if not key or not model:
                key_entry.focus_set()
                return
            self.cloud_profiles[provider] = {"api_key": key, "model": model}
            self.active_provider = provider
            self.api_btn.config(text=f"✓ {provider}")
            self.set_status(f"{provider} API hazır", GREEN_ACTIVE)
            dialog.destroy()

        tk.Button(actions, text="Vazgeç", command=dialog.destroy,
                  bg="#263A52", fg=TEXT_COLOR, relief="flat",
                  padx=12, pady=7, cursor="hand2").pack(side="left")
        tk.Button(actions, text="API'yi Kaydet ve Kullan",
                  command=save_profile, bg=BLUE, fg="white",
                  activebackground=BLUE_ACTIVE, relief="flat",
                  padx=12, pady=7, cursor="hand2").pack(side="right")

    def update_models_ui(self, names):
        menu = self.model_menu["menu"]
        menu.delete(0, "end")
        if not names:
            self.model_var.set("ogretmen:latest")
            self.set_status("Model bulunamadı", RED)
            return
        self.model_var.set(
            "ogretmen:latest" if "ogretmen:latest" in names else names[0]
        )
        for n in names:
            menu.add_command(label=n, command=lambda name=n: self._select_ollama_model(name))

    def _select_ollama_model(self, name):
        self.active_provider = None
        self.model_var.set(name)
        self.api_btn.config(text="＋ API Ekle")
        self.set_status("Ollama modeli seçildi", GREEN_ACTIVE)

    def set_status(self, text, color):
        self.status_label.config(text=text, fg=color)
        self.status_dot.config(fg=color)

    # ------------------------------------------------------------- mesajlar --
    def add_message(self, role, text="", live=False):
        if not self.screen_alive:
            return None
        outer = tk.Frame(self.messages_frame, bg=CARD_LIGHT)
        self._enable_chat_scrolling(outer)
        outer.pack(fill="x", padx=14, pady=(8, 3))

        is_user = (role == "user")
        accent = BLUE if is_user else GREEN_ACTIVE
        bubble_bg = "#1B3558" if is_user else "#183528"
        side = "right" if is_user else "left"

        bubble = tk.Frame(outer, bg=bubble_bg,
                           highlightthickness=1, highlightbackground=accent)
        self._enable_chat_scrolling(bubble)
        if is_user:
            bubble.pack(side=side, padx=2, pady=1)

        thinking_panel = None
        thinking_label = None
        if live and not is_user:
            thinking_panel = tk.Frame(
                outer, bg="#2B1E40", highlightthickness=1,
                highlightbackground="#9B6BCE",
            )
            self._enable_chat_scrolling(thinking_panel)
            thinking_heading = tk.Label(
                thinking_panel, text="DÜŞÜNME ÖZETİ",
                font=("Arial", 8, "bold"), fg="#D9B8FF", bg="#2B1E40",
            )
            self._enable_chat_scrolling(thinking_heading)
            thinking_heading.pack(anchor="w", padx=11, pady=(7, 0))
            thinking_label = tk.Label(
                thinking_panel, text="", font=("Arial", 10), fg="#F1E8FF",
                bg="#2B1E40", justify="left", wraplength=620,
                padx=11, pady=7,
            )
            self._enable_chat_scrolling(thinking_label)
            thinking_label.pack(anchor="w")

        heading = tk.Label(
            bubble, text="SEN" if is_user else "AI ÖĞRETMEN",
            font=("Arial", 8, "bold"), fg=accent, bg=bubble_bg,
        )
        self._enable_chat_scrolling(heading)
        heading.pack(anchor="w", padx=11, pady=(7, 0))

        msg_lbl = tk.Label(
            bubble, text=text, font=("Arial", 11), fg=TEXT_COLOR,
            bg=bubble_bg, justify="left", wraplength=635, padx=11, pady=7,
        )
        self._enable_chat_scrolling(msg_lbl)
        msg_lbl.pack(anchor="w")
        if not is_user:
            bubble.pack(anchor="w", padx=2, pady=1)

        if live:
            msg_lbl.config(text="▌")
            if thinking_panel is not None:
                self._thinking_widgets[msg_lbl] = {
                    "panel": thinking_panel, "label": thinking_label, "size": 0,
                }
        self._scroll_chat_to_bottom()
        return msg_lbl

    def welcome_message(self):
        self.add_message(
            "assistant",
            f"Selam! 👋 Ben MATHİX AI Öğretmen. {self.student_grade}. sınıf "
            "seviyene göre yardımcı olacağım.\n"
            "Matematik sorularını birlikte çözebiliriz. "
            "Cevaplar gerçek zamanlı akacaktır.",
        )

    # -------------------------------------------------------------- eylemler --
    def _mesajlari_temizle(self):
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        self._thinking_widgets.clear()
        self.chat_canvas.configure(scrollregion=(0, 0, 0, 0))
        self.chat_canvas.yview_moveto(0.0)

    def _aktif_sohbeti_kaydet(self):
        if not any(m.get("role") == "user" for m in self.history):
            return
        if not self.active_chat_id:
            self.active_chat_id = str(uuid4())
        try:
            sohbet_gecmisi.save_chat(
                self.parent.active_student["id"], self.active_chat_id, self.history
            )
            return True
        except OSError:
            self.set_status("Sohbet geçmişi kaydedilemedi", RED)
            return False

    def temizle(self):
        """Mevcut sohbeti geçmişe kaydet ve boş bir sohbet başlat."""
        if self.streaming:
            return
        self._aktif_sohbeti_kaydet()
        self.history = []
        self.active_chat_id = None
        self.prompt_entry.delete("1.0", "end")
        self.auto_scroll = True
        self._mesajlari_temizle()
        self.welcome_message()
        self.set_status("Yeni sohbet hazır", GREEN_ACTIVE)
        self.chat_canvas.after_idle(self._yeni_sohbet_konumlandir)

    def _yeni_sohbet_konumlandir(self):
        if not self.screen_alive:
            return
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(0.0)
        self.auto_scroll = False

    def sohbet_gecmisini_ac(self):
        if self.streaming:
            return
        self._aktif_sohbeti_kaydet()
        if self._history_window and self._history_window.winfo_exists():
            self._history_window.lift()
            self._gecmis_listesini_yenile()
            return

        window = tk.Toplevel(self)
        self._history_window = window
        window.title("AI Sohbet Geçmişi")
        window.configure(bg=BG_COLOR)
        window.transient(self.winfo_toplevel())
        window.geometry("620x440")
        window.minsize(480, 320)

        tk.Label(window, text="Sohbet geçmişi", font=("Arial", 16, "bold"),
                 fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(window, text="Bir konuşmayı açabilir, seçileni veya tüm geçmişi silebilirsin.",
                 font=("Arial", 9), fg=SECONDARY_TEXT, bg=BG_COLOR).pack(
                     anchor="w", padx=18, pady=(0, 10))

        list_frame = tk.Frame(window, bg=CARD_COLOR)
        list_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self._history_list = tk.Listbox(
            list_frame, bg=CARD_LIGHT, fg=TEXT_COLOR,
            selectbackground=BLUE, selectforeground="white",
            font=("Arial", 10), relief="flat", activestyle="none",
        )
        scroll = tk.Scrollbar(list_frame, orient="vertical",
                              command=self._history_list.yview)
        self._history_list.configure(yscrollcommand=scroll.set)
        self._history_list.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scroll.pack(side="right", fill="y", pady=5)
        self._history_list.bind("<Double-Button-1>", lambda _e: self._gecmis_sohbetini_ac())

        actions = tk.Frame(window, bg=BG_COLOR)
        actions.pack(fill="x", padx=18, pady=(0, 16))
        tk.Button(actions, text="Aç", command=self._gecmis_sohbetini_ac,
                  bg=BLUE, fg="white", relief="flat", padx=16, pady=7).pack(side="left")
        tk.Button(actions, text="Seçileni Sil", command=self._gecmis_sohbetini_sil,
                  bg="#8B3338", fg="white", relief="flat", padx=12, pady=7).pack(
                      side="left", padx=7)
        tk.Button(actions, text="Tüm Geçmişi Temizle", command=self._tum_gecmisi_sil,
                  bg="#67272B", fg="white", relief="flat", padx=12, pady=7).pack(side="left")
        tk.Button(actions, text="Kapat", command=window.destroy,
                  bg=CARD_COLOR, fg=TEXT_COLOR, relief="flat", padx=16, pady=7).pack(side="right")
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        window.bind("<Destroy>", self._gecmis_penceresi_kapat, add="+")
        self._gecmis_listesini_yenile()
        window.grab_set()

    def _gecmis_penceresi_kapat(self, event):
        if event.widget is self._history_window:
            self._history_window = None

    def _gecmis_listesini_yenile(self):
        if not self._history_window or not self._history_window.winfo_exists():
            return
        self._history_chats = sohbet_gecmisi.load_chats(self.parent.active_student["id"])
        self._history_list.delete(0, "end")
        for chat in self._history_chats:
            updated = str(chat.get("updated_at", "")).replace("T", " ")[:16]
            title = str(chat.get("title", "Yeni sohbet")).replace("\n", " ")
            self._history_list.insert("end", f"{title}    ·    {updated}")
        if not self._history_chats:
            self._history_list.insert("end", "Henüz kaydedilmiş sohbet yok.")

    def _gecmis_secili_kayit(self):
        selection = self._history_list.curselection()
        if not selection or selection[0] >= len(self._history_chats):
            return None
        return self._history_chats[selection[0]]

    def _gecmis_sohbetini_ac(self):
        chat = self._gecmis_secili_kayit()
        if not chat:
            return
        if self.streaming:
            return
        self._aktif_sohbeti_kaydet()
        loaded = sohbet_gecmisi.get_chat(
            self.parent.active_student["id"], chat["id"]
        )
        if not loaded:
            self._gecmis_listesini_yenile()
            return
        self.active_chat_id = loaded["id"]
        self.history = list(loaded.get("messages", []))
        self.prompt_entry.delete("1.0", "end")
        self.auto_scroll = True
        self._mesajlari_temizle()
        for message in self.history:
            if message.get("role") in {"user", "assistant"}:
                self.add_message(message["role"], message.get("content", ""))
        self.set_status("Sohbet geçmişinden açıldı", GREEN_ACTIVE)
        self.chat_canvas.after_idle(self._sohbeti_sona_kaydir)
        if self._history_window and self._history_window.winfo_exists():
            self._history_window.destroy()

    def _sohbeti_sona_kaydir(self):
        if self.screen_alive:
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
            self.chat_canvas.yview_moveto(1.0)
            self.auto_scroll = False

    def _gecmis_sohbetini_sil(self):
        chat = self._gecmis_secili_kayit()
        if not chat:
            return
        title = str(chat.get("title", "Bu sohbet"))[:80]
        if not messagebox.askyesno("Sohbeti sil", f"‘{title}’ sohbeti silinsin mi?",
                                   parent=self._history_window):
            return
        try:
            deleted = sohbet_gecmisi.delete_chat(
                self.parent.active_student["id"], chat["id"]
            )
        except OSError:
            deleted = False
        if not deleted:
            messagebox.showerror(
                "Sohbet silinemedi", "Sohbet geçmişi dosyasına erişilemedi.",
                parent=self._history_window,
            )
            return
        if self.active_chat_id == chat["id"]:
            self.active_chat_id = None
            self.history = []
            self._mesajlari_temizle()
            self.welcome_message()
            self.chat_canvas.after_idle(self._yeni_sohbet_konumlandir)
        self._gecmis_listesini_yenile()

    def _tum_gecmisi_sil(self):
        if not messagebox.askyesno(
            "Tüm sohbet geçmişini sil",
            "Bu öğrencinin tüm kayıtlı AI sohbetleri kalıcı olarak silinsin mi?",
            parent=self._history_window,
        ):
            return
        if not sohbet_gecmisi.clear_chats(self.parent.active_student["id"]):
            messagebox.showerror(
                "Geçmiş temizlenemedi", "Sohbet geçmişi dosyası silinemedi.",
                parent=self._history_window,
            )
            return
        self.active_chat_id = None
        self.history = []
        self._mesajlari_temizle()
        self.welcome_message()
        self.chat_canvas.after_idle(self._yeni_sohbet_konumlandir)
        self._gecmis_listesini_yenile()

    def hizli_soru(self, text):
        self.prompt_entry.delete("1.0", "end")
        self.prompt_entry.insert("1.0", text)
        self.gonder()

    def _enter_ile_gonder(self, event):
        # Shift+Enter metin kutusunun normal davranisiyle alt satir acar.
        if event.state & 0x1:
            return None
        self.gonder()
        return "break"

    def gonder(self):
        if not self.screen_alive or self.streaming:
            return
        text = self.prompt_entry.get("1.0", "end-1c").strip()
        if not text:
            return
        self.prompt_entry.delete("1.0", "end")

        self.auto_scroll = True
        self.streaming = True
        self.add_message("user", text)
        assistant_bubble = self.add_message("assistant", "", live=True)
        self.history.append({"role": "user", "content": text})
        self._aktif_sohbeti_kaydet()

        self.stop_event = threading.Event()
        self.send_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.set_status("Cevap yazılıyor...", BLUE_ACTIVE)

        system_message = {
            "role": "system",
            "content": (
                "Sen MATHİX eğitim oyunundaki AI Öğretmensin. Karşındaki "
                f"öğrenci {self.student_grade}. sınıf "
                "seviyesinde. Türkçe konuş. Samimi, sabırlı ol ve adım adım "
                "açıkla."
            ),
        }
        conversation = [system_message] + self.history[-12:]

        def on_chunk(token):
            if self.screen_alive:
                try:
                    self.parent.after(0, lambda chunk=token: self._append_chunk(
                        assistant_bubble, chunk))
                except tk.TclError:
                    pass

        def on_done(full_text, stopped):
            if self.screen_alive:
                try:
                    self.parent.after(
                        0, lambda: self._finish_stream(assistant_bubble, full_text, stopped)
                    )
                except tk.TclError:
                    pass

        def on_thinking(thought):
            if self.screen_alive:
                try:
                    self.parent.after(0, lambda part=thought: self._append_thinking(
                        assistant_bubble, part))
                except tk.TclError:
                    pass

        def on_error(err):
            if self.screen_alive:
                try:
                    self.parent.after(0, lambda error=err: self._show_stream_error(
                        assistant_bubble, error))
                except tk.TclError:
                    pass

        provider = self.active_provider
        if provider:
            profile = self.cloud_profiles[provider]
            ai_cloud_chat(
                provider, profile["api_key"], profile["model"], conversation,
                on_chunk, on_done, on_error, self.stop_event,
                on_thinking=on_thinking,
            )
        else:
            ai_stream_chat(
                self.model_var.get(), conversation,
                on_chunk, on_done, on_error, self.stop_event,
                on_thinking=on_thinking,
            )

    def _append_thinking(self, bubble, thought):
        if not self.screen_alive:
            return
        widgets = self._thinking_widgets.get(bubble)
        if not widgets:
            return
        widgets["size"] += len(thought)
        progress = (
            "Sorudaki bilgileri ve ne istendiğini inceliyorum…"
            if widgets["size"] < 120 else
            "Uygun çözüm yolunu belirleyip işlemleri uyguluyorum…"
            if widgets["size"] < 420 else
            "İşlem adımlarını ve sonucu kontrol ediyorum…"
        )
        widgets["label"].config(text=progress)
        widgets["panel"].pack(fill="x", before=bubble, padx=2, pady=(1, 5))
        self._scroll_chat_to_bottom()

    def _append_chunk(self, bubble, chunk):
        if not self.screen_alive or not bubble.winfo_exists():
            return
        widgets = self._thinking_widgets.pop(bubble, None)
        if widgets:
            widgets["panel"].pack_forget()
        bubble.config(text=bubble.cget("text").rstrip("▌") + chunk + "▌")
        self._scroll_chat_to_bottom()

    def _finish_stream(self, bubble, full_text, stopped):
        if not self.screen_alive:
            return
        should_follow = self.auto_scroll
        self.auto_scroll = False
        self.streaming = False
        self.stop_btn.config(state="disabled")
        self.send_btn.config(state="normal")
        widgets = self._thinking_widgets.pop(bubble, None)
        if widgets:
            widgets["panel"].pack_forget()
        if bubble.winfo_exists():
            bubble.config(text=full_text.strip() if full_text else
                          ("Üretim durduruldu." if stopped else "Boş yanıt."))
        if full_text and not stopped:
            self.history.append({"role": "assistant", "content": full_text.strip()})
            self._aktif_sohbeti_kaydet()
        self.set_status("Hazır", GREEN_ACTIVE)
        self._scroll_chat_to_bottom(force=should_follow)

    def _show_stream_error(self, bubble, err):
        if not self.screen_alive:
            return
        should_follow = self.auto_scroll
        self.auto_scroll = False
        self.streaming = False
        self.stop_btn.config(state="disabled")
        self.send_btn.config(state="normal")
        widgets = self._thinking_widgets.pop(bubble, None)
        if widgets:
            widgets["panel"].pack_forget()
        provider_name = self.active_provider or "Ollama"
        if bubble.winfo_exists():
            bubble.config(text=f"⚠️ {provider_name} bağlantı hatası: {err}")
        self.set_status(f"{provider_name} Hatası", RED)
        self._scroll_chat_to_bottom(force=should_follow)

    def geri_don(self):
        self.screen_alive = False
        self.stop_event.set()
        from mathix.menu.menu import MainMenuFrame
        self.parent.show_frame(MainMenuFrame)
