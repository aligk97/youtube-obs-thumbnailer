from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from single_instance import SingleInstance, make_instance_name


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OBS_PROCESS_NAMES = ("obs64.exe", "obs32.exe", "obs.exe")


def configure_logging(base_dir: Path) -> None:
    handlers: list[logging.Handler] = [
        logging.FileHandler(base_dir / "watcher.log", encoding="utf-8")
    ]
    if sys.stdout is not None:
        handlers.insert(0, logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def resolve_config_path(config: str) -> Path:
    config_path = Path(config).expanduser()
    if not config_path.is_absolute():
        config_path = BASE_DIR / config_path
    return config_path


def find_python_executable() -> str:
    venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)

    current = Path(sys.executable)
    if current.name.lower() == "pythonw.exe":
        python_exe = current.with_name("python.exe")
        if python_exe.exists():
            return str(python_exe)

    return sys.executable


def process_exists(process_names: tuple[str, ...]) -> bool:
    lowered_names = {name.lower() for name in process_names}
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags(),
            check=False,
        )
    except OSError:
        logging.exception("Windows tasklist calistirilamadi.")
        return False

    output = result.stdout.lower()
    return any(f'"{name}"' in output or name in output for name in lowered_names)


def thumbnailer_is_running(config_path: Path) -> bool:
    lock = SingleInstance(make_instance_name("OBSYouTubeThumbnailerRun", config_path))
    if not lock.acquire():
        return True
    lock.release()
    return False


def start_thumbnailer(config_path: Path, dry_run: bool) -> subprocess.Popen[bytes] | None:
    if not config_path.exists():
        logging.warning("Config dosyasi yok; thumbnailer baslatilmadi: %s", config_path)
        return None

    if thumbnailer_is_running(config_path):
        logging.info("Thumbnailer zaten calisiyor; ikinci kopya acilmayacak.")
        return None

    python_exe = find_python_executable()
    command = [
        python_exe,
        str(BASE_DIR / "thumbnailer.py"),
        "run",
        "--config",
        str(config_path),
    ]
    if dry_run:
        command.append("--dry-run")

    logging.info("OBS bulundu; thumbnailer arka planda baslatiliyor.")
    return subprocess.Popen(
        command,
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )


def stop_thumbnailer(process: subprocess.Popen[bytes], grace_seconds: int) -> None:
    if process.poll() is not None:
        return

    logging.info("OBS kapandi; thumbnailer durduruluyor.")
    process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        logging.warning("Thumbnailer kapanmadi; zorla kapatiliyor.")
        process.kill()
        process.wait(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OBS acilinca thumbnailer'i gizli baslatir, OBS kapaninca durdurur."
    )
    parser.add_argument("--config", default="config.json", help="Thumbnailer config dosyasi.")
    parser.add_argument(
        "--check-interval",
        type=int,
        default=5,
        help="OBS surec kontrol araligi, saniye cinsinden.",
    )
    parser.add_argument(
        "--stop-grace",
        type=int,
        default=10,
        help="OBS kapaninca thumbnailer'a verilen kapanma suresi.",
    )
    parser.add_argument(
        "--start-retry",
        type=int,
        default=30,
        help="Thumbnailer baslatma denemeleri arasindaki minimum sure.",
    )
    parser.add_argument(
        "--obs-process",
        action="append",
        default=[],
        help="Ek OBS process adi. Ornek: --obs-process obs64.exe",
    )
    parser.add_argument("--dry-run", action="store_true", help="Thumbnailer'i dry-run ile baslat.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(BASE_DIR)

    config_path = resolve_config_path(args.config)
    process_names = tuple(args.obs_process) if args.obs_process else DEFAULT_OBS_PROCESS_NAMES

    watcher_lock = SingleInstance(make_instance_name("OBSYouTubeThumbnailerWatcher", BASE_DIR))
    if not watcher_lock.acquire():
        logging.info("Watcher zaten calisiyor; ikinci kopya acilmayacak.")
        return 0

    child: subprocess.Popen[bytes] | None = None
    last_start_attempt = 0.0

    try:
        logging.info("OBS watcher basladi. Config=%s", config_path)
        while True:
            obs_running = process_exists(process_names)
            child_running = child is not None and child.poll() is None

            if obs_running and not child_running:
                now = time.monotonic()
                if now - last_start_attempt >= max(args.start_retry, args.check_interval, 5):
                    child = start_thumbnailer(config_path, args.dry_run)
                    last_start_attempt = now

            if not obs_running and child_running and child is not None:
                stop_thumbnailer(child, args.stop_grace)
                child = None

            if child is not None and child.poll() is not None:
                logging.info("Thumbnailer sureci kapandi. Kod=%s", child.returncode)
                child = None

            time.sleep(max(args.check_interval, 1))
    except KeyboardInterrupt:
        logging.info("Watcher durduruldu.")
        if child is not None:
            stop_thumbnailer(child, args.stop_grace)
        return 0
    finally:
        watcher_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
