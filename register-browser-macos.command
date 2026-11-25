#!/bin/bash
set -eu
for app in /Applications/HizliIndir.app "$HOME/Applications/HizliIndir.app"; do
    host="$app/Contents/MacOS/HizliIndirBrowserHost"
    if [ -x "$host" ]; then
        "$host" --register-browser-host
        printf '\nChrome kaydı tamamlandı. Chrome eklentisini yeniden açabilirsin.\n'
        exit 0
    fi
done
printf 'Önce HizliIndir.app uygulamasını /Applications veya ~/Applications klasörüne taşı.\n' >&2
exit 1
