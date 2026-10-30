# TapDeck Security & Privacy Architecture

Security and privacy are core engineering requirements for TapDeck 2.0. Because the application processes live microphone streams and executes desktop shortcuts, strict controls are established to protect user privacy and system integrity.

---

## 1. Audio Privacy & Zero-Data Retention

- **Local-Only Processing**: All audio signal processing (bandpass filtering, transient detection, GCC-PHAT cross-correlation, and feature extraction) occurs entirely in volatile RAM on the local host machine.
- **Zero Network Transmission**: TapDeck does not send any audio buffers, acoustic spectra, telemetry, or diagnostic telemetry to remote servers or cloud services.
- **No Disk Buffering of Audio**: Live audio streams are processed in transient circular buffers (512 samples) and discarded immediately. No audio is ever written to disk unless the user explicitly initiates a recording session in Diagnostic / Calibration Mode.
- **Microphone In-Use Notification**: TapDeck registers as a standard WASAPI client, ensuring the Windows system tray microphone privacy indicator is visible whenever audio capture is active.

---

## 2. Principle of Least Privilege (No Administrator Privileges)

- TapDeck is intentionally engineered to run under a standard, non-elevated Windows user account (`RunAsInvoker`).
- Standard desktop automations (media controls, app launching, virtual desktop navigation, window management) operate using standard user Win32 APIs (`SendInput`, `ShellExecuteEx`).
- Running with standard privileges protects the user by ensuring that any automated action is constrained by Windows User Account Control (UAC) and User Interface Privilege Isolation (UIPI).

---

## 3. Shell Command & Action Dispatch Risks

TapDeck allows users to configure shell commands or custom scripts to trigger on taps:

### Security Risks
- **Command Injection**: Arbitrary argument passing to shells (`cmd.exe` or `powershell.exe`) could expose vulnerabilities if external untrusted configuration files are imported.
- **Accidental Execution**: Physical vibrations (dropping a book on the desk) could inadvertently trigger an action if confidence thresholds are improperly lowered.

### Mitigations
1. **Direct Process Execution**: `LaunchAppAction` invokes executables directly via `subprocess.Popen` with argument lists rather than passing raw concatenated command strings to `shell=True`.
2. **Schema & Path Validation**: The configuration manager validates executable paths and rejects non-existent or suspicious paths prior to binding registration.
3. **Refractory & Confidence Gates**: All actions are gated behind a 150 ms refractory period and minimum cross-correlation confidence threshold ($> 3.0$) to eliminate accidental triggers.

---

## 4. Telemetry and Analytics Policy

- **No Third-Party Trackers**: TapDeck contains no third-party tracking SDKs, analytics endpoints, or advertising libraries.
- **Deterministic Crash Reporting**: Crash diagnostics, if enabled, are written only to local logs in `%APPDATA%\TapDeck\logs\` for user inspection.
