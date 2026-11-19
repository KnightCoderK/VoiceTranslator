import AVFoundation
import Observation
import Speech
import SwiftUI
import Translation
import UIKit

struct TranscriptLine: Identifiable, Equatable {
    let id = UUID()
    let language: SourceLanguage
    let original: String
    var english: String?
}

/// Listens, splits speech into sentences, translates each into English, and optionally reads it aloud.
@MainActor
@Observable
final class TranslatorModel {
    static let shared = TranslatorModel()
    static let english = Locale.Language(identifier: "en")

    // MARK: Settings (saved between launches)

    var language: SourceLanguage {
        didSet { defaults.set(language.rawValue, forKey: Keys.language) }
    }
    var speakAloud: Bool {
        didSet {
            defaults.set(speakAloud, forKey: Keys.speakAloud)
            if !speakAloud { speech.stopSpeaking() }
        }
    }
    var startWhenAppOpens: Bool {
        didSet { defaults.set(startWhenAppOpens, forKey: Keys.startWhenAppOpens) }
    }

    // MARK: State shown in the UI

    private(set) var isListening = false
    private(set) var liveOriginal = ""
    private(set) var liveEnglish = ""
    private(set) var lines: [TranscriptLine] = []
    var errorMessage: String?
    /// When set, the UI asks iOS to download this language pack (one time only).
    private(set) var languageToDownload: SourceLanguage?

    var downloadConfiguration: TranslationSession.Configuration? {
        languageToDownload.map {
            TranslationSession.Configuration(source: $0.translationLanguage, target: Self.english)
        }
    }

    // MARK: Internals

    @ObservationIgnored private let defaults = UserDefaults.standard
    @ObservationIgnored private let audio: AudioInput
    @ObservationIgnored private let speech: SpeechOutput
    @ObservationIgnored private var recognizer: SFSpeechRecognizer?
    @ObservationIgnored private var recognitionTask: SFSpeechRecognitionTask?
    @ObservationIgnored private var segmentID = 0
    @ObservationIgnored private var silenceTimer: Task<Void, Never>?
    @ObservationIgnored private var translator: TranslationSession?
    @ObservationIgnored private var translationQueue: Task<Void, Never>?
    @ObservationIgnored private var pendingLineTranslations = 0
    @ObservationIgnored private var partialTranslationInFlight = false
    @ObservationIgnored private var lastPartialTranslation = Date.distantPast
    @ObservationIgnored private var consecutiveFailures = 0
    @ObservationIgnored private var isStarting = false
    @ObservationIgnored private var listeningSince: Date?

    /// How long a pause has to be before the current sentence is finished and translated.
    private let sentencePause: Duration = .seconds(1.2)

    private enum Keys {
        static let language = "language"
        static let speakAloud = "speakAloud"
        static let startWhenAppOpens = "startWhenAppOpens"
    }

    private init() {
        let defaults = UserDefaults.standard
        language = SourceLanguage(rawValue: defaults.string(forKey: Keys.language) ?? "") ?? .japanese
        speakAloud = defaults.bool(forKey: Keys.speakAloud)
        startWhenAppOpens = defaults.object(forKey: Keys.startWhenAppOpens) as? Bool ?? true
        let audio = AudioInput()
        self.audio = audio
        speech = SpeechOutput(audio: audio)
    }

    // MARK: Triggers

    /// Called by the Action Button, Back Tap shortcut, Siri, and the Control Center button.
    func handleTrigger(language requested: SourceLanguage?) async {
        if isStarting { return }
        if isListening {
            if let requested, requested != language {
                await start(language: requested)
                return
            }
            // When the trigger cold-launches the app, the app's own auto-start may have
            // just begun. Only treat the trigger as "stop" if we've been listening a while.
            if let since = listeningSince, Date().timeIntervalSince(since) > 2 {
                stop()
            }
            return
        }
        await start(language: requested)
    }

    func startIfEnabledOnOpen() async {
        guard startWhenAppOpens, !isListening else { return }
        await start()
    }

    func toggleFromButton() async {
        if isListening { stop() } else { await start() }
    }

    func switchLanguage(to newLanguage: SourceLanguage) async {
        guard newLanguage != language else { return }
        if isListening {
            await start(language: newLanguage)
        } else {
            language = newLanguage
        }
    }

    // MARK: Start / stop

    func start(language requested: SourceLanguage? = nil) async {
        guard !isStarting else { return }
        if let requested, requested != language {
            if isListening { stop() }
            language = requested
        }
        guard !isListening else { return }

        isStarting = true
        defer { isStarting = false }
        errorMessage = nil
        consecutiveFailures = 0

        if let problem = await Permissions.requestAll() {
            errorMessage = problem
            return
        }

        guard let recognizer = SFSpeechRecognizer(locale: language.speechLocale), recognizer.isAvailable else {
            errorMessage = "Speech recognition for \(language.englishName) isn't available right now."
            return
        }
        self.recognizer = recognizer

        await prepareTranslator()

        do {
            try audio.start()
        } catch {
            errorMessage = "Couldn't start the microphone: \(error.localizedDescription)"
            return
        }

        isListening = true
        listeningSince = Date()
        UIApplication.shared.isIdleTimerDisabled = true
        beginSentence()
    }

    func stop() {
        guard isListening else { return }
        silenceTimer?.cancel()
        recognitionTask?.cancel()
        recognitionTask = nil
        commitLiveSentence()
        isListening = false
        listeningSince = nil
        segmentID += 1
        audio.stop()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    func clear() {
        lines.removeAll()
        liveOriginal = ""
        liveEnglish = ""
    }

    // MARK: Translation setup

    private func prepareTranslator() async {
        translator = nil
        let source = language.translationLanguage
        let status = await LanguageAvailability().status(from: source, to: Self.english)
        switch status {
        case .installed:
            translator = TranslationSession(installedSource: source, target: Self.english)
        case .supported:
            // Needs a one-time download. The UI shows Apple's download sheet.
            languageToDownload = language
        case .unsupported:
            errorMessage = "\(language.englishName) to English translation isn't supported on this iPhone."
        @unknown default:
            break
        }
    }

    /// Called by the UI after Apple's download sheet finishes.
    func languageDownloadFinished(success: Bool) async {
        languageToDownload = nil
        guard success else {
            errorMessage = "The \(language.englishName) language pack wasn't downloaded, so only the original text is shown."
            return
        }
        await prepareTranslator()
        // Translate anything heard while the pack was downloading.
        for line in lines where line.english == nil && line.language == language {
            enqueueTranslation(lineID: line.id, text: line.original)
        }
    }

    // MARK: Recognition

    private func beginSentence() {
        guard isListening, let recognizer else { return }
        segmentID += 1
        let segment = segmentID

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.addsPunctuation = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }
        audio.request = request
        liveOriginal = ""
        liveEnglish = ""

        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            let text = result?.bestTranscription.formattedString
            let isFinal = result?.isFinal ?? false
            let failure = error?.localizedDescription
            Task { @MainActor in
                self?.handleRecognition(text: text, isFinal: isFinal, failure: failure, segment: segment)
            }
        }
    }

    private func handleRecognition(text: String?, isFinal: Bool, failure: String?, segment: Int) {
        guard segment == segmentID, isListening else { return }

        if let text, !text.isEmpty {
            consecutiveFailures = 0
            liveOriginal = text
        }

        if isFinal || failure != nil {
            silenceTimer?.cancel()
            let heardSomething = !liveOriginal.isEmpty
            commitLiveSentence()
            if let failure, !heardSomething {
                // Usually "no speech detected" after a long quiet spell. Just listen again,
                // but give up if it keeps failing straight away.
                consecutiveFailures += 1
                if consecutiveFailures > 5 {
                    errorMessage = "Speech recognition stopped: \(failure)"
                    stop()
                    return
                }
                Task {
                    try? await Task.sleep(for: .milliseconds(300))
                    beginSentence()
                }
            } else {
                beginSentence()
            }
            return
        }

        scheduleSentenceEnd(segment: segment)
        translatePartialIfDue()
    }

    /// When the speaker pauses, close the sentence, translate it, and start a fresh one.
    private func scheduleSentenceEnd(segment: Int) {
        silenceTimer?.cancel()
        silenceTimer = Task { [sentencePause] in
            try? await Task.sleep(for: sentencePause)
            guard !Task.isCancelled, segment == segmentID, isListening else { return }
            recognitionTask?.cancel()
            commitLiveSentence()
            beginSentence()
        }
    }

    private func commitLiveSentence() {
        let text = liveOriginal.trimmingCharacters(in: .whitespacesAndNewlines)
        let preview = liveEnglish
        liveOriginal = ""
        liveEnglish = ""
        guard !text.isEmpty else { return }
        var line = TranscriptLine(language: language, original: text)
        if !preview.isEmpty { line.english = preview }
        lines.append(line)
        enqueueTranslation(lineID: line.id, text: text)
    }

    // MARK: Translating

    /// Final translations run one at a time so they're read aloud in order.
    private func enqueueTranslation(lineID: UUID, text: String) {
        let previous = translationQueue
        pendingLineTranslations += 1
        translationQueue = Task {
            await previous?.value
            await translateLine(id: lineID, text: text)
            pendingLineTranslations -= 1
        }
    }

    private func translateLine(id: UUID, text: String) async {
        guard let translator else { return }
        do {
            let response = try await translator.translate(text)
            if let index = lines.firstIndex(where: { $0.id == id }) {
                lines[index].english = response.targetText
            }
            if speakAloud {
                speech.speak(response.targetText)
            }
        } catch {
            errorMessage = "Translation failed: \(error.localizedDescription)"
        }
    }

    /// A rough English preview while the person is still talking.
    private func translatePartialIfDue() {
        guard let translator,
              !partialTranslationInFlight,
              pendingLineTranslations == 0,
              Date().timeIntervalSince(lastPartialTranslation) > 0.6
        else { return }

        partialTranslationInFlight = true
        lastPartialTranslation = Date()
        let segment = segmentID
        let text = liveOriginal
        Task {
            defer { partialTranslationInFlight = false }
            if let response = try? await translator.translate(text), segment == segmentID {
                liveEnglish = response.targetText
            }
        }
    }
}
