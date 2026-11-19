# Translator (iOS)

> Want it in a browser instead? The web version is in [`web/`](web/README.md) and runs at https://knightcoderk.github.io/voicetranslator/

Listens through the iPhone microphone and translates **Japanese** or **Brazilian Portuguese** speech into **English**, live. It shows the original words and the English side by side, and can read the English aloud.

It starts listening the moment it opens, so you can launch it with one press of the **Action Button**, a **double tap on the back** of the phone (Back Tap), or a **Control Center / Lock Screen** button.

Built for iPhone 17 Pro Max on iOS 26. Everything runs on the phone: Apple's on-device speech recognition and Apple's Translation framework. No API keys and no server.

## What's in the folder

| Path | What it does |
| --- | --- |
| `project.yml` | Project definition. XcodeGen turns it into `VoiceTranslator.xcodeproj`. |
| `VoiceTranslator/TranslatorModel.swift` | Listening, sentence splitting, translation, read-aloud. |
| `VoiceTranslator/ContentView.swift` | The screen: language switch, transcript, mic button. |
| `VoiceTranslator/AudioInput.swift` | Microphone capture. |
| `VoiceTranslator/SpeechOutput.swift` | Reads English aloud and mutes the mic while it talks. |
| `VoiceTranslator/Permissions.swift` | One-time microphone and speech permission. |
| `VoiceTranslator/VoiceTranslatorApp.swift` | App entry and the "Translate" App Shortcut (Action Button, Siri, Spotlight). |
| `Shared/ToggleTranslationIntent.swift` | "Start or Stop Translating" action used by the Action Button and Back Tap. |
| `Shared/OpenTranslatorIntent.swift` | Action used by the Control Center / Lock Screen buttons. |
| `Shared/SourceLanguage.swift` | Japanese and Portuguese settings. |
| `TranslatorControls/` | Control Center / Lock Screen buttons ("Translate Japanese", "Translate Portuguese"). |

## 1. Build it (needs a Mac)

Apple only allows iOS apps to be built and installed with **Xcode on a Mac**. A Windows PC can't do this step. Options if you don't have a Mac: borrow one, rent a cloud Mac (for example MacinCloud or AWS EC2 Mac), or use a Mac at work.

On the Mac:

1. Install **Xcode 26** or newer from the Mac App Store, open it once, and accept the license.
2. Install XcodeGen: `brew install xcodegen` (get Homebrew from https://brew.sh if needed).
3. Copy this `VoiceTranslator` folder to the Mac, then in Terminal:
   ```
   cd VoiceTranslator
   xcodegen generate
   open VoiceTranslator.xcodeproj
   ```
4. In Xcode, click the **VoiceTranslator** project, then for **both** targets (`VoiceTranslator` and `TranslatorControls`) open **Signing & Capabilities** and pick your **Team** (sign in with your Apple ID under Xcode > Settings > Accounts if the list is empty).
5. If Xcode says the bundle ID is taken, change `com.example` to something of your own (for example `com.khuram`) in `project.yml` for both targets, run `xcodegen generate` again, and reopen.
6. Plug in the iPhone, choose it at the top of Xcode, and press **Run** (▶).
   - First time only: on the iPhone, turn on **Settings > Privacy & Security > Developer Mode** and restart when asked.
   - With a free Apple ID, also go to **Settings > General > VPN & Device Management** and trust your developer certificate. Free-account installs stop opening after 7 days; just press Run again. A paid Apple Developer account ($99/yr) removes that limit and allows TestFlight.

Use a real iPhone. The Simulator doesn't support Apple's translation.

## 2. First launch (one time)

1. Open **Translator**. iOS asks for **Microphone** and **Speech Recognition**. Allow both. iOS never asks again.
2. If the Japanese or Portuguese translation pack isn't on the phone yet, Apple shows a **Download** sheet. Tap Download. You can also pre-download them in **Settings > Apps > Translate > Downloaded Languages** (get Japanese, Portuguese (Brazil) and English).
3. From now on, opening the app starts listening immediately, with no prompt. (Turn this off in the ••• menu if you prefer.)

## 3. Action Button (one press)

1. **Settings > Action Button**.
2. Swipe to **Shortcut**, tap **Choose a Shortcut**, and pick **Translator > Translate**.
3. Press the Action Button: the app opens and starts listening. Press it again to stop.

To always start in one language, create the shortcut in the Shortcuts app instead (see Back Tap below), set the language, and choose that shortcut here.

Alternative: swipe to **Controls** instead of Shortcut and pick **Translate Japanese** or **Translate Portuguese**.

## 4. Back Tap (double tap the back of the phone)

Back Tap runs a shortcut from the Shortcuts app, so make one first:

1. Open **Shortcuts**, tap **+**, tap **Add Action**, search **Translator**, choose **Start or Stop Translating**.
2. Optional: tap **Spoken language** and pick Japanese or Portuguese (leave empty to use the last one you used).
3. Rename the shortcut to **Translate** and tap Done.
4. **Settings > Accessibility > Touch > Back Tap > Double Tap**, scroll to Shortcuts, pick **Translate**.

Now double-tap the back of the phone to start, and again to stop. You can make a second shortcut for the other language and put it on **Triple Tap**.

## 5. Control Center and Lock Screen

- **Control Center:** swipe down from the top right, tap **+** > **Add a Control**, search **Translator**, add **Translate Japanese** and/or **Translate Portuguese**.
- **Lock Screen:** touch and hold the Lock Screen > **Customize** > **Lock Screen**, tap one of the bottom buttons, remove it, tap **+**, and pick a Translator control.

From the Lock Screen, iOS asks for Face ID before the app opens. That is an iOS rule for any app that opens.

## How it behaves

- It splits speech into sentences when the speaker pauses for about 1.2 seconds, then shows the final English. While someone is still talking you see a rough live preview.
- The speaker icon (top right) turns read-aloud on or off. The mic is muted while it speaks, so it doesn't translate itself.
- If you lock the screen while it's listening, it keeps listening (it's marked as an audio app).
- Pick the spoken language with the switch at the top. Switching while listening restarts in the new language.

## Known limits

- iOS doesn't let apps react to the Camera Control button, so the Action Button and Back Tap are the "one gesture" triggers.
- It doesn't auto-detect Japanese vs Portuguese. Pick the language, or set up one trigger per language.
- This code was written without a Mac, so it hasn't been compiled yet. If Xcode shows an error on first build, send the message and it can be fixed quickly.
