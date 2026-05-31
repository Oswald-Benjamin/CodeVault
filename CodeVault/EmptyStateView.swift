//
//  EmptyStateView.swift
//  CodeVault
//
//  Shown when there are no archives yet — invites drag & drop.
//

import SwiftUI
import UniformTypeIdentifiers

struct EmptyStateView: View {
    @Binding var isTargeted: Bool

    var body: some View {
        VStack(spacing: 16) {
            Spacer()

            ZStack {
                Circle()
                    .fill(isTargeted
                          ? Color.blue.opacity(0.15)
                          : Color.secondary.opacity(0.08))
                    .frame(width: 100, height: 100)

                Image(systemName: isTargeted ? "arrow.down.doc.fill" : "archivebox.fill")
                    .font(.system(size: 40))
                    .foregroundColor(isTargeted ? .blue : .secondary)
            }
            .animation(.easeInOut(duration: 0.2), value: isTargeted)

            VStack(spacing: 6) {
                Text("Drop a codebase here")
                    .font(.headline)
                    .foregroundColor(isTargeted ? .blue : .primary)

                Text("Drag & drop a folder, or use the toolbar button")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Excluded from archives:")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.secondary)

                Text("node_modules · .git · .next · dist · build · .venv · vendor")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .foregroundColor(.tertiary)
            }
            .padding(.top, 8)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onDrop(of: [.fileURL], isTargeted: $isTargeted) { providers in
            // Handled by parent
            false
        }
    }
}
