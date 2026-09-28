# OBS -> YouTube Automatic Thumbnailer

This tool captures a frame from OBS through OBS WebSocket and automatically updates the thumbnail of your YouTube live stream. The default update interval is 10 minutes.

## Features

- Captures the active OBS program scene.
- Prepares a YouTube-friendly `1280x720` thumbnail.
- Can automatically find your active YouTube live broadcast.
- Can target a specific YouTube video ID.
- Starts silently in the background when OBS opens.
- Stops the thumbnailer process when OBS closes.
- Prevents duplicate watcher and thumbnailer instances.
- Keeps local logs and the latest generated thumbnail.

## Requirements

- Windows
- Python 3.10 or newer
- OBS Studio
- OBS WebSocket enabled
- A Google Cloud project with YouTube Data API v3 enabled
- A YouTube channel that is allowed to upload custom thumbnails

OBS 28 and newer include OBS WebSocket by default. You can enable it from `Tools > WebSocket Server Settings` in OBS.

## Google / YouTube API Setup

1. Create or open a project in Google Cloud Console.
2. Enable `YouTube Data API v3`.
3. Complete the OAuth consent screen setup.
4. Create an `OAuth client ID`.
5. Select `Desktop app` as the application type.
6. Download the JSON file.
7. Put the downloaded file into the project folder as `client_secret.json`.

`client_secret.json` and `token.json` are not committed to GitHub. They are ignored by `.gitignore`.

## Installation

Open PowerShell in the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.sample.json config.json
notepad config.json
```

Edit `config.json` with your OBS password, YouTube settings, and update interval.

## First YouTube Authorization

```powershell
.\.venv\Scripts\python.exe thumbnailer.py auth --config config.json
```

A browser window will open. After you sign in with your YouTube channel, credentials are saved to `token.json`.

## Manual Usage

Test OBS connectivity and screenshot capture:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py test-obs --config config.json
```

Run a single test without uploading to YouTube:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py once --config config.json --dry-run
```

Update the YouTube thumbnail once:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py once --config config.json
```

Run continuously:

```powershell
.\.venv\Scripts\python.exe thumbnailer.py run --config config.json
```

## Start Automatically With OBS

Install the watcher into Windows Startup:

```powershell
.\install_autostart.bat
```

This adds a hidden startup shortcut. When you sign in to Windows, the watcher waits in the background. When OBS opens, the thumbnailer starts. When OBS closes, the thumbnailer stops.

To start the watcher immediately without restarting Windows, double-click:

```text
start_watcher_hidden.vbs
```

To remove automatic startup:

```powershell
.\uninstall_autostart.bat
```

## Configuration Fields

`obs.host`: OBS WebSocket host. Default is `127.0.0.1`.

`obs.port`: OBS WebSocket port. Default is `4455`.

`obs.password`: OBS WebSocket password. You can also use the `OBS_WEBSOCKET_PASSWORD` environment variable.

`obs.source_name`: If empty or `null`, the active program scene is used. Set a scene/source name if you want a specific source.

`youtube.client_secrets_file`: Google OAuth client JSON file.

`youtube.token_file`: Token file created after first authorization.

`youtube.video_id`: If empty, the active live broadcast is discovered automatically. Set a video ID to target a specific stream.

`youtube.find_active_broadcast`: Enables active live broadcast discovery.

`thumbnail.width` / `thumbnail.height`: Thumbnail size. YouTube recommends `1280x720`.

`thumbnail.output_dir`: Folder for generated thumbnail files.

`schedule.interval_seconds`: Update interval. `600` seconds = 10 minutes.

`schedule.only_when_obs_streaming`: If `true`, no upload is made while OBS is not actively streaming.

## Logs

- `thumbnailer.log`: OBS capture and YouTube upload logs.
- `watcher.log`: OBS detection and thumbnailer start/stop logs.
- `thumbnails/latest-thumbnail.jpg`: Latest generated thumbnail.

## Security

Do not upload these files to GitHub:

- `config.json`
- `client_secret.json`
- `token.json`
- `thumbnailer.log`
- `watcher.log`
- `thumbnails/`

They are already listed in `.gitignore`.

## Troubleshooting

If OBS is detected but the thumbnailer does not start, check `watcher.log`.

If OBS WebSocket connection fails, check OBS WebSocket settings, port, and password.

If YouTube authorization fails, delete `token.json` and run the `auth` command again.

If no active live broadcast is found, set `youtube.video_id` manually in `config.json`.
