"""Streaming AI hint panel shared by the math games."""
import threading
import tkinter as tk

from mathix.ai.ollama_client import ai_stream_chat


class GameAIHint:
    """Show AI-chat-style thinking status and a large, scrollable live answer."""

    def __init__(self, parent, button, background="#101820", placement="pack"):
        self.parent = parent
        self.button = button
        self.placement = placement
        self.running = False
        self.stop_event = None
        self.thought_size = 0
        self.generation = 0

        self.frame = tk.Frame(parent, bg=background)
        self.think_panel = tk.Frame(
            self.frame, bg="#2B1E40", highlightthickness=1,
            highlightbackground="#9B6BCE",
        )
        tk.Label(
            self.think_panel, text="DÜŞÜNME ÖZETİ",
            font=("Segoe UI", 10, "bold"), fg="#D9B8FF", bg="#2B1E40",
        ).pack(anchor="w", padx=12, pady=(8, 2))
        self.think_label = tk.Label(
            self.think_panel, text="Sorudaki bilgileri inceliyorum…",
            font=("Segoe UI", 13), fg="#F1E8FF", bg="#2B1E40",
            justify="left", anchor="w", wraplength=520,
        )
        self.think_label.pack(fill="x", padx=12, pady=(0, 9))

        self.answer_panel = tk.Frame(
            self.frame, bg="#183528", highlightthickness=1,
            highlightbackground="#3AA66B",
        )
        tk.Label(
            self.answer_panel, text="AI İPUCU",
            font=("Segoe UI", 10, "bold"), fg="#72E39B", bg="#183528",
        ).pack(anchor="w", padx=12, pady=(8, 2))
        text_row = tk.Frame(self.answer_panel, bg="#183528")
        text_row.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.answer = tk.Text(
            text_row, width=62, height=5, wrap="word", font=("Segoe UI", 13),
            fg="#E8FFF0", bg="#183528", insertbackground="#E8FFF0",
            relief="flat", padx=5, pady=3, spacing1=2, spacing3=2,
        )
        scrollbar = tk.Scrollbar(text_row, command=self.answer.yview)
        self.answer.configure(yscrollcommand=scrollbar.set)
        self.answer.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _show(self):
        if self.placement == "place":
            self.frame.place(x=220, y=450, width=560, height=178)
        else:
            self.frame.pack(fill="x", padx=16, pady=(4, 10))

    def hide(self):
        self.generation += 1
        if self.stop_event:
            self.stop_event.set()
        self.running = False
        try:
            self.frame.pack_forget()
            self.frame.place_forget()
        except tk.TclError:
            pass

    def start(self, prompt):
        if self.running:
            return
        self.running = True
        self.generation += 1
        generation = self.generation
        self.thought_size = 0
        self.stop_event = threading.Event()
        self.think_label.config(text="Sorudaki bilgileri inceliyorum…")
        self.answer.delete("1.0", "end")
        self.answer_panel.pack_forget()
        self.think_panel.pack(fill="x", padx=4, pady=4)
        self._show()
        self.button.config(state="disabled", text="⏳ Düşünüyor…")

        messages = [
            {"role": "system", "content": (
                "Sen MATHİX matematik oyunundaki AI öğretmensin. Türkçe, "
                "sıcak ve anlaşılır konuş. Soruyu kısa ve doğru biçimde "
                "çöz, gerekli işlemleri anlaşılır şekilde göster ve doğru "
                "sonucu açıkça yaz. Sonucu saklama veya yalnızca ipucu verip "
                "öğrenciden kendisinin bulmasını isteme. Gereksiz uzatma."
            )},
            {"role": "user", "content": prompt},
        ]

        def ui(callback, *args, **kwargs):
            try:
                if self.parent.winfo_exists():
                    self.parent.after(
                        0, lambda: callback(*args, **kwargs)
                        if self.generation == generation else None
                    )
            except tk.TclError:
                pass

        def on_thinking(part):
            self.thought_size += len(part)
            if self.thought_size < 120:
                status = "Sorudaki bilgileri ve ne istendiğini inceliyorum…"
            elif self.thought_size < 420:
                status = "Uygun çözüm yolunu belirliyorum…"
            else:
                status = "İşlem adımlarını ve ipucunu kontrol ediyorum…"
            ui(self.think_label.config, text=status)

        def on_chunk(chunk):
            ui(self._append, chunk)

        def on_done(_full_text, _stopped):
            ui(self._finish)

        def on_error(error):
            ui(self._show_error, error)

        ai_stream_chat(
            "gemma4:e4b", messages, on_chunk, on_done, on_error,
            self.stop_event, on_thinking=on_thinking,
        )

    def _append(self, chunk):
        if not self.running:
            return
        if self.think_panel.winfo_manager():
            self.think_panel.pack_forget()
        if not self.answer_panel.winfo_manager():
            self.answer_panel.pack(fill="both", expand=True, padx=4, pady=4)
        self.answer.insert("end", chunk)
        self.answer.see("end")

    def _finish(self):
        self.running = False
        self.think_panel.pack_forget()
        if not self.answer_panel.winfo_manager():
            self.answer_panel.pack(fill="both", expand=True, padx=4, pady=4)
        if not self.answer.get("1.0", "end-1c").strip():
            self.answer.insert("end", "Yanıt üretilemedi. Tekrar deneyebilirsin.")
        self.answer.see("end")
        self.button.config(state="normal", text="💡 AI İpucu")

    def _show_error(self, error):
        self._append(f"İpucu alınamadı: {error}")
        self._finish()
