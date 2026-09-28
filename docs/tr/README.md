# OBS -> YouTube Otomatik Thumbnail

Bu araç OBS WebSocket üzerinden yayın görüntüsü alır ve YouTube canlı yayın thumbnail'ini otomatik olarak günceller. Varsayılan ayar 10 dakikada bir güncellemedir.

## Özellikler

- OBS'deki aktif program sahnesinden görüntü alır.
- Görüntüyü YouTube thumbnail boyutuna uygun şekilde `1280x720` hazırlar.
- Aktif YouTube canlı yayınını otomatik bulabilir.
- İsterseniz belirli bir YouTube video ID'sine yükleme yapabilir.
- OBS açılınca arka planda gizlice başlar.
- OBS kapanınca thumbnailer sürecini kapatır.
- Program zaten açıksa ikinci kopyayı açmaz.
- Log ve son thumbnail dosyasını yerel klasörde saklar.

## Gereksinimler

- Windows
- Python 3.10 veya üzeri
- OBS Studio
- OBS WebSocket açık olmalı
- YouTube Data API v3 etkin bir Google Cloud projesi
- YouTube kanalında özel thumbnail yükleme yetkisi

OBS 28 ve üzeri sürümlerde OBS WebSocket yerleşik gelir. OBS içinde `Tools > WebSocket Server Settings` menüsünden açabilirsiniz.

## Google / YouTube API Kurulumu

1. Google Cloud Console'da bir proje oluşturun veya mevcut projenizi açın.
2. `YouTube Data API v3` API'sini etkinleştirin.
3. OAuth consent screen ayarlarını tamamlayın.
4. `Credentials` bölümünden `OAuth client ID` oluşturun.
5. Uygulama tipi olarak `Desktop app` seçin.
6. JSON dosyasını indirin.
7. İndirdiğiniz dosyayı proje klasörüne `client_secret.json` adıyla koyun.

`client_secret.json` ve `token.json` GitHub'a yüklenmez. Bu dosyalar `.gitignore` içindedir.

## Kurulum

Proje klasöründe PowerShell açın:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.sample.json config.json
notepad config.json
```

`config.json` içindeki OBS şifresi, YouTube ayarları ve çalışma aralığını düzenleyin.

## İlk YouTube Yetkilendirmesi

```powershell
.\.venv\Scripts\python.exe thumbnailer.py auth --config config.json
```

Tarayıcı açılır. YouTube kanalınızla giriş yaptıktan sonra yetki bilgisi `token.json` dosyasına kaydedilir.

## Manuel Kullanım

OBS bağlantısını ve görüntü almayı test etmek için:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py test-obs --config config.json
```

YouTube'a yükleme yapmadan tek sefer test:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py once --config config.json --dry-run
```

YouTube thumbnail'ini tek sefer güncellemek için:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py once --config config.json
```

Sürekli çalıştırmak için:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py run --config config.json
```

## OBS Açılınca Otomatik Başlatma

Windows başlangıcına watcher eklemek için:

```powershell
.\install_autostart.bat
```

Bu işlem Windows Başlangıç klasörüne gizli çalışan bir kısayol ekler. Windows oturumu açıldığında watcher arka planda bekler. OBS açıldığında thumbnailer başlar, OBS kapandığında thumbnailer kapanır.

Watcher'ı hemen başlatmak için Windows'u yeniden başlatabilir veya şu dosyayı çift tıklayabilirsiniz:

```text
start_watcher_hidden.vbs
```

Otomatik başlatmayı kaldırmak için:

```powershell
.\uninstall_autostart.bat
```

## Config Alanları

`obs.host`: OBS WebSocket adresi. Varsayılan `127.0.0.1`.

`obs.port`: OBS WebSocket portu. Varsayılan `4455`.

`obs.password`: OBS WebSocket şifresi. Boş bırakmak yerine isterseniz `OBS_WEBSOCKET_PASSWORD` ortam değişkenini kullanabilirsiniz.

`obs.source_name`: Boş veya `null` kalırsa aktif program sahnesi kullanılır. Belirli bir sahne/kaynak istiyorsanız adını yazın.

`youtube.client_secrets_file`: Google OAuth client JSON dosyası.

`youtube.token_file`: İlk yetkilendirmeden sonra oluşan token dosyası.

`youtube.video_id`: Boş bırakılırsa aktif canlı yayın otomatik bulunur. Belirli bir yayına yüklemek isterseniz video ID yazın.

`youtube.find_active_broadcast`: Aktif canlı yayını otomatik bulma ayarı.

`thumbnail.width` / `thumbnail.height`: Thumbnail boyutu. YouTube için önerilen değer `1280x720`.

`thumbnail.output_dir`: Hazırlanan thumbnail dosyalarının yazılacağı klasör.

`schedule.interval_seconds`: Güncelleme aralığı. `600` saniye = 10 dakika.

`schedule.only_when_obs_streaming`: `true` iken OBS yayında değilse YouTube'a yükleme yapılmaz.

## Loglar

- `thumbnailer.log`: OBS görüntü alma ve YouTube yükleme kayıtları.
- `watcher.log`: OBS açıldı mı, thumbnailer başladı mı, kapandı mı kayıtları.
- `thumbnails/latest-thumbnail.jpg`: En son hazırlanan thumbnail.

## Güvenlik

GitHub'a şu dosyaları yüklemeyin:

- `config.json`
- `client_secret.json`
- `token.json`
- `thumbnailer.log`
- `watcher.log`
- `thumbnails/`

Bu dosyalar `.gitignore` içinde tutulur.

## Sorun Giderme

OBS bulunuyor ama thumbnailer başlamıyorsa `watcher.log` dosyasını kontrol edin.

OBS WebSocket bağlantısı başarısızsa OBS içinde WebSocket ayarlarını, portu ve şifreyi kontrol edin.

YouTube yetkilendirmesi hata verirse `token.json` dosyasını silip `auth` komutunu tekrar çalıştırın.

Aktif canlı yayın bulunamıyorsa `config.json` içine `youtube.video_id` alanını manuel girin.
