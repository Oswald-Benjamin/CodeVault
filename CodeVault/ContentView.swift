//
//  ContentView.swift
//  CodeVault
//
//  Main dashboard: stats overview, archive list, drag & drop.
//

import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var manager: ArchiveManager
    @State private var searchText = ""
    @State private var showingDropTarget = false
    @State private var selectedArchive: CodebaseArchive?
    @State private var showingRestoreSheet = false

    var filteredArchives: [CodebaseArchive] {
        if searchText.isEmpty {
            return manager.archives
        }
        return manager.archives.filter {
            $0.name.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationSplitView {
            // Sidebar — Stats
            StatsSidebar(stats: manager.stats)
                .navigationTitle("CodeVault")
                .frame(minWidth: 250)
        } detail: {
            VStack(spacing: 0) {
                // Status bar
                if manager.isWorking || !manager.statusMessage.isEmpty {
                    StatusBar(
                        isWorking: manager.isWorking,
                        message: manager.statusMessage
                    )
                }

                // Archive list or empty state
                if manager.archives.isEmpty {
                    EmptyStateView(isTargeted: $showingDropTarget)
                        .onDrop(of: [.fileURL], isTargeted: $showingDropTarget, perform: handleDrop)
                } else {
                    ArchiveListView(
                        archives: filteredArchives,
                        searchText: $searchText,
                        onRestore: { archive in
                            selectedArchive = archive
                            showingRestoreSheet = true
                        },
                        onDelete: { archive in
                            manager.delete(archive: archive)
                        },
                        onDrop: handleDrop
                    )
                }
            }
            .navigationTitle("Archives")
            .sheet(isPresented: $showingRestoreSheet) {
                if let archive = selectedArchive {
                    RestoreView(
                        archive: archive,
                        manager: manager,
                        isPresented: $showingRestoreSheet
                    )
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    selectFolderToArchive()
                } label: {
                    Label("Archive Folder", systemImage: "archivebox.fill")
                }
                .disabled(manager.isWorking)
            }
        }
    }

    // MARK: - Actions

    private func selectFolderToArchive() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "Archive"

        panel.begin { response in
            if response == .OK, let url = panel.url {
                manager.archive(sourceURL: url) { _ in }
            }
        }
    }

    private func handleDrop(providers: [NSItemProvider], location: CGPoint) -> Bool {
        guard let provider = providers.first else { return false }
        provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { item, _ in
            guard let data = item as? Data,
                  let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
            var isDir: ObjCBool = false
            if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue {
                DispatchQueue.main.async {
                    manager.archive(sourceURL: url) { _ in }
                }
            }
        }
        return true
    }
}

// MARK: - Stats Sidebar

struct StatsSidebar: View {
    let stats: VaultStats

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Total Archives")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("\(stats.totalArchives)")
                    .font(.system(size: 36, weight: .bold, design: .rounded))
            }

            Divider()

            StatRow(label: "Original Size", value: stats.totalOriginalFormatted, color: .orange)
            StatRow(label: "Compressed", value: stats.totalCompressedFormatted, color: .blue)
            StatRow(label: "Space Saved", value: stats.totalSavedFormatted, color: .green)
            StatRow(label: "Avg Compression", value: stats.averageCompressionPercentage, color: .purple)

            Spacer()

            VStack(alignment: .leading, spacing: 4) {
                Text("Storage Location")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("~/CodeVault/Archives/")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding()
    }
}

struct StatRow: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            Text(value)
                .font(.system(.title3, design: .rounded).weight(.semibold))
                .foregroundColor(color)
        }
    }
}

// MARK: - Status Bar

struct StatusBar: View {
    let isWorking: Bool
    let message: String

    var body: some View {
        HStack(spacing: 8) {
            if isWorking {
                ProgressView()
                    .controlSize(.small)
                    .scaleEffect(0.8)
            }
            Text(message)
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(alignment: .bottom) {
            Divider()
        }
    }
}
