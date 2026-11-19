import AppIntents
import Foundation

/// Used by the Control Center / Lock Screen buttons. Apple requires an OpenIntent
/// (compiled into both the app and the controls extension) for a control to open the app.
struct OpenTranslatorIntent: OpenIntent {
    static let title: LocalizedStringResource = "Open Translator and Listen"
    static let description = IntentDescription("Opens Translator and starts listening in the chosen language.")

    @Parameter(title: "Spoken language")
    var target: SourceLanguage

    init() {
        target = .japanese
    }

    init(language: SourceLanguage) {
        target = language
    }

    @MainActor
    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        await TranslatorModel.shared.handleTrigger(language: target)
        #endif
        return .result()
    }
}
