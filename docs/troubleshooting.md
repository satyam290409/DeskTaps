# TapDeck Troubleshooting Guide

This guide covers common issues, root causes, and resolutions encountered when setting up and using TapDeck 2.0 on Windows.

---

## 1. Microphone & Audio Capture Issues

### Problem: "No suitable multi-channel microphone array detected"
- **Cause**: Windows is using a generic mono driver or the built-in microphone array is disabled in Windows Settings.
- **Resolution**:
  1. Open **Windows Settings > System > Sound**.
  2. Under **Input**, verify your laptop microphone (e.g. *Intel Smart Sound Technology Microphone Array*) is selected.
  3. Click the microphone device properties and ensure **Format** is set to **2 channels, 24-bit or 16-bit, 48000 Hz (Studio Quality)**.
  4. Run `python -m tapdeck --diagnostics` to inspect available PortAudio/WASAPI devices.

### Problem: "Audio stream underflow / buffer overflow warnings"
- **Cause**: CPU load spike or block size too small for current thread scheduling.
- **Resolution**:
  1. In `tapdeck_bindings.json`, increase audio `block_size` from `512` to `1024`.
  2. Ensure your laptop is not in extreme battery-saver mode which throttles CPU cores.

---

## 2. Detection & Recognition Issues

### Problem: Taps are not detected at all
- **Cause**: Input volume too low or energy threshold set higher than tap intensity.
- **Resolution**:
  1. Check your Windows microphone input volume slider; set it between 70% and 85%.
  2. Verify TapDeck is not paused (look for the orange pause badge on the tray icon).
  3. In TapDeck Settings, decrease the **Onset Energy Threshold** by 20–30%.
  4. Ensure your laptop's rubber feet are firmly touching the desk surface.

### Problem: Taps are misclassified (e.g. Right tap recognized as Left)
- **Cause**: Default spatial boundaries do not align with physical microphone placement.
- **Resolution**:
  1. Run the **Calibration Wizard** (`python -m tapdeck --calibrate`).
  2. Follow the 5-tap prompts per zone carefully to recalculate the GCC-PHAT delay offset.
  3. Verify whether your laptop has inverted stereo mic channels. If so, enable `invert_channels: true` in your configuration.

### Problem: Desk taps and Chassis taps are confused
- **Cause**: Desk surface has similar resonance to the laptop chassis, making HFR separation difficult.
- **Resolution**:
  1. Recalibrate specifically focusing on step 2 (LT) and step 3 (LB).
  2. When tapping the desk, tap 10–15 cm away from the laptop.
  3. When tapping the chassis, tap near the palm rest corner.
  4. If discrimination remains unstable, switch TapDeck to **2-Zone Mode** (`mode: "two_zone_lr"` in settings).

---

## 3. Automation & Action Execution Issues

### Problem: Hotkeys work in notepad but not in games or elevated apps
- **Cause**: User Interface Privilege Isolation (UIPI) prevents standard user processes from injecting keystrokes into elevated (Administrator) windows.
- **Resolution**:
  1. If you require hotkeys to work inside elevated tools (Task Manager, elevated cmd/PowerShell), launch TapDeck as Administrator.
  2. For everyday applications, standard user privileges are recommended.

### Problem: App launch action does not open the program
- **Cause**: Executable path contains spaces or executable is not in the system `PATH`.
- **Resolution**:
  1. Check the `executable` parameter in `tapdeck_bindings.json`.
  2. Use the full absolute path (e.g. `C:\\Program Files\\Notepad++\\notepad++.exe`) or ensure the executable is in your Windows `PATH` environment variable.
  3. Verify the file exists and is executable.

---

## 4. System Tray & Background Operation

### Problem: TapDeck icon does not appear in the system tray
- **Cause**: Windows hides new notification area icons inside the overflow chevron `^`.
- **Resolution**:
  1. Click the `^` arrow in your Windows taskbar tray area to reveal hidden icons.
  2. Drag the TapDeck icon out onto the taskbar for permanent visibility.
  3. In Windows Settings > Personalization > Taskbar > Other system tray icons, enable TapDeck.
