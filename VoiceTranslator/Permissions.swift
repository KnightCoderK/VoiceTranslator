import AVFoundation
import Speech

/// iOS asks for these only the first time. After that the app starts listening with no prompt.
enum Permissions {
    static func requestAll() async -> String? {
        let micAllowed = await AVAudioApplication.requestRecordPermission()
        guard micAllowed else {
            return "Microphone access is off. Turn it on in Settings > Apps > Translator."
        }

        let speechStatus = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
        }
        guard speechStatus == .authorized else {
            return "Speech Recognition is off. Turn it on in Settings > Apps > Translator."
        }
        return nil
    }
}
