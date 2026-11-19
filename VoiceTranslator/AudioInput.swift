import AVFoundation
import Speech

enum AudioInputError: LocalizedError {
    case noMicrophone

    var errorDescription: String? {
        "No microphone input is available."
    }
}

/// Owns the microphone. Feeds every audio buffer to whichever recognition request is current.
/// The tap runs on a real-time audio thread, so shared state is guarded by a lock.
final class AudioInput: @unchecked Sendable {
    private let engine = AVAudioEngine()
    private let lock = NSLock()
    private var currentRequest: SFSpeechAudioBufferRecognitionRequest?
    private var isMuted = false

    /// The request that receives audio. Swapped each time a new sentence starts.
    var request: SFSpeechAudioBufferRecognitionRequest? {
        get { lock.withLock { currentRequest } }
        set { lock.withLock { currentRequest = newValue } }
    }

    /// While the app reads a translation aloud, stop feeding audio so it doesn't transcribe itself.
    var muted: Bool {
        get { lock.withLock { isMuted } }
        set { lock.withLock { isMuted = newValue } }
    }

    func start() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(
            .playAndRecord,
            mode: .default,
            options: [.defaultToSpeaker, .allowBluetoothA2DP, .duckOthers]
        )
        try session.setActive(true, options: .notifyOthersOnDeactivation)

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            throw AudioInputError.noMicrophone
        }

        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard let self else { return }
            self.lock.lock()
            let target = self.isMuted ? nil : self.currentRequest
            self.lock.unlock()
            target?.append(buffer)
        }

        engine.prepare()
        try engine.start()
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        request = nil
        muted = false
    }
}
