"""Lightweight, dependency-free chiptune loops for the game screens."""
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave


_TRACKS = {
    "mario": ([60, 64, 67, 72, 67, 64, 62, 65, 69, 74, 69, 65], 132),
    "snake": ([52, 55, 59, 64, 59, 55, 50, 54, 57, 62, 57, 54], 108),
    "space": ([48, 55, 60, 67, 63, 60, 55, 63, 58, 65, 70, 77], 116),
    "race": ([67, 71, 74, 79, 76, 74, 71, 83, 79, 76, 74, 71], 156),
}


def _make_track(name):
    notes, bpm = _TRACKS[name]
    sample_rate = 22050
    note_seconds = 60 / bpm / 2
    frames = bytearray()
    for index, midi in enumerate(notes * 2):
        frequency = 440 * (2 ** ((midi - 69) / 12))
        count = int(sample_rate * note_seconds)
        for i in range(count):
            t = i / sample_rate
            # A soft square-like lead over a quiet fifth gives each game a
            # recognizable, distinct arcade loop without extra audio assets.
            fade = min(1.0, i / 180, (count - i) / 500)
            lead = math.sin(2 * math.pi * frequency * t)
            overtone = math.sin(2 * math.pi * frequency * 2 * t) * 0.22
            bass = math.sin(2 * math.pi * frequency / 2 * t) * 0.18
            value = int(max(-1, min(1, (lead + overtone + bass) * fade * 0.34)) * 32767)
            frames.extend(struct.pack("<h", value))
    handle = tempfile.NamedTemporaryFile(prefix=f"mathix_{name}_", suffix=".wav", delete=False)
    handle.close()
    with wave.open(handle.name, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(frames)
    return handle.name


class GameMusic:
    """Loop game-specific music; pause it while a math question is visible."""

    def __init__(self, track):
        self.path = _make_track(track)
        with wave.open(self.path, "rb") as audio:
            self._pcm = audio.readframes(audio.getnframes())
            self._sample_rate = audio.getframerate()
            self._channels = audio.getnchannels()
        self._stop = threading.Event()
        self._worker = None
        self._process = None
        self._lock = threading.Lock()
        self._backends = self._find_backends()
        self._backend = self._backends[0] if self._backends else None
        self._bound_widget = None
        if self._backend:
            self.resume()

    def attach(self, widget):
        self._bound_widget = widget
        widget.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is self._bound_widget:
            self.stop()

    @staticmethod
    def _find_backends():
        if sys.platform == "win32":
            return ["winsound"]
        if sys.platform.startswith("linux"):
            # Prefer the desktop audio server, then ALSA. ffplay is a fallback
            # because some builds exist without a working SDL audio device.
            order = ("paplay", "aplay", "ffplay")
        else:
            order = ("ffplay", "afplay")
        return [name for name in order if shutil.which(name)]

    def _player_command(self, backend):
        if backend == "paplay":
            return [backend, "--raw", "--format=s16le", "--rate",
                    str(self._sample_rate), "--channels", str(self._channels)]
        if backend == "aplay":
            return [backend, "-q", "-t", "raw", "-f", "S16_LE", "-r",
                    str(self._sample_rate), "-c", str(self._channels), "-"]
        return [backend, "-nodisp", "-autoexit", "-loglevel", "error",
                "-f", "s16le", "-ar", str(self._sample_rate), "-ac",
                str(self._channels), "-i", "pipe:0"]

    def _loop(self):
        while not self._stop.is_set():
            for backend in self._backends:
                if self._stop.is_set():
                    return
                process = None
                try:
                    if backend == "winsound":
                        import winsound
                        winsound.PlaySound(
                            self.path, winsound.SND_FILENAME | winsound.SND_ASYNC
                            | winsound.SND_LOOP
                        )
                        while not self._stop.wait(0.2):
                            pass
                        winsound.PlaySound(None, winsound.SND_PURGE)
                        return

                    if backend == "afplay":
                        process = subprocess.Popen(
                            [backend, self.path], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        self._process = process
                        while process.poll() is None and not self._stop.wait(0.1):
                            pass
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=1)
                        if self._stop.is_set():
                            return
                        # afplay is one-shot; retry the file if it ended normally.
                        continue

                    process = subprocess.Popen(
                        self._player_command(backend), stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    self._process = process
                    # Catch missing devices / unavailable sound servers before
                    # entering the stream loop, then fall through to another player.
                    time.sleep(0.25)
                    if process.poll() is not None:
                        continue
                    self._backend = backend
                    cursor = 0
                    chunk_size = 16_384
                    while not self._stop.is_set() and process.poll() is None:
                        end = min(cursor + chunk_size, len(self._pcm))
                        # Write directly to the pipe descriptor. BufferedWriter
                        # can otherwise emit an ignored BrokenPipeError while
                        # Python finalizes it after the player exits.
                        payload = memoryview(self._pcm)[cursor:end]
                        fd = process.stdin.fileno()
                        while payload and not self._stop.is_set():
                            written = os.write(fd, payload)
                            payload = payload[written:]
                        cursor = 0 if end >= len(self._pcm) else end
                    if self._stop.is_set():
                        return
                except (OSError, ValueError, subprocess.SubprocessError):
                    if self._stop.is_set():
                        return
                finally:
                    if process and process.stdin:
                        try:
                            process.stdin.close()
                        except (BrokenPipeError, OSError, ValueError):
                            pass
                    if process and process.poll() is None:
                        try:
                            process.terminate()
                            process.wait(timeout=1)
                        except (OSError, subprocess.SubprocessError):
                            process.kill()
                    if self._process is process:
                        self._process = None
                # A selected stream player died. Try the next installed backend.
            if not self._stop.wait(1.0):
                continue

    def resume(self):
        if not self._backend:
            return
        if self._worker and self._worker.is_alive() and self._stop.is_set():
            self._worker.join(timeout=1)
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()

    def pause(self):
        self._stop.set()
        process = self._process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        if process and process.stdin:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        worker = self._worker
        if worker and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=1)

    def stop(self):
        self.pause()
        try:
            os.unlink(self.path)
        except OSError:
            pass
