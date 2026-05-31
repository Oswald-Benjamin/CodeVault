//
//  ArchiveListView.swift
//  CodeVault
//
//  Searchable list of archived codebases with restore/delete actions.
//

import SwiftUI
import UniformTypeIdentifiers

struct ArchiveListView: View {
    let archives: [CodebaseArchive]
    @Binding var searchText: String
    let onRestore: (CodebaseArchive) -> Void
    let onDelete: (CodebaseArchive) -> Void
    let onDrop: ([NSItemProvider]) -> Bool

    @State private var archiveToDelete: CodebaseArchive?
    @State private var showingDeleteAlert = false

    var body: some View {
        VStack(spacing: 0) {
            // Search bar
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                TextField("Search archives…", text: $searchText)
                    .textFieldStyle(PlainTextFieldStyle())
                if !searchText.isEmpty {
                    Button {
                        searchText = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            .padding(10)
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            .padding()

            // List
            List(archives) { archive in
                ArchiveRowView(
                    archive: archive,
                    onRestore: { onRestore(archive) },
                    onDelete: {
                        archiveToDelete = archive
                        showingDeleteAlert = true
                    }
                )
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
            }
            .listStyle(PlainListStyle())
            .alert("Delete Archive?", isPresented: $showingDeleteAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Delete", role: .destructive) {
                    if let archive = archiveToDelete {
                        onDelete(archive)
                    }
                }
            } message: {
                if let archive = archiveToDelete {
                    Text("'\(archive.name)' and its compressed archive will be permanently deleted. This cannot be undone.")
                }
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.clear)
                .onDrop(of: [.fileURL], isTargeted: nil, perform: onDrop)
        )
    }
}

struct ArchiveRowView: View {
    let archive: CodebaseArchive
    let onRestore: () -> Void
    let onDelete: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 12) {
                // Icon
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(LinearGradient(
                            colors: [.blue.opacity(0.15), .purple.opacity(0.15)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ))
                        .frame(width: 44, height: 44)
                    Image(systemName: "archivebox.fill")
                        .font(.title3)
                        .foregroundColor(.blue)
                }

                // Info
                VStack(alignment: .leading, spacing: 4) {
                    Text(archive.name)
                        .font(.headline)
                        .lineLimit(1)

                    Text(archive.dateArchived, style: .relative)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .textSelection(.disabled)

                    // Size comparison bar
                    GeometryReader { geo in
                        HStack(spacing: 0) {
                            Rectangle()
                                .fill(Color.green)
                                .frame(width: geo.size.width * (1 - archive.compressionRatio))
                            Rectangle()
                                .fill(Color.orange.opacity(0.4))
                                .frame(width: geo.size.width * archive.compressionRatio)
                        }
                    }
                    .frame(height: 4)
                    .cornerRadius(2)

                    HStack(spacing: 12) {
                        Label(archive.originalSizeFormatted, systemImage: "doc.zipper")
                            .font(.caption2)
                            .foregroundColor(.secondary)

                        Image(systemName: "arrow.right")
                            .font(.caption2)
                            .foregroundColor(.secondary)

                        Label(archive.compressedSizeFormatted, systemImage: "archivebox")
                            .font(.caption2)
                            .foregroundColor(.blue)

                        Spacer()

                        Text(archive.compressionPercentage + " saved")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.green)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(Color.green.opacity(0.1))
                            .cornerRadius(4)
                    }
                }

                Spacer()

                // Actions
                VStack(spacing: 6) {
                    Button(action: onRestore) {
                        Image(systemName: "arrow.down.doc.fill")
                    }
                    .buttonStyle(BorderlessButtonStyle())
                    .help("Restore to folder")

                    Button(action: onDelete) {
                        Image(systemName: "trash.fill")
                    }
                    .buttonStyle(BorderlessButtonStyle())
                    .foregroundColor(.red)
                    .help("Delete archive")
                }
            }
            .padding(12)
        }
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(10)
        .padding(.horizontal)
        .padding(.vertical, 3)
    }
}
