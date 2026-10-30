# TapDeck 2.0 Acoustic Feasibility Validation Plan

| Field | Detail |
| :--- | :--- |
| **Document Title** | TapDeck 2.0 Acoustic Feasibility & Localization Plan |
| **Creation Date** | October 30, 2026 |
| **Status** | **IN PROGRESS** |
| **Target Platform** | Windows 11 x64 (Laptop Multi-channel Array) |
| **Lead Engineer** | Audio DSP & System Automation Subsystem |

---

## 1. Executive Summary & Objectives

The primary objective of this feasibility plan is to definitively prove or disprove whether passive acoustic tap detection using standard built-in laptop microphone arrays can reliably distinguish four discrete spatial desk/chassis interaction zones:
- **Left-Top (LT)**: Left desk surface adjacent to laptop bezel
- **Left-Bottom (LB)**: Left palm rest / front corner of chassis
- **Right-Top (RT)**: Right desk surface adjacent to laptop bezel
- **Right-Bottom (RB)**: Right palm rest / front corner of chassis

Secondary objectives include:
1. Validating end-to-end processing latency from physical impact to desktop action execution.
2. Establishing empirical acoustic boundary baselines (TDOA / GCC-PHAT delay and High-to-Low Frequency Ratio).
3. Quantifying false positive resistance under realistic ambient workloads (keyboard typing, mouse clicks, speech, fan noise).

---

## 2. Hardware & Acoustic Environment Specification

### 2.1 Hardware Configuration
- **Audio Device**: Intel Smart Sound Technology (Intel SST) Microphone Array
- **Physical Geometry**: 2-to-4 capsule linear or planar microphone array integrated above the display panel / top chassis bezel
- **Sampling Rate ($f_s$)**: 48,000 Hz (48 kHz), 16-bit or 32-bit float PCM
- **Input Channels**: 2 or 4 synchronized channels
- **Processing Window**: 512 samples (~10.67 ms per block)

### 2.2 Test Surfaces & Mechanical Couplings
- **Primary Desk Surface**: Solid wood desk (high dampening, resonant low-mid conduction)
- **Secondary Surface**: Laminated composite desk (crisp transient acoustic conduction)
- **Laptop Support**: Direct rubber foot contact with desk surface

---

## 3. Experimental Protocol

Data collection will be conducted across structured recording sessions:

### 3.1 Controlled Tap Protocol
- **Number of Trials**: Minimum 25 controlled trials per zone ($4 \times 25 = 100$ total baseline trials).
- **Physical Locations**:
  - `LT`: 5 cm to 15 cm left of laptop keyboard, upper quadrant.
  - `LB`: Left laptop corner palm rest edge.
  - `RT`: 5 cm to 15 cm right of laptop keyboard, upper quadrant.
  - `RB`: Right laptop corner palm rest edge.
- **Tapping Actuator**: Index fingertip pad, finger knuckle, and pencil eraser tap to capture varying impact dynamics.

### 3.2 Environmental Test Conditions
1. **Quiet Baseline**: Ambient room sound level $< 35\text{ dBA}$, no typing, no HVAC bursts.
2. **Typing & Office Noise**: Active mechanical/scissor switch keyboard typing (60–90 WPM) and mouse movement/clicking.
3. **Audio Playback**: Background conversational audio or music played at moderate listening levels (50–60 dBA).
4. **Varying Force Trials**: Light taps (soft finger touch) vs. firm tactile taps.

---

## 4. Acoustic Analysis Methodology

```
Physical Tap → Audio Array Capture → 300–3000 Hz Bandpass Filter
       ↓
Transient Energy & Onset Detection
       ↓
┌───────────────────────┴────────────────────────┐
│                                                │
GCC-PHAT Cross-Correlation           Spectral Feature Analysis
(TDOA Delay Δt: Left vs. Right)      (HFR & Spectral Centroid: Desk vs. Chassis)
│                                                │
└───────────────────────┬────────────────────────┘
                        ↓
             Zone Classifier (LT, LB, RT, RB)
```

### 4.1 Time Difference of Arrival (TDOA) via GCC-PHAT
Cross-spectral phase transform is computed between stereo capsule signals $x_1(t)$ and $x_2(t)$:
$$R_{12}^{\text{PHAT}}(\tau) = \mathcal{F}^{-1}\left( \frac{X_1(f) X_2^*(f)}{|X_1(f) X_2^*(f)|} \right)$$
- When tap is on the Left, $x_1(t)$ leads $x_2(t)$, producing a negative delay.
- When tap is on the Right, $x_2(t)$ leads $x_1(t)$, producing a positive delay.
- Sub-sample parabolic interpolation provides sub-millisecond precision.

### 4.2 High-to-Low Frequency Ratio (HFR)
Differentiates Desk taps (Top) from Chassis taps (Bottom):
- **Desk taps (Top)** transmit energy through desk wood/laminate into laptop rubber feet, filtering out high harmonics while preserving 200–800 Hz resonance.
- **Chassis taps (Bottom)** directly excite laptop aluminum/plastic frame, creating sharp high-frequency transient clicks ($> 1200\text{ Hz}$).
$$\text{HFR} = \frac{\int_{f_{\text{split}}}^{f_{\text{high}}} |S(f)|^2 df}{\int_{f_{\text{low}}}^{f_{\text{split}}} |S(f)|^2 df}$$

---

## 5. Acceptance Criteria

| Metric | Target Threshold | Critical Failure Boundary |
| :--- | :--- | :--- |
| **Macro-F1 Score** | $\ge 90\%$ across all 4 zones | $< 80\%$ |
| **Precision** | $\ge 95\%$ per active zone | $< 88\%$ |
| **False Positive Rate** | $< 1$ false trigger per hour | $> 3$ false triggers per hour |
| **End-to-End Latency** | $< 200\text{ ms}$ (tap impact to UI/action) | $> 350\text{ ms}$ |
| **Refractory Rejection** | $100\%$ suppression within 150 ms | Spurious double triggers |

---

## 6. Fallback Strategies

If 4-zone detection fails to achieve the $\ge 90\%$ macro-F1 criteria due to mic placement symmetry or chassis dampening limitations:

1. **Two-Zone Horizontal Fallback (Left / Right)**:
   - Eliminates HFR vertical discrimination.
   - Relies strictly on GCC-PHAT TDOA ($x$-axis), which has an empirical acoustic separation $> 8\sigma$.
   - Yields 2 single triggers (`LEFT`, `RIGHT`) and 1 dual combo (`DUAL_LEFT_RIGHT`).
2. **Frequency-Calibrated Per-User Model**:
   - Adaptive k-NN or logistic boundary calibrated via the user's desk surface during the Calibration Wizard.
3. **Multi-mic Beamforming Aggregation**:
   - For 4-channel arrays, beamforming steering vector projection to amplify directional contrast.

---

## 7. Data Format & Storage

All empirical validation recordings are structured as follows:
- **Audio Captures**: Stereo / Quad WAV, 48 kHz, 32-bit float PCM (`data/recordings/zone_{ZONE}_{TRIAL:03d}.wav`).
- **Ground Truth Labels**: CSV file (`data/labels.csv`) with columns:
  - `filename`: Relative path to WAV file.
  - `ground_truth_zone`: `LT`, `LB`, `RT`, `RB`.
  - `tap_force`: `light`, `medium`, `firm`.
  - `ambient_condition`: `quiet`, `typing`, `music`.
  - `estimated_delay_samples`: GCC-PHAT output.
  - `estimated_hfr`: Spectral ratio.
  - `classified_zone`: Output classification.
  - `confidence_score`: Peak-to-mean cross-correlation ratio.
