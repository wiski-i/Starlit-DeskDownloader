# Starlit DeskDownloader

Hızlı İndir is a Windows desktop app for saving direct file links and supported videos from Chrome.

## Open the packaged app

Double-click `dist/HizliIndir/HizliIndir.exe`. Keep the `_internal` folder alongside the executable if you move it.

1. Open a file URL or supported video page in Chrome and press `Ctrl+Shift+F9`.
2. Click the Hızlı İndir icon by the Windows clock to see progress. If the page has multiple supported videos, select one in the app.
3. After the download completes, select **Dosyayı göster** to locate the file.

You can also paste any HTTP or HTTPS file URL into the app. Select **Değiştir** to choose another destination. To change the global shortcut, open **Ayarlar → Klavye kısayolu**, press the combination, and select **Kaydet**. Closing the window keeps the shortcut active in the notification area. Open the executable again or click its notification icon to bring back the window. To stop the app, select **Çıkış** from the notification icon menu.

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

## Run the download integration tests

```powershell
python -m unittest -v test_downloads
```

The tests generate their own files and serve them on localhost. FFmpeg is required for video tests. Set `VIDEOINDIR_FFMPEG` to an existing executable path if FFmpeg is outside `PATH`.

## License

Starlit DeskDownloader is licensed under the [GNU General Public License v3.0 only](LICENSE).
