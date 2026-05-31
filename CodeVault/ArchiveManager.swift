//
//  ArchiveManager.swift
//  CodeVault
//
//  Core logic: compress, restore, list, delete archives.
//  Stores archives as .tar.gz in ~/CodeVault/Archives/
//  Stores metadata as JSON in ~/CodeVault/vault.json
//

import Foundation
import Compression
import UserNotifications

class ArchiveManager: ObservableObject {
    @Published var archives: [CodebaseArchive] = []
    @Published var isWorking = false
    @Published var statusMessage = ""

    let archivesDirectory: URL
    let metadataURL: URL

    /// Directory names to exclude from archives
    let excludedDirectoryNames: Set<String> = [
        "node_modules", ".git", ".next", ".turbo", ".cache",
        "dist", "build", "coverage", ".venv", "vendor",
        "__pycache__", ".gradle", ".idea", ".vscode",
        "DerivedData", ".DS_Store"
    ]

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let vaultDir = home.appendingPathComponent("CodeVault")
        archivesDirectory = vaultDir.appendingPathComponent("Archives")
        metadataURL = vaultDir.appendingPathComponent("vault.json")

        try? FileManager.default.createDirectory(
            at: archivesDirectory,
            withIntermediateDirectories: true
        )

        loadMetadata()
        requestNotificationPermission()
    }

    // MARK: - Metadata persistence

    func saveMetadata() {
        do {
            let data = try JSONEncoder().encode(archives)
            try data.write(to: metadataURL)
        } catch {
            print("Failed to save metadata: \(error)")
        }
    }

    func loadMetadata() {
        guard
            let data = try? Data(contentsOf: metadataURL),
            let decoded = try? JSONDecoder().decode([CodebaseArchive].self, from: data)
        else { return }
        archives = decoded
    }

    // MARK: - Stats

    var stats: VaultStats {
        VaultStats.from(archives: archives)
    }

    // MARK: - Archive (shrink)

    func archive(sourceURL: URL, completion: @escaping (Bool) -> Void) {
        isWorking = true
        statusMessage = "Archiving \(sourceURL.lastPathComponent)..."

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }

            let name = sourceURL.lastPathComponent
            let archiveFileName = "\(name)-\(UUID().uuidString.prefix(8)).tar.gz"
            let archiveURL = self.archivesDirectory.appendingPathComponent(archiveFileName)

            // Calculate original size (excluding excluded dirs)
            let originalSize = self.calculateSizeSkippingExclusions(at: sourceURL)
            let fileCount = self.countFilesSkippingExclusions(at: sourceURL)

            // Create tar.gz
            let success = self.createTarGz(source: sourceURL, destination: archiveURL)

            DispatchQueue.main.async {
                self.isWorking = false

                if success, let compressedSize = self.fileSize(at: archiveURL) {
                    let archive = CodebaseArchive(
                        id: UUID(),
                        name: name,
                        originalPath: sourceURL.path,
                        dateArchived: Date(),
                        originalSizeBytes: originalSize,
                        compressedSizeBytes: compressedSize,
                        fileCount: fileCount,
                        archiveFileName: archiveFileName
                    )
                    self.archives.insert(archive, at: 0)
                    self.saveMetadata()
                    self.statusMessage = "Archived \(name) — saved \(archive.spaceSavedFormatted)"
                    self.sendNotification(
                        title: "Archive Complete",
                        body: "\(name): \(archive.originalSizeFormatted) → \(archive.compressedSizeFormatted) (\(archive.compressionPercentage) smaller)"
                    )
                    completion(true)
                } else {
                    self.statusMessage = "Failed to archive \(name)"
                    completion(false)
                }
            }
        }
    }

    // MARK: - Restore

    func restore(archive: CodebaseArchive, to destination: URL, completion: @escaping (Bool) -> Void) {
        isWorking = true
        statusMessage = "Restoring \(archive.name)..."

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }

            let archiveURL = self.archivesDirectory.appendingPathComponent(archive.archiveFileName)
            let success = self.extractTarGz(source: archiveURL, destination: destination)

            DispatchQueue.main.async {
                self.isWorking = false
                if success {
                    self.statusMessage = "Restored \(archive.name) to \(destination.path)"
                    self.sendNotification(
                        title: "Restore Complete",
                        body: "\(archive.name) restored to \(destination.lastPathComponent)/"
                    )
                } else {
                    self.statusMessage = "Failed to restore \(archive.name)"
                }
                completion(success)
            }
        }
    }

    // MARK: - Delete

    func delete(archive: CodebaseArchive) {
        let url = archivesDirectory.appendingPathComponent(archive.archiveFileName)
        try? FileManager.default.removeItem(at: url)
        archives.removeAll { $0.id == archive.id }
        saveMetadata()
        statusMessage = "Deleted \(archive.name) from vault"
    }

    // MARK: - Tar/Gz helpers

    func createTarGz(source: URL, destination: URL) -> Bool {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/tar")
        task.arguments = [
            "-czf", destination.path,
            "-C", source.deletingLastPathComponent().path,
            "--exclude=node_modules", "--exclude=.git", "--exclude=.next",
            "--exclude=.turbo", "--exclude=.cache", "--exclude=dist",
            "--exclude=build", "--exclude=coverage", "--exclude=.venv",
            "--exclude=vendor", "--exclude=__pycache__", "--exclude=.gradle",
            "--exclude=.idea", "--exclude=.vscode", "--exclude=DerivedData",
            "--exclude=.DS_Store",
            source.lastPathComponent
        ]

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe

        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus == 0
        } catch {
            print("tar error: \(error)")
            return false
        }
    }

    func extractTarGz(source: URL, destination: URL) -> Bool {
        try? FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)

        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/tar")
        task.arguments = ["-xzf", source.path, "-C", destination.path, "--strip-components=1"]

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe

        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus == 0
        } catch {
            print("untar error: \(error)")
            return false
        }
    }

    // MARK: - Size calculation

    func calculateSizeSkippingExclusions(at url: URL) -> Int64 {
        let fm = FileManager.default
        guard let enumerator = fm.enumerator(
            at: url,
            includingPropertiesForKeys: [.fileSizeKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else { return 0 }

        var total: Int64 = 0
        for case let fileURL as URL in enumerator {
            // Skip excluded directory contents
            let relPath = fileURL.path.dropFirst(url.path.count + 1)
            let components = relPath.split(separator: "/").map(String.init)
            if components.contains(where: excludedDirectoryNames.contains) {
                enumerator.skipDescendants()
                continue
            }
            if let size = try? fileURL.resourceValues(forKeys: [.fileSizeKey]).fileSize {
                total += Int64(size)
            }
        }
        return total
    }

    func countFilesSkippingExclusions(at url: URL) -> Int {
        let fm = FileManager.default
        guard let enumerator = fm.enumerator(
            at: url,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else { return 0 }

        var count = 0
        for case let fileURL as URL in enumerator {
            let relPath = fileURL.path.dropFirst(url.path.count + 1)
            let components = relPath.split(separator: "/").map(String.init)
            if components.contains(where: excludedDirectoryNames.contains) {
                enumerator.skipDescendants()
                continue
            }
            if let isDir = try? fileURL.resourceValues(forKeys: [.isDirectoryKey]).isDirectory,
               !isDir {
                count += 1
            }
        }
        return count
    }

    func fileSize(at url: URL) -> Int64? {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path) else {
            return nil
        }
        return attrs[.size] as? Int64
    }

    // MARK: - Notifications

    func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    func sendNotification(title: String, body: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 0.1, repeats: false)
        )

        UNUserNotificationCenter.current().add(request)
    }
}
