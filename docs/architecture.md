# TapDeck 2.0 System Architecture

## 1. System Overview

TapDeck 2.0 transforms passive physical desk and laptop chassis taps into programmable desktop shortcuts and system actions on Windows. By capturing acoustic transients via the laptop's integrated multi-microphone array and performing real-time digital signal processing (DSP), the application classifies tap positions into spatial quadrants and dispatches user actions without requiring dedicated physical peripherals.

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Physical Tap   │ ----> │ Microphones (2) │ ----> │  AudioCapture   │
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                             │ Audio Buffer
                                                             ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ ZoneClassifier  │ <---- │  GCC-PHAT & HFR │ <---- │TransientDetector│
└────────┬────────┘       └─────────────────┘       └─────────────────┘
         │ Zone Token (LT/LB/RT/RB)
         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   ComboEngine   │ ----> │ActionDispatcher │ ----> │   Windows API   │
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │ Qt Signal
                                   ▼
                          ┌─────────────────┐
                          │ PySide6 UI/Tray │
                          └─────────────────┘
```

---

## 2. Component Breakdown

### 2.1 Audio Pipeline Subsystem (`tapdeck.audio`)
- **`device_manager.py`**: Queries WASAPI / DirectSound audio devices via `sounddevice` to locate multichannel microphone arrays (e.g. Intel SST).
- **`capture.py`**: Runs the low-latency PortAudio input stream callback at 48 kHz with block size 512 samples. Pushes raw audio frames into a lock-free thread-safe queue.
- **`preprocessing.py`**: Implements `BandpassFilter` using a 4th-order Butterworth Second-Order Sections (SOS) filter (300 Hz – 3000 Hz) to eliminate DC hum, rumble, and high-frequency hiss while maintaining filter state across audio blocks.
- **`transient_detector.py`**: Detects sharp acoustic onsets via energy rise and peak amplitude thresholds. Applies a 150 ms refractory lockout to prevent duplicate triggers from physical bounce.
- **`gcc_phat.py`**: Computes Generalized Cross-Correlation with Phase Transform between microphone channels to calculate fractional sample delays (TDOA) with sub-sample parabolic interpolation.
- **`feature_extractor.py`**: Computes High-to-Low Frequency Ratio (HFR), crest factor (Peak-to-RMS), spectral centroid, and signal clipping diagnostics.
- **`zone_classifier.py`**: Combines horizontal delay with vertical HFR spectral profiles to determine spatial zones (`LT`, `LB`, `RT`, `RB`) or `UNKNOWN` if confidence is insufficient.

### 2.2 Combination Engine (`tapdeck.combos`)
- **`combo_engine.py`**: Maintains a temporal window (default 120 ms). Translates isolated taps into single tokens (`SINGLE_LT`, `SINGLE_LB`, `SINGLE_RT`, `SINGLE_RB`) and resolves rapid dual taps into synchronized chord triggers (`DUAL_LT_RT`, `DUAL_LB_RB`, `DUAL_LT_RB`, `DUAL_LB_RT`).

### 2.3 Action Dispatcher (`tapdeck.actions`)
- **`action_dispatcher.py`**: Maps trigger tokens to configured action handlers.
- **Action Handlers**:
  - `HotkeyAction`: Dispatches global keystrokes using Win32 `SendInput` (e.g. `Win+Tab`, `Ctrl+Win+Right`).
  - `LaunchAppAction`: Spawns desktop executables with arguments via `subprocess.Popen`.
  - `MediaAction`: Controls media playback via virtual key codes (`VK_MEDIA_PLAY_PAUSE`, `VK_VOLUME_MUTE`).
  - `TestModeAction`: Intercepts actions during diagnostics or calibration to safely log execution without side-effects.

### 2.4 Configuration Subsystem (`tapdeck.config`)
- **`config_manager.py`**: Loads, validates, and serializes user settings from `%APPDATA%\TapDeck\tapdeck_bindings.json`. Handles schema versioning, defaults fallback, and automatic `.bak` backup creation on save.

### 2.5 User Interface & System Tray (`tapdeck.ui`, `tapdeck.tray`)
- **PySide6 Application**: Modern desktop GUI displaying real-time audio waveforms, detection confidence meters, interactive calibration wizard, and trigger-to-action configuration tables.
- **System Tray**: Provides background operation, status indicators, and pause/resume toggling.

---

## 3. Threading & Concurrency Model

TapDeck enforces a strict 3-tier threading architecture to guarantee zero audio dropouts and jitter-free UI responsiveness:

```
[ Tier 1: Real-Time Audio Callback ]
  │ High-priority PortAudio / WASAPI callback thread.
  │ Non-blocking enqueue to multiprocessing/queue.Queue.
  ▼
[ Tier 2: DSP Processing Worker ]
  │ Dedicated background QThread / Worker thread.
  │ Dequeues blocks -> Filters -> Detects transients -> GCC-PHAT -> Classifies.
  │ Pushes detected tokens to ComboEngine.
  │ Dispatches Action asynchronously.
  │ Emits Qt Signals (tapDetected, waveformUpdated) to Main Thread.
  ▼
[ Tier 3: Qt Main UI Thread ]
  │ PySide6 Event Loop (GUI rendering, Tray Icon, Settings Dialogs).
  │ Consumes Qt Signals, updates graphs, renders feedback animations.
```

> **Crucial Invariant**: The PortAudio callback never performs dynamic memory allocation, file I/O, or action dispatching. Desktop actions are executed in the background worker thread or dedicated worker pools.

---

## 4. Configuration Schema

Configurations are stored in JSON format with strict schema validation:
```json
{
  "schema_version": 1,
  "bindings": {
    "SINGLE_LT": {
      "category": "app_launch",
      "action": "launch_app",
      "params": { "executable": "code", "args": [] },
      "label": "Open VS Code"
    },
    "DUAL_LT_RT": {
      "category": "window_action",
      "action": "hotkey",
      "params": { "keys": ["ctrl", "win", "right"] },
      "label": "Desktop Right"
    }
  }
}
```

---

## 5. Error Handling & Resilience Strategy

1. **Audio Device Disconnection**:
   - If the active microphone array is unplugged or sleep-cycled, `AudioCapture` catches stream errors, transitions to a reconnect polling state, and notifies the UI.
2. **Corrupted Configuration**:
   - If `tapdeck_bindings.json` fails JSON validation or schema checks, `ConfigManager` restores from the `.bak` file or initializes safe defaults while alerting the user.
3. **Action Execution Faults**:
   - Non-existent executables or invalid key sequences in `ActionDispatcher` log structured errors and return failed `ActionResult` objects without terminating background audio monitoring.
4. **Saturation & Clipping**:
   - Microphone clipping (> 0.99 amplitude) generates diagnostic warnings to advise adjusting Windows input gain.
