//
//  CodebaseArchive.swift
//  CodeVault
//
//  Data model representing a single archived codebase.
//

import Foundation

struct CodebaseArchive: Identifiable, Codable {
    let id: UUID
    var name: String
    var originalPath: String
    let dateArchived: Date
    let originalSizeBytes: Int64
    let compressedSizeBytes: Int64
    let fileCount: Int
    var archiveFileName: String

    var originalSizeFormatted: String {
        Self.formatBytes(originalSizeBytes)
    }

    var compressedSizeFormatted: String {
        Self.formatBytes(compressedSizeBytes)
    }

    var spaceSavedBytes: Int64 {
        originalSizeBytes - compressedSizeBytes
    }

    var spaceSavedFormatted: String {
        Self.formatBytes(spaceSavedBytes)
    }

    var compressionRatio: Double {
        guard originalSizeBytes > 0 else { return 0 }
        return Double(compressedSizeBytes) / Double(originalSizeBytes)
    }

    var compressionPercentage: String {
        let pct = (1.0 - compressionRatio) * 100
        return String(format: "%.0f%%", pct)
    }

    static func formatBytes(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: bytes)
    }
}

// MARK: - Stats aggregate

struct VaultStats {
    let totalArchives: Int
    let totalOriginalBytes: Int64
    let totalCompressedBytes: Int64
    let totalSavedBytes: Int64

    var totalOriginalFormatted: String {
        CodebaseArchive.formatBytes(totalOriginalBytes)
    }

    var totalCompressedFormatted: String {
        CodebaseArchive.formatBytes(totalCompressedBytes)
    }

    var totalSavedFormatted: String {
        CodebaseArchive.formatBytes(totalSavedBytes)
    }

    var averageCompressionPercentage: String {
        guard totalOriginalBytes > 0 else { return "0%" }
        let ratio = Double(totalCompressedBytes) / Double(totalOriginalBytes)
        let pct = (1.0 - ratio) * 100
        return String(format: "%.0f%%", pct)
    }

    static func from(archives: [CodebaseArchive]) -> VaultStats {
        VaultStats(
            totalArchives: archives.count,
            totalOriginalBytes: archives.reduce(0) { $0 + $1.originalSizeBytes },
            totalCompressedBytes: archives.reduce(0) { $0 + $1.compressedSizeBytes },
            totalSavedBytes: archives.reduce(0) { $0 + $1.spaceSavedBytes }
        )
    }
}
