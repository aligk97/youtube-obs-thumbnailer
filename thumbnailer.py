from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from single_instance import SingleInstance, make_instance_name

try:
    import websockets
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from PIL import Image, ImageOps
except ImportError as exc:
    print(
        "Eksik Python paketi var. Once su komutu calistirin:\n"
        "  python -m pip install -r requirements.txt\n\n"
        f"Ayrinti: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(2)


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
SUPPORTED_IMAGE_FORMATS = {"jpg", "jpeg", "png"}
MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}

DEFAULT_CONFIG: dict[str, Any] = {
    "obs": {
        "host": "127.0.0.1",
        "port": 4455,
        "password": "",
        "source_name": None,
    },
    "youtube": {
        "client_secrets_file": "client_secret.json",
        "token_file": "token.json",
        "video_id": "",
        "find_active_broadcast": True,
    },
    "thumbnail": {
        "width": 1280,
        "height": 720,
        "format": "jpg",
        "quality": 90,
        "save_history": True,
        "output_dir": "thumbnails",
    },
    "schedule": {
        "interval_seconds": 600,
        "retry_seconds": 60,
        "run_immediately": True,
        "only_when_obs_streaming": True,
    },
    "logging": {
        "log_file": "thumbnailer.log",
    },
}


class OBSRequestError(RuntimeError):
    pass


class StreamNotActive(RuntimeError):
    pass


@dataclass
class CaptureResult:
    source_name: str
    raw_image_path: Path


@dataclass
class CycleResult:
    uploaded: bool
    skipped_reason: str | None = None


class OBSWebSocketClient:
    def __init__(self, host: str, port: int, password: str | None) -> None:
        self.host = host
        self.port = port
        self.password = password or ""
        self.websocket: Any = None

    async def connect(self) -> None:
        url = f"ws://{self.host}:{self.port}"
        self.websocket = await websockets.connect(url, subprotocols=["obswebsocket.json"])
        hello = json.loads(await self.websocket.recv())
        if hello.get("op") != 0:
            raise OBSRequestError(f"OBS beklenmeyen ilk mesaj gonderdi: {hello!r}")

        hello_data = hello.get("d", {})
        identify_data: dict[str, Any] = {
            "rpcVersion": min(int(hello_data.get("rpcVersion", 1)), 1),
            "eventSubscriptions": 0,
        }

        auth = hello_data.get("authentication")
        if auth:
            if not self.password:
                raise OBSRequestError(
                    "OBS WebSocket sifre istiyor, ama config icinde obs.password bos."
                )
            identify_data["authentication"] = self._make_authentication(
                self.password,
                auth["salt"],
                auth["challenge"],
            )

        await self.websocket.send(json.dumps({"op": 1, "d": identify_data}))
        identified = json.loads(await self.websocket.recv())
        if identified.get("op") != 2:
            raise OBSRequestError(f"OBS kimlik dogrulamayi kabul etmedi: {identified!r}")

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def request(self, request_type: str, request_data: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.websocket:
            raise OBSRequestError("OBS WebSocket baglantisi acik degil.")

        request_id = str(uuid.uuid4())
        payload = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
            },
        }
        if request_data is not None:
            payload["d"]["requestData"] = request_data

        await self.websocket.send(json.dumps(payload))
        while True:
            message = json.loads(await self.websocket.recv())
            if message.get("op") != 7:
                continue

            data = message.get("d", {})
            if data.get("requestId") != request_id:
                continue

            status = data.get("requestStatus", {})
            if not status.get("result"):
                code = status.get("code")
                comment = status.get("comment", "")
                raise OBSRequestError(f"{request_type} basarisiz oldu. Kod={code} {comment}")

            return data.get("responseData", {})

    @staticmethod
    def _make_authentication(password: str, salt: str, challenge: str) -> str:
        secret = hashlib.sha256((password + salt).encode("utf-8")).digest()
        encoded_secret = base64.b64encode(secret).decode("utf-8")
        auth = hashlib.sha256((encoded_secret + challenge).encode("utf-8")).digest()
        return base64.b64encode(auth).decode("utf-8")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_path(config_dir: Path, value: str | os.PathLike[str]) -> Path:
    expanded = os.path.expandvars(str(value))
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return path


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config dosyasi yok: {config_path}\n"
            "Once `python thumbnailer.py init-config` calistirin."
        )

    with config_path.open("r", encoding="utf-8") as handle:
        user_config = json.load(handle)
    return deep_merge(DEFAULT_CONFIG, user_config)


def write_initial_config(target: Path, overwrite: bool) -> None:
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} zaten var. Uzerine yazmak icin --overwrite kullanin.")
    target.write_text(
        json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def configure_logging(config: dict[str, Any], config_dir: Path) -> None:
    log_file = resolve_path(config_dir, config["logging"]["log_file"])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    if sys.stdout is not None:
        handlers.insert(0, logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def decode_obs_image(image_data: str) -> bytes:
    if "," in image_data and image_data.lower().startswith("data:"):
        image_data = image_data.split(",", 1)[1]
    return base64.b64decode(image_data)


async def capture_obs_frame(config: dict[str, Any], config_dir: Path, raw_image_path: Path) -> CaptureResult:
    obs_config = config["obs"]
    thumbnail_config = config["thumbnail"]
    schedule_config = config["schedule"]

    password = os.getenv("OBS_WEBSOCKET_PASSWORD", obs_config.get("password") or "")
    client = OBSWebSocketClient(
        host=str(obs_config["host"]),
        port=int(obs_config["port"]),
        password=password,
    )

    await client.connect()
    try:
        if schedule_config.get("only_when_obs_streaming", True):
            stream_status = await client.request("GetStreamStatus")
            if not stream_status.get("outputActive"):
                raise StreamNotActive("OBS stream cikisi aktif degil.")

        source_name = obs_config.get("source_name")
        if not source_name:
            current_scene = await client.request("GetCurrentProgramScene")
            source_name = current_scene.get("sceneName") or current_scene.get("currentProgramSceneName")
        if not source_name:
            raise OBSRequestError("OBS aktif sahne adini dondurmedi.")

        image_format = str(thumbnail_config["format"]).lower()
        if image_format == "jpeg":
            image_format = "jpg"
        if image_format not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"Desteklenmeyen gorsel formati: {image_format}")

        screenshot = await client.request(
            "GetSourceScreenshot",
            {
                "sourceName": source_name,
                "imageFormat": image_format,
                "imageWidth": int(thumbnail_config["width"]),
                "imageHeight": int(thumbnail_config["height"]),
                "imageCompressionQuality": int(thumbnail_config["quality"]),
            },
        )
        raw_image_path.parent.mkdir(parents=True, exist_ok=True)
        raw_image_path.write_bytes(decode_obs_image(screenshot["imageData"]))
        return CaptureResult(source_name=str(source_name), raw_image_path=raw_image_path)
    finally:
        await client.close()


def prepare_thumbnail(config: dict[str, Any], source_path: Path, output_path: Path) -> Path:
    thumbnail_config = config["thumbnail"]
    width = int(thumbnail_config["width"])
    height = int(thumbnail_config["height"])
    quality = int(thumbnail_config["quality"])
    image_format = str(thumbnail_config["format"]).lower()
    if image_format == "jpeg":
        image_format = "jpg"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image = image.convert("RGB")
        image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        if image_format == "png":
            image.save(output_path, format="PNG", optimize=True)
        else:
            image.save(
                output_path,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )
    return output_path


def build_youtube_service(config: dict[str, Any], config_dir: Path) -> Any:
    youtube_config = config["youtube"]
    client_secrets_file = resolve_path(
        config_dir,
        os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", youtube_config["client_secrets_file"]),
    )
    token_file = resolve_path(config_dir, youtube_config["token_file"])

    if not client_secrets_file.exists():
        raise FileNotFoundError(
            f"YouTube OAuth client secret bulunamadi: {client_secrets_file}\n"
            "Google Cloud Console'dan OAuth Desktop client JSON dosyasini indirip "
            "bu konuma koyun ya da config'te youtube.client_secrets_file alanini guncelleyin."
        )

    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), YOUTUBE_SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_file), YOUTUBE_SCOPES)
            credentials = flow.run_local_server(port=0)
        token_file.write_text(credentials.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=credentials)


def find_active_broadcast_video_id(youtube: Any) -> tuple[str, str]:
    response = (
        youtube.liveBroadcasts()
        .list(
            part="id,snippet,status",
            broadcastStatus="active",
            broadcastType="all",
            maxResults=5,
        )
        .execute()
    )
    items = response.get("items", [])
    if not items:
        raise RuntimeError("YouTube hesabinda aktif canli yayin bulunamadi.")

    live_items = [
        item
        for item in items
        if item.get("status", {}).get("lifeCycleStatus") in {"live", "liveStarting"}
    ]
    selected = live_items[0] if live_items else items[0]
    title = selected.get("snippet", {}).get("title", "(baslik yok)")
    return selected["id"], title


def upload_thumbnail(youtube: Any, video_id: str, thumbnail_path: Path, image_format: str) -> None:
    media = MediaFileUpload(
        str(thumbnail_path),
        mimetype=MIME_TYPES[image_format],
        resumable=False,
    )
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()


def get_video_id(config: dict[str, Any], youtube: Any | None, override_video_id: str | None) -> tuple[str, str]:
    if override_video_id:
        return override_video_id, "CLI ile verilen video"

    youtube_config = config["youtube"]
    config_video_id = str(youtube_config.get("video_id") or "").strip()
    if config_video_id:
        return config_video_id, "config video_id"

    if not youtube_config.get("find_active_broadcast", True):
        raise RuntimeError(
            "youtube.video_id bos ve find_active_broadcast=false. Bir video_id belirtin."
        )
    if youtube is None:
        raise RuntimeError("Aktif yayin bulmak icin YouTube servisi hazir degil.")
    return find_active_broadcast_video_id(youtube)


def build_output_paths(config: dict[str, Any], config_dir: Path) -> tuple[Path, Path, Path, str]:
    thumbnail_config = config["thumbnail"]
    image_format = str(thumbnail_config["format"]).lower()
    if image_format == "jpeg":
        image_format = "jpg"
    output_dir = resolve_path(config_dir, thumbnail_config["output_dir"])
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw_path = output_dir / "_raw-last-capture"
    raw_path = raw_path.with_suffix(f".{image_format}")
    latest_path = output_dir / f"latest-thumbnail.{image_format}"

    if thumbnail_config.get("save_history", True):
        final_path = output_dir / f"thumbnail-{timestamp}.{image_format}"
    else:
        final_path = latest_path
    return raw_path, final_path, latest_path, image_format


def run_cycle(
    config: dict[str, Any],
    config_dir: Path,
    youtube: Any | None,
    dry_run: bool,
    override_video_id: str | None,
) -> CycleResult:
    raw_path, final_path, latest_path, image_format = build_output_paths(config, config_dir)

    capture = asyncio.run(capture_obs_frame(config, config_dir, raw_path))
    prepare_thumbnail(config, capture.raw_image_path, final_path)
    if final_path != latest_path:
        shutil.copyfile(final_path, latest_path)

    if dry_run:
        logging.info(
            "Dry-run: OBS kaynagi '%s' yakalandi, thumbnail hazirlandi: %s",
            capture.source_name,
            final_path,
        )
        return CycleResult(uploaded=False, skipped_reason="dry-run")

    if youtube is None:
        raise RuntimeError("YouTube servisi hazir degil.")

    video_id, title = get_video_id(config, youtube, override_video_id)
    upload_thumbnail(youtube, video_id, final_path, image_format)
    logging.info(
        "Thumbnail guncellendi. Video=%s (%s), OBS kaynagi=%s, dosya=%s",
        video_id,
        title,
        capture.source_name,
        final_path,
    )
    return CycleResult(uploaded=True)


def run_loop(
    config: dict[str, Any],
    config_dir: Path,
    youtube: Any | None,
    dry_run: bool,
    override_video_id: str | None,
) -> None:
    schedule = config["schedule"]
    interval_seconds = int(schedule["interval_seconds"])
    retry_seconds = int(schedule["retry_seconds"])

    if not schedule.get("run_immediately", True):
        logging.info("Ilk calisma %s saniye sonra.", interval_seconds)
        time.sleep(interval_seconds)

    while True:
        started_at = time.monotonic()
        wait_seconds = interval_seconds
        try:
            result = run_cycle(config, config_dir, youtube, dry_run, override_video_id)
            if result.skipped_reason == "dry-run":
                wait_seconds = interval_seconds
        except StreamNotActive as exc:
            logging.info("%s %s saniye sonra tekrar denenecek.", exc, retry_seconds)
            wait_seconds = retry_seconds
        except KeyboardInterrupt:
            logging.info("Durduruldu.")
            return
        except Exception:
            logging.exception("Dongu basarisiz oldu. %s saniye sonra tekrar denenecek.", retry_seconds)
            wait_seconds = retry_seconds

        elapsed = time.monotonic() - started_at
        sleep_for = max(0, wait_seconds - elapsed)
        logging.info("Sonraki kontrol %.0f saniye sonra.", sleep_for)
        try:
            time.sleep(sleep_for)
        except KeyboardInterrupt:
            logging.info("Durduruldu.")
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OBS'den goruntu alip YouTube canli yayin thumbnail'ini otomatik gunceller."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["init-config", "auth", "test-obs", "once", "run"],
        help="Calisma modu. Varsayilan: run",
    )
    parser.add_argument("--config", default="config.json", help="Config dosyasi yolu.")
    parser.add_argument("--overwrite", action="store_true", help="init-config icin var olan config'i ez.")
    parser.add_argument("--dry-run", action="store_true", help="YouTube'a yukleme yapmadan test et.")
    parser.add_argument("--video-id", default=None, help="Config yerine bu YouTube video ID'sini kullan.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    config_dir = config_path.parent
    instance_lock: SingleInstance | None = None

    if args.command == "run":
        instance_lock = SingleInstance(make_instance_name("OBSYouTubeThumbnailerRun", config_path))
        if not instance_lock.acquire():
            print("Thumbnailer zaten calisiyor; ikinci kopya acilmayacak.")
            return 0

    try:
        if args.command == "init-config":
            write_initial_config(config_path, args.overwrite)
            print(f"Config olusturuldu: {config_path}")
            return 0

        config = load_config(config_path)
        configure_logging(config, config_dir)

        if args.command == "test-obs":
            run_cycle(config, config_dir, youtube=None, dry_run=True, override_video_id=None)
            return 0

        youtube = None
        if args.command == "auth" or not args.dry_run:
            youtube = build_youtube_service(config, config_dir)

        if args.command == "auth":
            try:
                video_id, title = get_video_id(config, youtube, args.video_id)
                logging.info("YouTube baglantisi hazir. Hedef video: %s (%s)", video_id, title)
            except RuntimeError as exc:
                logging.info("YouTube baglantisi hazir. Not: %s", exc)
            return 0

        if args.command == "once":
            run_cycle(config, config_dir, youtube, args.dry_run, args.video_id)
            return 0

        run_loop(config, config_dir, youtube, args.dry_run, args.video_id)
        return 0
    finally:
        if instance_lock is not None:
            instance_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
