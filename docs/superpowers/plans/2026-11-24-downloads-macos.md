# DeskDownloader 0.2.2 implementation plan

Goal: restore the handoff changes on current dfe331f, fix download regressions, support macOS and deliver tested Windows x64 / macOS arm64 and x64 packages.
Architecture: keep Qt, yt-dlp and FFmpeg, separate only existing platform services. Preserve extension identity, UI and all 15 formats / 58 quality choices. No new runtime dependency.
Spec: user-supplied Starlit DeskDownloader handoff (24 November 2026), sections 1-19. User requested continuation.

## Tasks and ownership
- [ ] Download regressions (root): test_publish.py then downloads.py / direct_files.py and test_downloads.py. Prove competing publisher preservation, exclusive copy fallback and cleanup, full UTF-8 filename bound including Unicode suffix, BOM HTML/MPD handoff, malformed URL rejection. Run Python suite.
- [ ] Platform services (platform worker): shortcuts.py, desktop.py, unix_desktop.py, mac_hotkey.py, windows.py, app.py, test_platform.py. Common interface unchanged; only primary removes stale sockets, second instance requests reopen, Carbon lifecycle and AppleScript timeout tested. Linux capture explicitly unsupported.
- [ ] Native bridge (native worker): browser_bridge.py, native_host.py, extension bridge/manifest/popup, test_bridge.py and tests/extension.test.mjs. Windows-only APIs conditional, Chrome Mac registration correctly quotes source paths and uses packaged host. Preserve callback failures and malformed framing as protocol responses.
- [ ] Packaging (packages worker): shared spec, Windows scripts, Mac builder/registration command, third-party inventory, verified requirements, CI, packaged-host probe. Windows local setup and two Mac runner builds with hashes; no automatic Release or Developer ID claims.
- [ ] Integration (root): full suites, installed Windows protocol/launch/reopen/cancel/exit checks, PR + real Actions, collect three packages and extension ZIP with SHA256SUMS; Turkish usage and exact test report.

## Review focus
Filename suffix plus numbering must fit UTF-8 filesystem limit; fallback copies may be visible until complete. URL parsing must reject credential/backslash normalization differences. Mac host and application paths must resolve in actual bundle, stdout must remain framing-only. Socket cleanup must not disrupt running primary. Real Mac CI smoke cannot prove interactive permission prompts, keyboard layouts or notarization.

## Verification commands
.venv/Scripts/python.exe -m unittest -v
node --test tests/extension.test.mjs
./build.ps1 -Python .venv/Scripts/python.exe
.venv/Scripts/python.exe tests/check_packaged_host.py dist/HizliIndir/HizliIndirBrowserHost.exe
./build-installer.ps1
Mac runners: python build_macos.py and packaged host / offscreen GUI checks.
