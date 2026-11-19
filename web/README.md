# Translator (web)

The web version of Translator. Open it in a browser, speak **Japanese** or **Brazilian Portuguese**, and the English appears on screen, live. It can also read the English aloud.

**Open it:** https://knightcoderk.github.io/voicetranslator/

No install, no account, no API key. It works on a laptop and on a phone.

## How to use it

- It starts listening as soon as the page opens. The first time, the browser asks for the microphone: choose **Allow**.
- Pick **Japanese** or **Portuguese** at the top.
- Each sentence shows the original in grey and the English underneath. A pause of about 1.5 seconds ends a sentence.
- **Read aloud** speaks each English sentence. The microphone pauses while it talks so it doesn't translate itself.
- **Clear** empties the screen.

Keyboard shortcuts (laptop):

| Key | Does |
| --- | --- |
| Space or Ctrl+Alt+T | Start / stop listening |
| J | Japanese |
| P | Portuguese |
| R | Read aloud on / off |

Shortcuts only work while the Translator tab is in front.

Links that open straight into one language (good for bookmarks or home-screen icons):

- Japanese: https://knightcoderk.github.io/voicetranslator/?lang=ja
- Portuguese: https://knightcoderk.github.io/voicetranslator/?lang=pt

**Put it on your phone's home screen:** iPhone Safari: Share > Add to Home Screen. Android Chrome: menu > Add to Home screen (or Install app).

## Which browsers work

| Browser | Works? | Notes |
| --- | --- | --- |
| Chrome or Edge on Windows / Mac | Yes, best | Listens continuously. Recent Chrome can translate on the computer itself. |
| Chrome on Android | Yes | Restarts listening after each sentence, so you may hear a short beep each time. |
| Safari on iPhone / iPad (iOS 14.5+) | Yes, with limits | See below. |
| Chrome / Edge / Firefox on iPhone | Use Safari instead | Apple limits speech recognition in other iPhone browsers. |
| Firefox (computer or Android) | No | Firefox has no speech recognition. |

**iPhone (Safari) limits**

- **Dictation must be on:** Settings > General > Keyboard > Enable Dictation.
- Safari usually wants a **tap on the microphone** before it will listen, so it may not start by itself. It says so on screen.
- Safari ends listening every so often; the page restarts it automatically, but a word can be lost at the switch.
- Read-aloud starts working after your first tap on the page.
- The screen must stay on and Safari must stay in front. It stops when the phone locks or you switch apps. (The page asks the phone to keep the screen awake while listening.)
- For hands-free use on iPhone, the iOS app is still better: it runs fully on the phone and has the Action Button and Back Tap shortcuts.

**Internet is needed.** Browsers send the speech to their own recognition service (Google for Chrome, Apple for Safari). Translation uses Google's free web translator (MyMemory as a backup). Recent desktop Chrome can translate on the computer instead, after a one-time language download that starts when you tap the microphone.

## How it's built

Plain HTML, CSS and JavaScript, no build step.

| File | What it does |
| --- | --- |
| `index.html` | The page. |
| `app.js` | Listening (Web Speech API), sentence splitting, translation, read-aloud, shortcuts. |
| `style.css` | Look and feel, light and dark mode. |
| `manifest.webmanifest`, `icon*` | Home-screen icon and name. |

To try it on your own computer: run `python -m http.server` inside `web/` and open http://localhost:8000. (The microphone only works on `localhost` or `https://` pages.)

## Publishing

`.github/workflows/deploy-web.yml` publishes the `web/` folder to GitHub Pages whenever it changes on `main` (or from the **Run workflow** button on the Actions tab).

One-time setup: in the repository on GitHub, open **Settings > Pages** and set **Source** to **GitHub Actions**.
