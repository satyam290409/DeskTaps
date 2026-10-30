"""TapDeck 2.0 — Main entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure structured logging with rotating file handler."""
    if log_dir is None:
        log_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "TapDeck" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))

    # File handler with rotation (5MB, keep 5 files)
    file_handler = RotatingFileHandler(
        log_dir / "tapdeck.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        handlers=[console_handler, file_handler],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="tapdeck",
        description="TapDeck 2.0 — Acoustic tap detection and desktop automation",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        default=True,
        help="Launch with diagnostics/telemetry GUI window (default: True)",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start minimized to system tray without displaying the main window",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Log actions without executing them",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: INFO)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Audio device index (default: system default)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List audio devices and exit",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for TapDeck."""
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger("tapdeck")

    logger.info("TapDeck 2.0 starting...")

    if args.list_devices:
        from tapdeck.audio.device_manager import DeviceManager

        dm = DeviceManager()
        devices = dm.enumerate_devices()
        for dev in devices:
            marker = " [DEFAULT]" if dev.is_default else ""
            print(
                f"  {dev.index}: {dev.name} ({dev.max_input_channels}ch, "
                f"{dev.default_samplerate}Hz){marker}"
            )
        return 0

    try:
        from tapdeck.app import TapDeckApp

        show_gui = not args.minimized
        logger.info("Launching TapDeck (show_gui=%s, test_mode=%s)...", show_gui, args.test_mode)
        app = TapDeckApp(
            diagnostics_mode=show_gui,
            test_mode=args.test_mode,
            device_index=args.device,
        )
        return app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        return 0
    except Exception:
        logger.exception("Fatal error in TapDeck")
        return 1


if __name__ == "__main__":
    sys.exit(main())
