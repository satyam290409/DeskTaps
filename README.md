# TapDeck 2.0 — Acoustic Tap Detection for Windows

**TapDeck** converts physical taps near your laptop into configurable desktop actions using acoustic signal processing. It uses your laptop's built-in microphone array to detect taps, estimate their spatial zone (left-top, left-bottom, right-top, right-bottom), and execute assigned actions like launching apps, media controls, or keyboard shortcuts.

> **Status: In Development** — Acoustic feasibility is being validated before full UI polish.

## Features

- **Four-zone acoustic localization** — Detects tap position using inter-channel time delay (GCC-PHAT) and frequency analysis
- **Eight trigger tokens** — 4 single-tap zones + 4 dual-tap combinations
- **Configurable actions** — App launch, hotkeys, media controls, shell commands
- **Calibration wizard** — Adapts to your specific microphone and desk surface
- **Real-time diagnostics** — Waveform display, feature visualization, confidence metrics
- **System tray integration** — Runs quietly in the background
- **Privacy-first** — All audio processing is local, no data uploaded

## Requirements

- Windows 10/11 x64
- Python 3.11 or newer
- Stereo or multi-channel microphone input (built-in laptop mic array recommended)
- ~50 MB disk space (source + dependencies ~1.5 GB with venv)

## Quick Start

```powershell
# Clone and enter the project
cd Desktaps

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e ".[dev]"

# Run diagnostics mode (Phase 1 prototype)
python -m tapdeck --diagnostics

# Run the full application
python -m tapdeck

# Run tests
pytest
pytest -m "not hardware"  # skip hardware-dependent tests
```

## Project Structure

```
tapdeck/
├── pyproject.toml          # Project metadata and dependencies
├── src/tapdeck/
│   ├── main.py             # Entry point and CLI
│   ├── app.py              # Application controller
│   ├── audio/              # Audio capture, DSP, classification
│   │   ├── device_manager.py
│   │   ├── capture.py
│   │   ├── preprocessing.py
│   │   ├── transient_detector.py
│   │   ├── gcc_phat.py
│   │   ├── feature_extractor.py
│   │   ├── zone_classifier.py
│   │   ├── audio_recorder.py
│   │   └── diagnostics.py
│   ├── calibration/        # Calibration wizard and profiles
│   ├── combos/             # Dual-tap combination engine
│   ├── actions/            # Action dispatch (hotkeys, apps, media)
│   ├── config/             # Configuration management
│   ├── platform/           # Windows-specific integration
│   ├── ui/                 # PySide6 desktop interface
│   └── tray/               # System tray controls
├── tests/                  # Unit, integration, hardware tests
├── docs/                   # Architecture, feasibility, calibration docs
├── scripts/                # Dev, build, and packaging scripts
├── config/                 # Example configuration files
└── web/                    # Next.js marketing website
```

## Architecture

```
Microphone → AudioCapture → Preprocessing → TransientDetector
    → GCC-PHAT + FeatureExtractor → ZoneClassifier
    → ComboEngine → ActionDispatcher → Windows API
```

All audio processing runs in a background thread. The UI observes state through Qt signals. Actions are never executed from the audio callback.

## Testing

```powershell
pytest                           # All non-hardware tests
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests
pytest -m hardware               # Hardware tests (needs real mic)
pytest --cov=tapdeck             # With coverage
```

## Documentation

- [Architecture](docs/architecture.md)
- [Feasibility Plan](docs/feasibility-plan.md)
- [Acoustic Validation](docs/acoustic-validation.md)
- [Calibration Guide](docs/calibration.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Security](docs/security.md)
- [Release Process](docs/release.md)

## License

MIT — see [LICENSE](LICENSE)
