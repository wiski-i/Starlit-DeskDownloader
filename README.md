# Starlit DeskDownloader

Hızlı İndir is a Windows desktop app for saving direct file links and supported videos from Chrome.

**[Türkçe kullanıcı kılavuzu](docs/kullanim-kilavuzu.md)** · Windows ve Chrome kurulumu, ilk indirme, biçim ve kalite seçimi, sorun giderme.

## Install on Windows

Run the Windows x64 `Setup.exe` from [GitHub Releases](https://github.com/wiski-i/Starlit-DeskDownloader/releases) when a release is available. Setup installs for the current Windows account, adds **Hızlı İndir** to the Start menu, and registers the local connection for the Chrome extension. Close the app from its tray menu before updating or uninstalling it. You can remove it from **Settings → Apps → Installed apps**. Your download folder and preferences are kept.

The development Chrome extension is a separate ZIP. Extract it into a folder you plan to keep, then use **Load unpacked** on `chrome://extensions` and select that folder. Windows Setup registers the matching host automatically. The manual registry step below is only for testing a portable build.

## Open the packaged app

Double-click `dist/HizliIndir/HizliIndir.exe`. Keep the `_internal` folder alongside the executable if you move it.

1. Open a file URL or supported video page in Chrome and press `Ctrl+Shift+F9`.
2. Click the Hızlı İndir icon by the Windows clock to see progress. If the page has multiple supported videos, select one in the app.
3. After the download completes, select **Dosyayı göster** to locate the file.

You can also paste any HTTP or HTTPS file URL into the app. Select **Değiştir** to choose another destination. To change the global shortcut, open **Ayarlar → Klavye kısayolu**, press the combination, and select **Kaydet**. Closing the window keeps the shortcut active in the notification area. Open the executable again or click its notification icon to bring back the window. To stop the app, select **Çıkış** from the notification icon menu.

Pick **Biçim** and **Kalite** before downloading. The keyboard shortcut and Chrome’s right-click menu use the last desktop selection. With Windows Setup 0.2.1 and Chrome extension 0.2.1, the Chrome toolbar popup displays the full tab address, starts with your desktop settings, and lets you override them for a single download. If you already loaded the unpacked extension from the updated folder, use **Reload** on its card at `chrome://extensions`.

**Orijinal** keeps direct files intact and can prefer a resolution on video pages. Video conversion can lower the source resolution, and the quality label is a ceiling. Audio bit rates apply to the encoded output. For WAV the quality setting controls PCM bit depth. For FLAC it controls lossless compression. Ordinary files such as ZIP and PDF are always saved as received.

Chrome address capture depends on Windows accessibility. If Chrome does not expose the active address, paste a link. The download engine supports direct file responses and supported video pages. For other pages, copy the underlying file URL. Some video extractors need Node.js 22+ or Deno 2.3+ and the `yt-dlp-ejs` package.

## Run from source

Use 64-bit Windows 10 or 11 and Python 3.11 or newer for a fresh installation.

```powershell
python -m pip install -r requirements.txt
```

```powershell
python app.py
```

## Build the Windows package

```powershell
python -m pip install pyinstaller
```

```powershell
.\build.ps1
```

To use a compatible existing FFmpeg executable, pass its path as `-Ffmpeg`. The build places it inside the Windows package.

With NSIS 3.11 on PATH, package that build into a Windows setup executable:

```powershell
.\build-installer.ps1 -Version 0.2.1
```

Pass `-MakeNsis` with the full path to `makensis.exe` if it is outside PATH. The installer is written to `dist`. The version determines the installed application directory, so use a higher version for an update with a different set of files.

## Test the Chrome extension on Windows

The development extension lives in `browser_extension`. Its popup sends the active tab, and **Bu bağlantıyı Hızlı İndir’e gönder** sends a link from Chrome’s context menu. The desktop app opens if needed and uses its current download folder. If another download is in progress, the extension reports that the app is busy.

1. Build the Windows package.
2. In `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**, and select the `browser_extension` folder.
3. From the repository root, register the native host for the current Windows account:

   ```powershell
   $manifest = (Resolve-Path '.\dist\HizliIndir\com.starlit.deskdownloader.json').Path
   reg add 'HKCU\Software\Google\Chrome\NativeMessagingHosts\com.starlit.deskdownloader' /ve /t REG_SZ /d $manifest /f
   ```

To undo the development registration, remove that host's key and remove the unpacked extension in Chrome. The host manifest, `HizliIndirBrowserHost.exe`, `HizliIndir.exe`, and `_internal` must stay in the same directory. The public key in the development manifest keeps its extension ID stable. A future store build must register its own ID in `allowed_origins` if it differs.

## Run the download integration tests

```powershell
python -m unittest -v test_downloads
```

The tests generate their own files and serve them on localhost. FFmpeg is required for video tests. Set `VIDEOINDIR_FFMPEG` to an existing executable path if FFmpeg is outside `PATH`.

## License

Starlit DeskDownloader is licensed under the [GNU General Public License v3.0 only](LICENSE).

The Windows x64 0.2.1 package includes the GPL-enabled [Gyan FFmpeg 9.0.2 essentials build](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2) as a separate executable. Gyan identifies [FFmpeg commit `946fcce07b`](https://github.com/FFmpeg/FFmpeg/commit/946fcce07b) as the source for that build. The SHA-256 of the packaged executable is `3256173f3f8bffd7df12227c68adf68025edb1832273a9530688a7bb1ed8edec`.
