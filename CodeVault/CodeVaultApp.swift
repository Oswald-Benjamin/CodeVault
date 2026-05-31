//
//  CodeVaultApp.swift
//  CodeVault
//
//  Main app entry point.
//

import SwiftUI

@main
struct CodeVaultApp: App {
    @StateObject private var archiveManager = ArchiveManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(archiveManager)
                .frame(minWidth: 800, minHeight: 550)
        }
        .windowResizability(.contentSize)
    }
}
