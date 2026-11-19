# Translator for Windows

Listens through your laptop's microphone and translates **Japanese** or **Brazilian Portuguese** speech into **English**, live. It shows the original words and the English, and can read the English aloud.

- **Start or stop from anywhere:** press **Ctrl + Alt + T**, or click the microphone icon next to the clock (the Windows version of the iPhone's Action Button).
- **Starts listening as soon as it opens.** No questions, no pop-ups.
- **Free and offline.** Speech recognition and translation run on your laptop with OpenAI's Whisper model. No account, no API key, nothing sent to a server. The only time it uses the internet is to download the speech model the first time (about 480 MB).

## Install (about 5 minutes)

1. Open **https://github.com/KnightCoderK/VoiceTranslator/releases/tag/windows-latest** and click **TranslatorSetup.exe** under *Assets* to download it.
2. Open the downloaded file.
   - Windows may show a blue box saying **"Windows protected your PC"**. That's because the app isn't from a big publisher. Click **More info**, then **Run anyway**.
3. Click **Next** through the installer (no administrator password needed), and leave **Open Translator now** ticked at the end.
4. **First time only:** the app downloads its speech model. The bottom of the window says *"Downloading the small speech model..."* and then *Ready*. Wait for that (a few minutes on normal Wi‑Fi).

That's it. Start talking in Japanese or Portuguese and the English appears.

Don't want to install anything? Download **Translator-portable.zip** from the same page instead, right-click it > **Extract All**, and double-click **Translator.exe** inside the folder.

## Using it

| To do this | Do this |
| --- | --- |
| Start or stop listening | **Ctrl + Alt + T**, the big button, or left-click the tray icon |
| Switch Japanese / Portuguese | The *Language* box at the top, or right-click the tray icon |
| Hear the English | Tick **Read English aloud** (the app ignores the mic while it's talking, so it doesn't translate itself) |
| Hide the window | Close it with the ✕. It keeps running in the tray, and the hotkey still works |
| Quit completely | Right-click the tray icon > **Quit** |

The tray icon is **blue** when stopped and **red** while listening. If you can't see it, click the small **^** arrow next to the clock.

**Settings** (button at the top) lets you:
- Pick a speech model: *Fast* (quicker, less accurate), *Balanced* (default), or *Best* (most accurate, needs a fast laptop).
- Turn off *Show the original words* to get the English about twice as fast.
- Choose whether it starts listening when it opens, and whether it opens with Windows.
- Change the hotkey (for example `ctrl+shift+space`).

## Tips and fixes

- **English appears a moment after you stop talking.** The app waits for a short pause, then translates the whole phrase, which gives better English than word by word. Long speeches are translated every 12 seconds.
- **Nothing happens when I talk.** Check **Settings > Privacy & security > Microphone** in Windows: *Microphone access* and *Let desktop apps access your microphone* must be on. Also check the right microphone is the default one in **Settings > System > Sound > Input**.
- **It's slow.** Choose *Fast* in Settings, or turn off *Show the original words*.
- **Detect automatically** in the Language box works for both languages, but picking the right one is more accurate.
- If something goes wrong, details are saved in `%LOCALAPPDATA%\Translator\error.log`.
- **Uninstall:** Windows **Settings > Apps > Installed apps > Translator > Uninstall**. To also remove the downloaded speech model, delete the folder `%LOCALAPPDATA%\Translator`.

## How it's built (for developers)

| File | What it does |
| --- | --- |
| `translator_app.py` | Window, tray icon, global hotkey, settings, read-aloud (Windows SAPI voice). |
| `engine.py` | Microphone capture, splitting speech at pauses, Whisper transcription and translation. |
| `make_icon.py` | Draws the app icon during the build. |
| `installer.iss` | Inno Setup script for `TranslatorSetup.exe` (per-user install, no admin). |
| `../.github/workflows/build-windows.yml` | Builds everything on a Windows machine in GitHub Actions. |

Run from source on Windows with Python 3.12:

```
cd windows
pip install -r requirements.txt
python translator_app.py
```

A fresh build runs automatically when anything in `windows/` changes. To publish a new download, open **Actions > Build Windows app > Run workflow**, or push to `main`.
