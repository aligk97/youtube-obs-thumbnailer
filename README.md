# OBS -> YouTube Automatic Thumbnailer

Automatically updates your YouTube live stream thumbnail with a fresh frame captured from OBS. It can also run quietly in the background: when OBS opens, the thumbnailer starts; when OBS closes, it stops.

OBS'den alınan güncel görüntüyle YouTube canlı yayın thumbnail'ini otomatik günceller. Arka planda sessiz çalışabilir: OBS açılınca başlar, OBS kapanınca durur.

## Documentation

- [Türkçe kurulum ve kullanım rehberi](docs/tr/README.md)
- [English installation and usage guide](docs/en/README.md)

## Quick Start

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.sample.json config.json
notepad config.json
.\.venv\Scripts\python.exe thumbnailer.py auth --config config.json
.\.venv\Scripts\python.exe thumbnailer.py run --config config.json
```

Install the hidden OBS watcher:

```powershell
.\install_autostart.bat
```

## What It Does

- Captures the active OBS program scene through OBS WebSocket.
- Creates a YouTube-ready `1280x720` thumbnail.
- Finds the active YouTube live broadcast automatically, or uses a configured video ID.
- Updates the thumbnail every 10 minutes by default.
- Prevents duplicate watcher and thumbnailer instances.
- Keeps secrets, tokens, logs, and generated thumbnails out of Git.

## Security Note

Do not commit `config.json`, `client_secret.json`, `token.json`, logs, or generated thumbnails. They are already ignored by `.gitignore`.
