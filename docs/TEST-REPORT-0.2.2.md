# Starlit DeskDownloader 0.2.2 verification

Date: 24 November 2026. Base: dfe331f. Review branch: codex/fix-downloads-macos. PR: https://github.com/wiski-i/Starlit-DeskDownloader/pull/1

## Windows local checks

Windows 11 x64, Python 3.12.11, PySide6 6.12.0, yt-dlp 2026.11.23, imageio-ffmpeg 0.8.1, PyInstaller 6.22.3, NSIS 3.13.

- `python -m unittest -v`: 55 tests passed. The format matrix generates and decodes all 58 choices across 15 formats. Regression failures were reproduced before fixes.
- `node --test tests/extension.test.mjs`: 3 tests passed, sharing 46 URL vectors with Python.
- `tests/check_desktop_flow.py`: four source-only offscreen UI checks passed: clipboard paste + Download click with 262178 exact bytes; capture signal and duplicate filename preservation; busy rejection and cancel cleanup; real exit-confirmation button and waiting for worker cleanup.
- Windows EXEs and NSIS Setup built. Packaged host returns exactly one valid Native Messaging frame containing 15 formats/58 choices. GUI smoke startup/cleanup exits 0.
- Real published v0.2.1 Setup SHA256 was checked, then installed in an owned test directory. 0.2.1 -> 0.2.2 upgrade, same-version reinstall and uninstall passed. Sentinel user files and preferences survived; app/host registry entries and Start menu shortcut were removed. Old 0.2.1 host was tested; it has no smoke-test flag, so the new diagnostic is only used for 0.2.2 GUI checks.
- Optional real Chromium test: extension ID stayed jnhpcainmeohhdljgolpbgkhoodcfape; native catalog was 15/58. A real toolbar default action (Chrome Extensions.triggerAction, granting activeTab) opened the popup, showed the full fixture URL and 15 formats; Send launched a closed packaged desktop app and saved exact PDF bytes. The test uses an isolated browser profile, localhost and temporary host/settings registrations, then restores them.

## Linux, Intel Mac and Apple Silicon Mac

[Successful four-platform run 45475828421](https://github.com/wiski-i/Starlit-DeskDownloader/actions/runs/45475828421) tested commit 3cb2c60. All four jobs passed. Each ran 55 Python and 3 Node tests. Windows produced Setup; Intel and Apple Silicon produced separate DMGs; Linux produced the extension ZIP.

Both Mac runners checked the two actual Contents/MacOS executables, FFmpeg execution, final FFmpeg hash inventory, bundle metadata, ad-hoc signature structure, packaged host framing, offscreen packaged GUI startup/cleanup, and DMG integrity. The Mac packages are native architecture builds, not a universal binary.

The later verification scripts add source UI and Windows install/reinstall/uninstall checks to CI. Their exact latest result is available in the PR checks; earlier package results are not relabeled as a test of a different commit. Production app code is unchanged after the successful run.

## Limits and release status

- Mac global hotkey delivery through a real user session, keyboard layouts, Automation consent/denial prompts, Gatekeeper interaction, Finder user acceptance and physical Chrome context-menu selection remain interactive acceptance checks. The headless Chrome test does not claim a native context-menu click.
- Node tests cover the context-menu dispatch path and protocol behavior; live broad YouTube/Instagram/X download compatibility was not established. Downloads in automated checks use localhost fixtures.
- Ad-hoc signing is not Developer ID signing or notarization. No Apple credentials were configured.
- Hardlink publishing is atomic. Exclusive-copy fallback prevents overwrites but can show a partly copied destination until completion.
- The third-party notice identifies the shipped binary and provider; it is not a complete redistribution compliance assessment.
- PR opened; main was not merged and no new GitHub Release was published. Checked packages are available directly and as Actions artifacts.

## Reproduce optional browser check

Install Playwright only in the development virtual environment; it is not an application dependency. Install its Chromium under `.deps/browsers`, then run `python tests/check_chrome_native.py`. The script aborts if a host is already registered or the tested portable app is already running, so it must not replace a user's installation.
