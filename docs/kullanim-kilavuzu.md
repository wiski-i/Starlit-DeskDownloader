# Hızlı İndir kullanıcı kılavuzu

Hızlı İndir ile doğrudan dosya bağlantılarını ve desteklenen video sayfalarını Windows veya macOS cihazına kaydedebilirsin. Chrome eklentisi açık sekmeyi veya seçtiğin bağlantıyı masaüstü uygulamasına gönderir.

## Windows uygulamasını kur

1. 64 bit Windows 10 veya 11’de [GitHub Releases](https://github.com/wiski-i/Starlit-DeskDownloader/releases) sayfasını aç. Bir sürüm yayımlandığında **Assets** bölümünde `Starlit-DeskDownloader-Setup-…-win-x64.exe` dosyasını bulabilirsin.
2. Setup dosyasını çalıştır ve kurulum adımlarını tamamla. Kurulum bu Windows hesabına yapılır ve Chrome bağlantısını da hazırlar.
3. Başlat menüsünden **Hızlı İndir**’i aç. Pencerenin altında **Kayıt klasörü** görünür. Başka bir konum seçmek için **Değiştir**’e tıkla.

Releases sayfasında hazır paket bulunmuyorsa uygulamayı [kaynak koddan çalıştırabilir](../README.md#run-from-source) veya [kurulum paketini derleyebilirsin](../README.md#build-the-windows-package). GitHub’daki **Code → Download ZIP** düğmesi kaynak dosyalarını indirir.

## macOS uygulamasını kur

1. Apple Silicon (M serisi) icin `macos-arm64.dmg`, Intel Mac icin `macos-x64.dmg` paketini ac.
2. `HizliIndir.app` dosyasini Applications klasorune surukle.
3. DMG icindeki `register-browser-macos.command` dosyasini calistir. Komut `/Applications` ve `~/Applications` altindaki uygulamayi bulup Google Chrome baglantisini kaydeder. Uygulamayi tasirsan yeniden calistir.
4. Chrome eklentisini asagidaki gibi yukle. macOS'ta Setup EXE calistirilmaz.

Paket ad-hoc imzalidir; Apple Developer ID ve noter onayi yoktur. macOS uygulamayi engellerse Sistem Ayarlari > Gizlilik ve Guvenlik bolumundeki acma secenegini kullanman gerekebilir. Global kisayolun tarayici adresini okuyabilmesi icin Otomasyon izni istenebilir. Izin verilmezse baglantiyi yapistir veya Chrome panelini kullan. Tamamlanan dosya Finder'da secilir.

## Uygulama içinden Extension kur

Masaüstü uygulamasındaki **Extension Kur** düğmesine bas. Extension dosyaları paketin içinde gelir; ayrı ZIP indirmen gerekmez. Uygulama dosyaları sürüm yükseltmelerinden etkilenmeyen sabit bir klasöre hazırlar ve paketli uygulamanın Chrome bağlantısını kaydeder.

**Chrome’u aç** düğmesi klasör yolunu panoya kopyalar ve `chrome://extensions/` sayfasını açar. **Geliştirici modu → Paketlenmemiş öğe yükle** seçeneğine bas, klasör alanına yolu yapıştır ve seç. Chrome bu son onayı senden ister. Aynı ekranda **Yolu kopyala** ve **Klasörü aç** da bulunur. Güncelleme sonrası Extension Kur düğmesi dosyaları aynı yerde yeniler; Chrome kartından Yeniden Yükle seçeneğini kullan.

## Chrome Extension ZIP ile kur

1. Önce masaüstü uygulamasını Windows Setup veya macOS DMG ile kur. Chrome içinden biçim ve kalite seçmek için **Windows 0.2.1 veya üzeri** gerekir.
2. Release varlıklarındaki `HizliIndir-Chrome-…zip` dosyasını kalıcı bir klasöre çıkar. Kaynak kodu indirdiysen doğrudan `browser_extension` klasörünü kullanabilirsin.
3. Chrome’un adres çubuğunda `chrome://extensions` sayfasını aç.
4. **Geliştirici modu**’nu aç ve **Paketlenmemiş öğe yükle**’ye tıkla.
5. İçinde doğrudan `manifest.json` bulunan klasörü seç. Klasör seçme penceresinde dosyayı görmemen normal. Üstteki adres çubuğundan doğru klasörü açıp **Klasör Seç**’e bas.
6. **Uzantılar** menüsünden **Hızlı İndir**’i aç. İstersen menüdeki iğneyle araç çubuğuna sabitle. Chrome eklentiyi seçtiğin klasörden yüklediği için bu klasörü sakla.

Masaüstü uygulamasını kaynak koddan çalıştırıyorsan Chrome bağlantısını [geliştirme yönergelerine](../README.md#test-the-chrome-extension-on-windows) göre kaydet.

## İlk indirmeyi yap

| Yöntem | Yapacağın işlem | Kullanılan biçim ve kalite |
| --- | --- | --- |
| Masaüstü | Bir bağlantıyı **İndirme bağlantısı** alanına yapıştır ve **İndir**’e bas. | Masaüstünde seçtiğin ayar |
| Hızlı kısayol | Hızlı İndir açıkken Chrome’da ilgili sekmeye geç ve **Ctrl+Shift+F9**’a bas. | Masaüstünde seçtiğin ayar |
| Chrome paneli | Eklentiyi aç, gösterilen adresi kontrol et, **Biçim** ve **Kalite** seçip **Bu sekmeyi gönder**’e bas. | Yalnızca bu indirme için seçtiğin ayar |
| Chrome sağ tık | Bir web bağlantısına sağ tıkla ve **Bu bağlantıyı Hızlı İndir’e gönder**’i seç. | Masaüstünde seçtiğin ayar |

Örneğin masaüstünde **MP4 · 1080p’ye kadar** seçiliyken klavye kısayolu bu ayarı kullanır. Bir videonun sesini almak istediğinde Chrome panelinden **MP3 · 320 kbps** seçebilirsin. Sonraki kısayol yine masaüstündeki MP4 ayarıyla çalışır.

İlerlemeyi masaüstü penceresinde görürsün. Bir sayfada birden fazla uygun video varsa uygulamada **Bir video seç** listesi açılır. İndirme tamamlanınca **Dosyayı göster**, dosyayı Windows Gezgini’nde açar. Bir indirme devam ederken tamamlanmasını bekleyebilir veya **İptal et**’i kullanabilirsin.

Pencereyi kapatınca Hızlı İndir, saatin yanındaki bildirim alanında çalışmaya devam eder. Simgeye tıklayarak pencereyi geri açabilir, simgeye sağ tıklayıp **Çıkış**’ı seçerek uygulamayı kapatabilirsin. Kısayolu **Ayarlar → Klavye kısayolu** bölümünden değiştirebilirsin.

## Biçim ve kaliteyi seç

| İstediğin çıktı | Seçim |
| --- | --- |
| Dosyayı olduğu gibi kaydetmek | **Orijinal**. Doğrudan dosyalar aynı şekilde kaydedilir. Video sayfalarında bir akış kalitesine öncelik verebilirsin. |
| Video | **MP4, MKV, WebM, MOV**. Kalite listesindeki çözünürlük üst sınırdır. Kaynak daha düşük çözünürlükteyse büyütülmez. |
| Sıkıştırılmış ses | **MP3, M4A, Opus, AAC, Ogg Vorbis**. Kalite seçimi çıktı bit hızını belirler. |
| WAV veya FLAC | **WAV**’da PCM bit derinliğini, **FLAC**’ta kayıpsız sıkıştırma seviyesini seçersin. |
| Eski oynatıcı ve cihazlar | **AVI, 3GP, FLV**. Bu biçimlerin kendi çözünürlük seçenekleri vardır. |

ZIP veya PDF gibi doğrudan dosyalar, panelde bir ses ya da video biçimi seçili olsa da kendi biçimlerini korur.

## Güncelle veya kaldır

- **Windows güncellemesi:** Bildirim alanından **Çıkış**’ı seç ve yeni Setup dosyasını çalıştır. İndirme klasörün ve uygulama tercihlerin korunur.
- **Chrome güncellemesi:** Yeni eklenti dosyalarını aynı klasöre çıkar. `chrome://extensions` sayfasında **Hızlı İndir → Yeniden Yükle**’ye bas.
- **Kaldırma:** Windows 11’de **Ayarlar → Uygulamalar → Yüklü uygulamalar**, Windows 10’da **Ayarlar → Uygulamalar → Uygulamalar ve özellikler** bölümünden **Hızlı İndir**’i kaldırabilirsin. Chrome eklentisini kaldırmak için `chrome://extensions` sayfasında eklenti kartındaki **Kaldır** düğmesini kullan.

## Sorun gider

| Belirti | Ne yapabilirsin? |
| --- | --- |
| **Manifest bulunamadı** | ZIP’i çıkar ve içinde doğrudan `manifest.json` bulunan klasörü seç. |
| **Bu sekme gönderilemiyor** | `chrome://extensions` veya yeni sekme yerine bir HTTP veya HTTPS web sayfası aç ve eklentiyi orada kullan. |
| **Hızlı İndir’e bağlanılamadı** | Masaüstü uygulamasını açabildiğini kontrol et. Windows Setup veya macOS kayıt komutuyla Chrome bağlantısını kurduğundan ve eklentinin etkin olduğundan emin ol. |
| **Chrome panelinde Biçim ve Kalite yok** | Windows uygulamasını 0.2.1 veya üzeri sürüme güncelle, ardından Chrome eklentisini yeniden yükle. |
| **Kısayol çalışmıyor** | Hızlı İndir’in bildirim alanında çalıştığını ve Chrome’un önde olduğunu kontrol et. Adres yine alınamıyorsa bağlantıyı masaüstü uygulamasına yapıştır. |
| **İndirme tamamlanamadı** | Bağlantıyı ve kayıt klasörünü kontrol et. Genel bir web sayfası desteklenmiyorsa doğrudan dosya bağlantısını dene. |
