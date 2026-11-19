# Install Translator on your iPhone from a Windows laptop

You don't need a Mac. A Mac in the cloud (GitHub Actions, free) builds the app, and **Sideloadly** on Windows puts it on your iPhone using your normal Apple ID.

Because it's free, Apple lets the app run for **7 days**. After that, plug the phone in and repeat Part C (takes about 2 minutes). Your settings stay.

---

## Part A. Get the app file (Translator.ipa)

The easy way: ask Claude in this thread for the latest **Translator.ipa** and download it.

To build it yourself on GitHub:

1. Open your GitHub repository (for example `github.com/<your-name>/VoiceTranslator`).
2. Click **Actions** at the top, then **Build iPhone app** on the left, then **Run workflow** > **Run workflow**.
3. Wait about 5 to 10 minutes for the green tick. Click the run, scroll to **Artifacts**, and click **Translator-ipa**.
4. That downloads a .zip. Right-click it > **Extract All**. Inside is **Translator.ipa**.

## Part B. Set up the laptop (one time)

1. Install **iTunes** from Apple's website (not the Microsoft Store version): https://www.apple.com/itunes/ — scroll to "Looking for other versions?" > Windows.
2. Install **iCloud for Windows** from Apple's website too (Sideloadly needs both).
   - If you already have the Microsoft Store versions, uninstall them first, then install Apple's website versions.
3. Download and install **Sideloadly** from https://sideloadly.io (Windows version).
4. Restart the laptop.

## Part C. Install the app

1. Plug the iPhone into the laptop with a USB-C cable. Unlock the iPhone and tap **Trust**, then enter your passcode.
2. Open **Sideloadly**. Your iPhone should appear in the **iDevice** box.
3. Drag **Translator.ipa** onto the Sideloadly window (or click the IPA icon and pick it).
4. In **Apple Account**, type your Apple ID email.
5. Click **Start**. Type your Apple ID password, and the 6-digit code your phone shows if asked.
6. Wait until it says **Done**.

Tip: you can use a second, spare Apple ID for this if you prefer not to use your main one. It works the same.

## Part D. Allow the app on the iPhone (first time only)

1. **Trust your Apple ID as a developer:** Settings > General > **VPN & Device Management** > tap your Apple ID email > **Trust** > **Trust**.
2. **Turn on Developer Mode:** Settings > **Privacy & Security** > scroll to the bottom > **Developer Mode** > turn it on > **Restart**. After the restart, tap **Turn On** and enter your passcode.
   - If you don't see Developer Mode, do Part C once first, then look again.
3. Open **Translator**. Allow **Microphone** and **Speech Recognition**. If it offers to download Japanese or Portuguese, tap **Download**.

Then set up the Action Button, Back Tap and Control Center buttons with the steps in README.md (sections 3 to 5).

## Every 7 days

The app stops opening after 7 days. Plug in the phone, open Sideloadly, drag the same Translator.ipa in, and click **Start**. Your settings are kept.

Sideloadly can also refresh it automatically over Wi‑Fi while the laptop is on: after installing, open Sideloadly's **Advanced options** and turn on **Automatic refresh** (the laptop and phone must be on the same Wi‑Fi).

## If something goes wrong

- **"Your maximum App ID limit has been reached":** a free Apple ID can create up to 10 App IDs per week. Wait a few days, or use a spare Apple ID.
- **Sideloadly can't see the phone:** make sure iTunes is the Apple website version, unplug and replug, and tap Trust on the phone.
- **Install fails mentioning an extension or "PlugIns":** in Sideloadly's **Advanced options**, tick **Remove app extensions** and try again. The app and Action Button still work. Only the Control Center buttons are removed (Back Tap and Action Button still work through Shortcuts).
- **App opens then closes right away:** the 7 days are up. Reinstall as above.
