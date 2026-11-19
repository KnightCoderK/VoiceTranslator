import AppIntents
import Foundation

/// Starts listening and translating right away, or stops if it is already running.
/// Used by the Action Button, Back Tap (via a Shortcut), Siri, and the Control Center / Lock Screen control.
struct ToggleTranslationIntent: AppIntent {
    static let title: LocalizedStringResource = "Start or Stop Translating"
    static let description = IntentDescription(
        "Opens Translator and immediately starts listening to Japanese or Portuguese speech and translating it into English. Runs again to stop."
    )

    /// The app has to be in the foreground to use the microphone reliably, so the system opens it.
    static let openAppWhenRun: Bool = true

    @Parameter(title: "Spoken language", description: "Leave empty to use the last language you picked.")
    var language: SourceLanguage?

    init() {}

    init(language: SourceLanguage?) {
        self.language = language
    }

    @MainActor
    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        await TranslatorModel.shared.handleTrigger(language: language)
        #endif
        return .result()
    }
}
