//
//  RestoreView.swift
//  CodeVault
//
//  Sheet for choosing restore destination and confirming.
//

import SwiftUI

struct RestoreView: View {
    let archive: CodebaseArchive
    let manager: ArchiveManager
    @Binding var isPresented: Bool

    @State private var destinationPath = ""
    @State private var isRestoring = false
    @State private var restoreComplete = false

    init(archive: CodebaseArchive, manager: ArchiveManager, isPresented: Binding<Bool>) {
        self.archive = archive
        self.manager = manager
        self._isPresented = isPresented
        // Default to the original parent directory
        let originalParent = (archive.originalPath as NSString).deletingLastPathComponent
        _destinationPath = State(initialValue: originalParent)
    }

    var destinationURL: URL {
        URL(fileURLWithPath: destinationPath).appendingPathComponent(archive.name)
    }

    var destinationExists: Bool {
        FileManager.default.fileExists(atPath: destinationURL.path)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Header
            VStack(alignment: .leading, spacing: 6) {
                Text("Restore \(archive.name)")
                    .font(.title2.weight(.bold))

                Text("Choose where to extract the archive contents.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            // Archive info
            HStack(spacing: 12) {
                InfoPill(icon: "archivebox.fill", text: archive.compressedSizeFormatted, color: .blue)
                InfoPill(icon: "doc.zipper", text: archive.originalSizeFormatted + " original", color: .orange)
                InfoPill(icon: "clock", text: archive.dateArchived.formatted(date: .abbreviated, time: .omitted), color: .secondary)
            }

            // Destination picker
            VStack(alignment: .leading, spacing: 8) {
                Text("Destination")
                    .font(.headline)

                HStack {
                    Text(destinationPath)
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Button("Choose…") {
                        selectDestination()
                    }
                }
                .padding(10)
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)

                if destinationExists {
                    Label("A folder with this name already exists at the destination. It will be replaced.", systemImage: "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundColor(.orange)
                }

                Text("Will extract to: \(destinationURL.path)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            Spacer()

            // Actions
            HStack {
                Button("Cancel") {
                    isPresented = false
                }
                .disabled(isRestoring)

                Spacer()

                Button {
                    performRestore()
                } label: {
                    if isRestoring {
                        HStack(spacing: 6) {
                            ProgressView().controlSize(.small).scaleEffect(0.7)
                            Text("Restoring…")
                        }
                    } else if restoreComplete {
                        Label("Done", systemImage: "checkmark.circle.fill")
                    } else {
                        Label("Restore Here", systemImage: "arrow.down.doc.fill")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(destinationPath.isEmpty || isRestoring)
            }
        }
        .padding(24)
        .frame(width: 520, height: 340)
    }

    private func selectDestination() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "Choose"
        panel.message = "Select the parent folder where \(archive.name) should be restored"

        panel.begin { response in
            if response == .OK, let url = panel.url {
                destinationPath = url.path
            }
        }
    }

    private func performRestore() {
        isRestoring = true
        let dest = URL(fileURLWithPath: destinationPath)
        manager.restore(archive: archive, to: dest) { success in
            isRestoring = false
            restoreComplete = success
            if success {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
                    isPresented = false
                }
            }
        }
    }
}

struct InfoPill: View {
    let icon: String
    let text: String
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption)
            Text(text)
                .font(.caption)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.1))
        .foregroundColor(color)
        .cornerRadius(6)
    }
}
