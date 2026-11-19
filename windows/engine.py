"""Listening and translation engine for the Windows Translator app.

Microphone audio is cut into phrases at pauses. Each phrase goes through
Whisper (faster-whisper, runs offline on the laptop's CPU) twice: once to write
down the original Japanese or Portuguese, once to translate it to English.
Results come back to the UI through a queue as ("event", data) tuples.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16_000
BLOCK_SECONDS = 0.03                 # 30 ms microphone blocks
SENTENCE_PAUSE = 0.8                 # pause that ends a phrase (seconds)
MAX_PHRASE = 12.0                    # translate long speech every 12 s anyway
MIN_PHRASE = 0.4                     # ignore clicks and coughs shorter than this
PRE_ROLL = 0.3                       # keep a little audio from before speech started

LANGUAGES = {
    # key: (label, whisper code)
    "ja": ("Japanese", "ja"),
    "pt": ("Portuguese (Brazil)", "pt"),
    "auto": ("Detect automatically", None),
}

MODELS = {
    # key: (label, whisper model name, rough download size)
    "fast": ("Fast (lower accuracy)", "base", "150 MB"),
    "balanced": ("Balanced (recommended)", "small", "480 MB"),
    "best": ("Best (needs a fast laptop)", "medium", "1.5 GB"),
}


def model_folder() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "Translator", "models")
    os.makedirs(path, exist_ok=True)
    return path


def model_is_downloaded(model_key: str) -> bool:
    name = MODELS[model_key][1]
    root = model_folder()
    for entry in os.listdir(root):
        if entry.startswith("models--") and entry.endswith(f"faster-whisper-{name}"):
            snapshots = os.path.join(root, entry, "snapshots")
            if os.path.isdir(snapshots) and os.listdir(snapshots):
                return True
    return False


def load_model(model_key: str):
    from faster_whisper import WhisperModel

    name = MODELS[model_key][1]
    threads = max(1, (os.cpu_count() or 4) - 1)
    return WhisperModel(
        name,
        device="cpu",
        compute_type="int8",
        cpu_threads=threads,
        download_root=model_folder(),
    )


@dataclass
class Settings:
    language: str = "ja"
    model: str = "balanced"
    show_original: bool = True


# Phrases Whisper tends to invent from silence or noise.
_HALLUCINATIONS = {
    "thank you.", "thank you for watching.", "thanks for watching!",
    "thank you for watching!", "thanks for watching.", "you", ".", "bye.",
    "please subscribe.", "subtitles by the amara.org community",
    "ご視聴ありがとうございました", "ご視聴ありがとうございました。",
    "obrigado.", "obrigada.", "legendas pela comunidade amara.org",
}


def _clean(text: str) -> str:
    text = " ".join(text.split())
    if text.strip().lower() in _HALLUCINATIONS:
        return ""
    return text


class Engine:
    def __init__(self, events: "queue.Queue[tuple[str, object]]", settings: Settings):
        self.events = events
        self.settings = settings
        self._model = None
        self._model_key = None
        self._model_lock = threading.Lock()
        self._phrases: "queue.Queue[np.ndarray | None]" = queue.Queue()
        self._stream = None
        self._listening = False
        self._muted_until = 0.0
        self._worker = threading.Thread(target=self._translate_loop, daemon=True)
        self._worker.start()
        # Phrase splitting state (microphone thread only)
        self._buffer: list[np.ndarray] = []
        self._pre_roll: list[np.ndarray] = []
        self._in_speech = False
        self._silence = 0.0
        self._speech_len = 0.0
        self._noise_floor = 0.003

    # ---------- public API (UI thread) ----------

    @property
    def listening(self) -> bool:
        return self._listening

    def start(self) -> None:
        if self._listening:
            return
        import sounddevice as sd

        self._reset_phrase()
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=int(SAMPLE_RATE * BLOCK_SECONDS),
                callback=self._on_audio,
            )
            self._stream.start()
        except Exception as exc:  # no microphone, or blocked in Windows privacy settings
            self._stream = None
            self.events.put(("error", "Couldn't open the microphone. Check that one is plugged in and that "
                                      "Settings > Privacy & security > Microphone lets desktop apps use it.\n"
                                      f"({exc})"))
            return
        self._listening = True
        self.events.put(("listening", True))
        self.preload_model()

    def stop(self) -> None:
        if not self._listening:
            return
        self._listening = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._flush_phrase()
        self.events.put(("listening", False))

    def toggle(self) -> None:
        self.stop() if self._listening else self.start()

    def mute_for(self, seconds: float) -> None:
        """Ignore the microphone while the app reads English aloud."""
        self._muted_until = max(self._muted_until, time.monotonic() + seconds)

    def unmute(self) -> None:
        self._muted_until = 0.0

    def preload_model(self) -> None:
        threading.Thread(target=self._ensure_model, daemon=True).start()

    # ---------- microphone thread ----------

    def _reset_phrase(self) -> None:
        self._buffer = []
        self._pre_roll = []
        self._in_speech = False
        self._silence = 0.0
        self._speech_len = 0.0

    def _on_audio(self, indata, frames, time_info, status) -> None:
        block = indata[:, 0].copy()
        if time.monotonic() < self._muted_until:
            self._reset_phrase()
            self.events.put(("level", 0.0))
            return
        self._feed(block)

    def _feed(self, block: np.ndarray) -> None:
        """Split audio into phrases using loudness. Split out so it can be tested."""
        rms = float(np.sqrt(np.mean(block * block)) + 1e-9)
        dur = len(block) / SAMPLE_RATE
        self.events.put(("level", min(1.0, rms * 12)))

        threshold = max(0.008, self._noise_floor * 3.0)
        loud = rms > threshold
        if not self._in_speech:
            # Track background noise slowly while nobody is talking.
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * min(rms, 0.05)
            self._pre_roll.append(block)
            while len(self._pre_roll) * BLOCK_SECONDS > PRE_ROLL:
                self._pre_roll.pop(0)
            if loud:
                self._in_speech = True
                self._buffer = list(self._pre_roll)
                self._pre_roll = []
                self._speech_len = dur
                self._silence = 0.0
            return

        self._buffer.append(block)
        if loud:
            self._speech_len += dur
            self._silence = 0.0
        else:
            self._silence += dur
        total = sum(len(b) for b in self._buffer) / SAMPLE_RATE
        if self._silence >= SENTENCE_PAUSE or total >= MAX_PHRASE:
            self._flush_phrase()

    def _flush_phrase(self) -> None:
        if self._in_speech and self._speech_len >= MIN_PHRASE and self._buffer:
            self._phrases.put(np.concatenate(self._buffer))
            self.events.put(("busy", self._phrases.qsize()))
        self._reset_phrase()

    # ---------- translation thread ----------

    def _ensure_model(self):
        with self._model_lock:
            key = self.settings.model
            if self._model is not None and self._model_key == key:
                return self._model
            label, name, size = MODELS[key]
            if not model_is_downloaded(key):
                self.events.put(("status", f"Downloading the {name} speech model ({size}, one time only)..."))
            else:
                self.events.put(("status", "Loading the speech model..."))
            try:
                self._model = load_model(key)
                self._model_key = key
            except Exception as exc:
                self._model = None
                self.events.put(("error", "Couldn't download or load the speech model. The first run needs "
                                          f"an internet connection.\n({exc})"))
                return None
            self.events.put(("status", "Ready"))
            return self._model

    def _translate_loop(self) -> None:
        while True:
            audio = self._phrases.get()
            if audio is None:
                return
            model = self._ensure_model()
            if model is None:
                continue
            try:
                self._process(model, audio)
            except Exception as exc:
                self.events.put(("error", f"Translation failed: {exc}"))
            self.events.put(("busy", self._phrases.qsize()))

    def _process(self, model, audio: np.ndarray) -> None:
        lang_code = LANGUAGES[self.settings.language][1]
        common = dict(beam_size=1, vad_filter=False, condition_on_previous_text=False,
                      without_timestamps=True, no_speech_threshold=0.6)

        original = ""
        detected = lang_code
        if self.settings.show_original or lang_code is None:
            segments, info = model.transcribe(audio, language=lang_code, task="transcribe", **common)
            original = _clean("".join(s.text for s in segments))
            detected = info.language
            if not original:
                return
        if detected == "en":
            english = original
        else:
            segments, _ = model.transcribe(audio, language=detected, task="translate", **common)
            english = _clean("".join(s.text for s in segments))
        if not english and not original:
            return
        self.events.put(("line", {"language": detected or "", "original": original if self.settings.show_original else "",
                                  "english": english}))


def self_test() -> int:
    """Used by the cloud build to check the packaged app works: load the
    smallest model and run both passes on a short tone."""
    from faster_whisper import WhisperModel

    def say(msg: str) -> None:
        with open("selftest.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    say("Loading tiny model...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8", download_root=model_folder())
    t = np.arange(int(SAMPLE_RATE * 1.5)) / SAMPLE_RATE
    audio = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    for task in ("transcribe", "translate"):
        segments, info = model.transcribe(audio, language="ja", task=task, beam_size=1)
        say(f"{task}: {''.join(s.text for s in segments)!r} (detected {info.language})")
    import sounddevice  # noqa: F401  (checks PortAudio DLL is bundled)
    import keyboard  # noqa: F401
    import pystray  # noqa: F401
    say("SELFTEST OK")
    return 0


if __name__ == "__main__" and "--selftest" in sys.argv:
    sys.exit(self_test())
