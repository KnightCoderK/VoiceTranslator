import AppIntents
import SwiftUI

@main
struct VoiceTranslatorApp: App {
    @State private var model = TranslatorModel.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(model)
        }
    }
}

/// Makes the intent show up in Shortcuts, Spotlight, Siri, and the Action Button's "Shortcut" list
/// without the person having to build a shortcut first.
struct TranslatorShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: ToggleTranslationIntent(),
            phrases: [
                "Translate with \(.applicationName)",
                "Start \(.applicationName)",
            ],
            shortTitle: "Translate",
            systemImageName: "waveform.badge.mic"
        )
    }
}
