import AppIntents
import SwiftUI
import WidgetKit

/// Buttons for Control Center, the Lock Screen, and the Action Button's "Controls" option.
/// One per language, so a single tap starts listening in the right one.
struct TranslateJapaneseControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "com.example.VoiceTranslator.translate.japanese") {
            ControlWidgetButton(action: OpenTranslatorIntent(language: .japanese)) {
                Label("Japanese → English", systemImage: "waveform.badge.mic")
            }
        }
        .displayName("Translate Japanese")
        .description("Start translating Japanese speech into English.")
    }
}

struct TranslatePortugueseControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "com.example.VoiceTranslator.translate.portuguese") {
            ControlWidgetButton(action: OpenTranslatorIntent(language: .portuguese)) {
                Label("Portuguese → English", systemImage: "waveform.badge.mic")
            }
        }
        .displayName("Translate Portuguese")
        .description("Start translating Brazilian Portuguese speech into English.")
    }
}

@main
struct TranslatorControlsBundle: WidgetBundle {
    var body: some Widget {
        TranslateJapaneseControl()
        TranslatePortugueseControl()
    }
}
