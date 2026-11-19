import SwiftUI
import Translation

struct ContentView: View {
    @Environment(TranslatorModel.self) private var model

    var body: some View {
        @Bindable var model = model

        NavigationStack {
            VStack(spacing: 0) {
                Picker("Spoken language", selection: languageBinding) {
                    ForEach(SourceLanguage.allCases) { language in
                        Text(language.nativeName).tag(language)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.vertical, 8)

                transcript

                if let message = model.errorMessage {
                    Banner(text: message, systemImage: "exclamationmark.triangle.fill", tint: .orange) {
                        model.errorMessage = nil
                    }
                }
                if let language = model.languageToDownload {
                    Banner(
                        text: "Downloading \(language.englishName) for offline translation. This happens only once.",
                        systemImage: "arrow.down.circle.fill",
                        tint: .blue,
                        onClose: nil
                    )
                }

                listenButton
            }
            .navigationTitle("Translator")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        model.speakAloud.toggle()
                    } label: {
                        Image(systemName: model.speakAloud ? "speaker.wave.2.fill" : "speaker.slash")
                    }
                    .accessibilityLabel(model.speakAloud ? "Stop reading translations aloud" : "Read translations aloud")
                }
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Toggle("Start listening when app opens", isOn: $model.startWhenAppOpens)
                        Button("Clear conversation", systemImage: "trash", role: .destructive) {
                            model.clear()
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
        // Apple's one-time language pack download. Runs only when a pack is missing.
        .translationTask(model.downloadConfiguration) { session in
            do {
                try await session.prepareTranslation()
                await model.languageDownloadFinished(success: true)
            } catch {
                await model.languageDownloadFinished(success: false)
            }
        }
        .task {
            await model.startIfEnabledOnOpen()
        }
    }

    private var languageBinding: Binding<SourceLanguage> {
        Binding(
            get: { model.language },
            set: { newValue in Task { await model.switchLanguage(to: newValue) } }
        )
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if model.lines.isEmpty && model.liveOriginal.isEmpty {
                        EmptyHint(isListening: model.isListening, language: model.language)
                    }
                    ForEach(model.lines) { line in
                        LineCard(original: line.original, english: line.english, isLive: false)
                            .id(line.id)
                    }
                    if !model.liveOriginal.isEmpty {
                        LineCard(original: model.liveOriginal, english: model.liveEnglish, isLive: true)
                            .id("live")
                    }
                }
                .padding()
            }
            .onChange(of: model.lines.count) {
                guard let last = model.lines.last?.id else { return }
                withAnimation { proxy.scrollTo(last, anchor: .bottom) }
            }
            .onChange(of: model.liveOriginal) {
                guard !model.liveOriginal.isEmpty else { return }
                proxy.scrollTo("live", anchor: .bottom)
            }
        }
    }

    private var listenButton: some View {
        Button {
            Task { await model.toggleFromButton() }
        } label: {
            ZStack {
                Circle()
                    .fill(model.isListening ? Color.red : Color.accentColor)
                    .frame(width: 76, height: 76)
                Image(systemName: model.isListening ? "stop.fill" : "mic.fill")
                    .font(.system(size: 30, weight: .semibold))
                    .foregroundStyle(.white)
                    .symbolEffect(.pulse, isActive: model.isListening)
            }
        }
        .accessibilityLabel(model.isListening ? "Stop listening" : "Start listening")
        .padding(.vertical, 16)
    }
}

private struct LineCard: View {
    let original: String
    let english: String?
    let isLive: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(original)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if let english, !english.isEmpty {
                Text(english)
                    .font(.title3.weight(.semibold))
            } else {
                Text(isLive ? "…" : "Translating…")
                    .font(.title3)
                    .foregroundStyle(.tertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(isLive ? Color.accentColor.opacity(0.12) : Color(.secondarySystemBackground))
        )
        .opacity(isLive ? 0.85 : 1)
    }
}

private struct EmptyHint: View {
    let isListening: Bool
    let language: SourceLanguage

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: isListening ? "waveform" : "mic.slash")
                .font(.system(size: 40))
                .foregroundStyle(.secondary)
                .symbolEffect(.variableColor.iterative, isActive: isListening)
            Text(isListening ? "Listening for \(language.englishName)…" : "Tap the microphone, or press the Action Button.")
                .font(.headline)
                .multilineTextAlignment(.center)
            Text("The original text and the English translation appear here.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 80)
    }
}

private struct Banner: View {
    let text: String
    let systemImage: String
    let tint: Color
    let onClose: (() -> Void)?

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage).foregroundStyle(tint)
            Text(text).font(.footnote)
            Spacer(minLength: 0)
            if let onClose {
                Button(action: onClose) {
                    Image(systemName: "xmark").font(.footnote.weight(.bold))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Dismiss")
            }
        }
        .padding(12)
        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
        .padding(.top, 8)
    }
}
