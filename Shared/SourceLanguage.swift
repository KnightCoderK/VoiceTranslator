import AppIntents
import Foundation

/// The languages the app can listen for. Translation always goes into English.
enum SourceLanguage: String, CaseIterable, Identifiable, Codable, AppEnum {
    case japanese
    case portuguese

    var id: String { rawValue }

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Spoken Language"
    static let caseDisplayRepresentations: [SourceLanguage: DisplayRepresentation] = [
        .japanese: "Japanese",
        .portuguese: "Portuguese (Brazil)",
    ]

    /// Locale used by the speech recognizer.
    var speechLocale: Locale {
        switch self {
        case .japanese: Locale(identifier: "ja-JP")
        case .portuguese: Locale(identifier: "pt-BR")
        }
    }

    /// Language used by the Translation framework.
    var translationLanguage: Locale.Language {
        switch self {
        case .japanese: Locale.Language(identifier: "ja")
        case .portuguese: Locale.Language(identifier: "pt-BR")
        }
    }

    /// Label shown on the language switch, in the language itself.
    var nativeName: String {
        switch self {
        case .japanese: "日本語"
        case .portuguese: "Português"
        }
    }

    var englishName: String {
        switch self {
        case .japanese: "Japanese"
        case .portuguese: "Portuguese"
        }
    }
}
