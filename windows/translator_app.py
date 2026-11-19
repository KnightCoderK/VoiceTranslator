"""Translator for Windows.

Listens to Japanese or Brazilian Portuguese through the microphone and shows
the English translation live. Start and stop with Ctrl+Alt+T from anywhere,
or from the tray icon next to the clock.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# A windowed .exe has no console. Give libraries somewhere harmless to print.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from engine import LANGUAGES, MODELS, Engine, Settings, self_test  # noqa: E402

APP_NAME = "Translator"
DEFAULT_HOTKEY = "ctrl+alt+t"


# ---------------------------------------------------------------- settings

def settings_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    folder = os.path.join(base, APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


DEFAULTS = {
    "language": "ja",
    "model": "balanced",
    "show_original": True,
    "speak_aloud": False,
    "start_listening_on_open": True,
    "hotkey": DEFAULT_HOTKEY,
}


def load_settings() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data.update(json.load(f))
    except Exception:
        pass
    if data["language"] not in LANGUAGES:
        data["language"] = "ja"
    if data["model"] not in MODELS:
        data["model"] = "balanced"
    return data


def save_settings(data: dict) -> None:
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- start with Windows

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _exe_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}" --minimized'


def starts_with_windows() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except Exception:
        return False


def set_start_with_windows(enabled: bool) -> None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _exe_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        pass


# ---------------------------------------------------------------- read aloud

class Speaker:
    """Reads English aloud with the voice built into Windows (works offline)."""

    def __init__(self, on_start, on_done):
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._on_start = on_start
        self._on_done = on_done
        self._voice = None
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str) -> None:
        self._queue.put(text)

    def stop(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        if self._voice is not None:
            try:
                self._voice.Speak("", 2)  # SVSFPurgeBeforeSpeak: cut off current speech
            except Exception:
                pass

    def _run(self) -> None:
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            self._voice = win32com.client.Dispatch("SAPI.SpVoice")
            for token in self._voice.GetVoices():
                # Prefer an English voice if Windows has several.
                if "English" in token.GetDescription():
                    self._voice.Voice = token
                    break
        except Exception:
            self._voice = None
        while True:
            text = self._queue.get()
            if self._voice is None:
                continue
            self._on_start(text)
            try:
                self._voice.Speak(text)
            except Exception:
                pass
            if self._queue.empty():
                self._on_done()


# ---------------------------------------------------------------- tray icon

def make_icon_image(listening: bool):
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (220, 53, 69) if listening else (37, 99, 235)
    d.ellipse((2, 2, size - 2, size - 2), fill=color)
    # Simple microphone
    d.rounded_rectangle((24, 12, 40, 38), radius=8, fill="white")
    d.arc((17, 22, 47, 46), start=0, end=180, fill="white", width=4)
    d.line((32, 46, 32, 53), fill="white", width=4)
    d.line((24, 53, 40, 53), fill="white", width=4)
    return img


# ---------------------------------------------------------------- main window

class App:
    def __init__(self, start_minimized: bool):
        self.settings = load_settings()
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.engine = Engine(self.events, Settings(
            language=self.settings["language"],
            model=self.settings["model"],
            show_original=self.settings["show_original"],
        ))
        self.speaker = Speaker(on_start=self._on_speak_start, on_done=self._on_speak_done)
        self.tray = None
        self.hotkey_handle = None
        self.quitting = False

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("760x560")
        self.root.minsize(480, 360)
        self._set_window_icon()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self._register_hotkey()
        self._start_tray()
        listen_for_second_launch(self.events)

        if start_minimized:
            self.root.withdraw()
        self.root.after(50, self._poll_events)

        self.engine.preload_model()
        if self.settings["start_listening_on_open"]:
            self.root.after(300, self.engine.start)

    # ----- UI -----

    def _set_window_icon(self) -> None:
        try:
            from PIL import ImageTk
            self._icon_photo = ImageTk.PhotoImage(make_icon_image(False))
            self.root.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    def _build_ui(self) -> None:
        root = self.root
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(size=10)
        self.font_english = tkfont.Font(family="Segoe UI", size=15, weight="bold")
        self.font_original = tkfont.Font(family="Yu Gothic UI", size=12)
        self.font_button = tkfont.Font(family="Segoe UI", size=13, weight="bold")

        top = ttk.Frame(root, padding=(12, 10, 12, 4))
        top.pack(fill="x")

        ttk.Label(top, text="Language:").pack(side="left")
        self.lang_var = tk.StringVar(value=LANGUAGES[self.settings["language"]][0])
        lang_box = ttk.Combobox(top, textvariable=self.lang_var, state="readonly", width=22,
                                values=[v[0] for v in LANGUAGES.values()])
        lang_box.pack(side="left", padx=(6, 16))
        lang_box.bind("<<ComboboxSelected>>", lambda e: self._language_changed())

        self.speak_var = tk.BooleanVar(value=self.settings["speak_aloud"])
        ttk.Checkbutton(top, text="Read English aloud", variable=self.speak_var,
                        command=self._speak_changed).pack(side="left")

        ttk.Button(top, text="Clear", command=self._clear).pack(side="right")
        ttk.Button(top, text="Settings", command=self._open_settings).pack(side="right", padx=6)

        # Transcript
        mid = ttk.Frame(root, padding=(12, 4, 12, 4))
        mid.pack(fill="both", expand=True)
        self.text = tk.Text(mid, wrap="word", relief="flat", padx=12, pady=10,
                            bg="#ffffff", fg="#111827", state="disabled", cursor="arrow")
        scroll = ttk.Scrollbar(mid, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("original", font=self.font_original, foreground="#6b7280",
                                spacing1=10)
        self.text.tag_configure("english", font=self.font_english, foreground="#111827",
                                spacing3=6)
        self.text.tag_configure("hint", font=self.font_original, foreground="#9ca3af")
        self._show_hint()

        # Bottom bar
        bottom = ttk.Frame(root, padding=(12, 4, 12, 12))
        bottom.pack(fill="x")
        self.button = tk.Button(bottom, text="Start listening", font=self.font_button,
                                bg="#2563eb", fg="white", activebackground="#1d4ed8",
                                activeforeground="white", relief="flat", padx=18, pady=8,
                                command=self.engine.toggle)
        self.button.pack(side="left")
        self.level = ttk.Progressbar(bottom, length=120, maximum=1.0)
        self.level.pack(side="left", padx=12)
        self.status_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.status_var, foreground="#4b5563",
                  wraplength=420).pack(side="left", fill="x", expand=True)
        self.hotkey_var = tk.StringVar(value=f"Hotkey: {self._hotkey_label()}")
        ttk.Label(bottom, textvariable=self.hotkey_var, foreground="#6b7280").pack(side="right")

    def _hotkey_label(self) -> str:
        return "+".join(p.capitalize() for p in self.settings["hotkey"].split("+"))

    def _show_hint(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", f"Speak {self.lang_var.get() if self.settings['language'] != 'auto' else 'Japanese or Portuguese'}"
                                f" and the English appears here.\n\nPress {self._hotkey_label()} anywhere "
                                "to start or stop, or use the tray icon next to the clock.", "hint")
        self.text.configure(state="disabled")
        self._hint_shown = True

    def _clear(self) -> None:
        self._show_hint()

    def _append_line(self, original: str, english: str) -> None:
        self.text.configure(state="normal")
        if self._hint_shown:
            self.text.delete("1.0", "end")
            self._hint_shown = False
        if original:
            self.text.insert("end", original + "\n", "original")
        self.text.insert("end", english + "\n", "english")
        self.text.configure(state="disabled")
        self.text.see("end")

    def _language_changed(self) -> None:
        label = self.lang_var.get()
        key = next(k for k, v in LANGUAGES.items() if v[0] == label)
        self.set_language(key)

    def set_language(self, key: str) -> None:
        self.settings["language"] = key
        self.engine.settings.language = key
        self.lang_var.set(LANGUAGES[key][0])
        save_settings(self.settings)
        if self._hint_shown:
            self._show_hint()
        self._update_tray()

    def _speak_changed(self) -> None:
        self.settings["speak_aloud"] = bool(self.speak_var.get())
        save_settings(self.settings)
        if not self.settings["speak_aloud"]:
            self.speaker.stop()
            self.engine.unmute()
        self._update_tray()

    def _open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.resizable(False, False)
        win.transient(self.root)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both")

        ttk.Label(frame, text="Speech model:").grid(row=0, column=0, sticky="w")
        model_var = tk.StringVar(value=MODELS[self.settings["model"]][0])
        ttk.Combobox(frame, textvariable=model_var, state="readonly", width=30,
                     values=[v[0] for v in MODELS.values()]).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(frame, text="A bigger model is more accurate but slower. It downloads once.",
                  foreground="#6b7280").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        orig_var = tk.BooleanVar(value=self.settings["show_original"])
        ttk.Checkbutton(frame, text="Show the original words too (turn off for faster English)",
                        variable=orig_var).grid(row=2, column=0, columnspan=2, sticky="w")
        auto_var = tk.BooleanVar(value=self.settings["start_listening_on_open"])
        ttk.Checkbutton(frame, text="Start listening as soon as the app opens",
                        variable=auto_var).grid(row=3, column=0, columnspan=2, sticky="w")
        boot_var = tk.BooleanVar(value=starts_with_windows())
        ttk.Checkbutton(frame, text="Open Translator when Windows starts (in the tray)",
                        variable=boot_var).grid(row=4, column=0, columnspan=2, sticky="w")

        ttk.Label(frame, text="Start/stop hotkey:").grid(row=5, column=0, sticky="w", pady=(10, 0))
        hotkey_var = tk.StringVar(value=self.settings["hotkey"])
        ttk.Entry(frame, textvariable=hotkey_var, width=20).grid(row=5, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(frame, text="For example ctrl+alt+t or ctrl+shift+space",
                  foreground="#6b7280").grid(row=6, column=0, columnspan=2, sticky="w")

        def save():
            label = model_var.get()
            self.settings["model"] = next(k for k, v in MODELS.items() if v[0] == label)
            self.settings["show_original"] = bool(orig_var.get())
            self.settings["start_listening_on_open"] = bool(auto_var.get())
            new_hotkey = hotkey_var.get().strip().lower() or DEFAULT_HOTKEY
            hotkey_changed = new_hotkey != self.settings["hotkey"]
            self.settings["hotkey"] = new_hotkey
            save_settings(self.settings)
            set_start_with_windows(bool(boot_var.get()))
            self.engine.settings.model = self.settings["model"]
            self.engine.settings.show_original = self.settings["show_original"]
            self.engine.preload_model()
            if hotkey_changed:
                self._register_hotkey()
                self.hotkey_var.set(f"Hotkey: {self._hotkey_label()}")
                self._update_tray()
            win.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=save).pack(side="right", padx=6)

    # ----- events from the engine -----

    def _poll_events(self) -> None:
        level = None
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "level":
                    level = data
                elif kind == "listening":
                    self._set_listening_ui(bool(data))
                elif kind == "status":
                    self.status_var.set(str(data))
                elif kind == "error":
                    self.status_var.set(str(data))
                elif kind == "busy":
                    if self.engine.listening:
                        self.status_var.set("Translating..." if data else "Listening...")
                elif kind == "line":
                    self._append_line(data["original"], data["english"])
                    if self.settings["speak_aloud"] and data["english"]:
                        self.speaker.say(data["english"])
                elif kind == "toggle":
                    self.engine.toggle()
                elif kind == "show":
                    self.show_window()
                elif kind == "language":
                    self.set_language(str(data))
                elif kind == "speak":
                    self.speak_var.set(not self.speak_var.get())
                    self._speak_changed()
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        if level is not None:
            self.level["value"] = level
        self.root.after(50, self._poll_events)

    def _set_listening_ui(self, listening: bool) -> None:
        if listening:
            self.button.configure(text="Stop listening", bg="#dc2626", activebackground="#b91c1c")
            if not self.status_var.get() or self.status_var.get() in ("Stopped", "Ready"):
                self.status_var.set("Listening...")
        else:
            self.button.configure(text="Start listening", bg="#2563eb", activebackground="#1d4ed8")
            self.level["value"] = 0
            self.status_var.set("Stopped")
        self._update_tray()

    def _on_speak_start(self, text: str) -> None:
        # Don't translate our own voice: ignore the mic while speaking.
        self.engine.mute_for(60)

    def _on_speak_done(self) -> None:
        # Keep ignoring the mic for a moment so the end of our own voice isn't picked up.
        self.engine.unmute()
        self.engine.mute_for(0.4)

    # ----- hotkey -----

    def _register_hotkey(self) -> None:
        try:
            import keyboard
            if self.hotkey_handle is not None:
                keyboard.remove_hotkey(self.hotkey_handle)
            self.hotkey_handle = keyboard.add_hotkey(
                self.settings["hotkey"], lambda: self.events.put(("toggle", None)), suppress=False)
        except Exception as exc:
            self.hotkey_handle = None
            self.status_var.set(f"Couldn't set the hotkey {self.settings['hotkey']!r}: {exc}")

    # ----- tray -----

    def _start_tray(self) -> None:
        try:
            import pystray
        except Exception:
            return
        put = self.events.put

        def lang_item(key):
            return pystray.MenuItem(
                LANGUAGES[key][0], lambda icon, item: put(("language", key)),
                checked=lambda item: self.settings["language"] == key, radio=True)

        menu = pystray.Menu(
            pystray.MenuItem(lambda item: "Stop listening" if self.engine.listening else "Start listening",
                             lambda icon, item: put(("toggle", None)), default=True),
            pystray.MenuItem("Show window", lambda icon, item: put(("show", None))),
            pystray.Menu.SEPARATOR,
            lang_item("ja"), lang_item("pt"), lang_item("auto"),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Read English aloud", lambda icon, item: put(("speak", None)),
                             checked=lambda item: self.settings["speak_aloud"]),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda icon, item: put(("quit", None))),
        )
        self.tray = pystray.Icon(APP_NAME, make_icon_image(False), self._tray_title(), menu)
        self.tray.run_detached()

    def _tray_title(self) -> str:
        state = "listening" if self.engine.listening else "stopped"
        return f"{APP_NAME} ({state}) - {self._hotkey_label()} to start/stop"

    def _update_tray(self) -> None:
        if self.tray is None:
            return
        try:
            self.tray.icon = make_icon_image(self.engine.listening)
            self.tray.title = self._tray_title()
            self.tray.update_menu()
        except Exception:
            pass

    # ----- window -----

    def hide_window(self) -> None:
        if self.tray is None:
            self.quit()
            return
        self.root.withdraw()
        if not getattr(self, "_told_about_tray", False):
            self._told_about_tray = True
            try:
                self.tray.notify(f"Still running. Press {self._hotkey_label()} to start or stop, "
                                 "or right-click this icon.", APP_NAME)
            except Exception:
                pass

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        self.engine.stop()
        self.speaker.stop()
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


# ---------------------------------------------------------------- single instance

INSTANCE_PORT = 47613  # localhost only


def already_running() -> bool:
    """If Translator is already open, bring its window forward and return True."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", INSTANCE_PORT), timeout=0.5) as s:
            s.sendall(b"show")
        return True
    except OSError:
        return False


def listen_for_second_launch(events) -> None:
    import socket

    def serve():
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(("127.0.0.1", INSTANCE_PORT))
            server.listen(2)
        except OSError:
            return
        while True:
            try:
                conn, _ = server.accept()
                with conn:
                    if conn.recv(16) == b"show":
                        events.put(("show", None))
            except OSError:
                return

    threading.Thread(target=serve, daemon=True).start()


def log_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    folder = os.path.join(base, APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "error.log")


def log_error(text: str) -> None:
    try:
        import datetime
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
    except Exception:
        pass


def main() -> int:
    if "--selftest" in sys.argv:
        return self_test()
    smoke = "--smoketest" in sys.argv
    if not smoke and already_running():
        return 0
    try:
        # Sharp text on high-DPI laptop screens.
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    import traceback
    try:
        app = App(start_minimized="--minimized" in sys.argv)
        app.root.report_callback_exception = lambda *exc: log_error("".join(traceback.format_exception(*exc)))
        if smoke:
            # Cloud build check: open the window, run for a few seconds, toggle, then quit.
            def report():
                with open("smoketest.txt", "w", encoding="utf-8") as f:
                    f.write(f"status={app.status_var.get()!r}\nlistening={app.engine.listening}\n"
                            f"tray={app.tray is not None}\nhotkey={app.hotkey_handle is not None}\n")
                app.quit()
            app.root.after(2000, lambda: app._append_line("こんにちは", "Hello"))
            app.root.after(3000, app.engine.toggle)
            app.root.after(8000, report)
        app.run()
    except Exception:
        log_error(traceback.format_exc())
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
