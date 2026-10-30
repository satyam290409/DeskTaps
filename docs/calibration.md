# TapDeck Calibration Guide

## 1. Why Calibration is Needed

Laptop microphone arrays, chassis materials (aluminum alloy vs. polycarbonate), desk surfaces (solid wood, composite, glass), and user tapping styles vary significantly across setups.

Calibration personalizes two key acoustic parameters for your environment:
1. **Horizontal Separation Boundary**: TDOA delay threshold (GCC-PHAT) separating Left and Right taps.
2. **Vertical Surface Boundary**: High-to-Low Frequency Ratio (HFR) separating Desk surface taps (Top) from Laptop Chassis taps (Bottom).

---

## 2. Step-by-Step Wizard Walkthrough

To launch the Calibration Wizard:
1. Right-click the **TapDeck** system tray icon and select **Calibrate Zones**, or launch with `python -m tapdeck --calibrate`.
2. Ensure you are seated at your normal working desk in a typical ambient noise setting.

```
Step 1: Noise Floor Profiling (Keep Quiet for 3 seconds)
  ↓
Step 2: Calibrate Left-Top (LT) — Tap on the desk left of laptop (5 taps)
  ↓
Step 3: Calibrate Left-Bottom (LB) — Tap on the left palm rest corner (5 taps)
  ↓
Step 4: Calibrate Right-Top (RT) — Tap on the desk right of laptop (5 taps)
  ↓
Step 5: Calibrate Right-Bottom (RB) — Tap on the right palm rest corner (5 taps)
  ↓
Step 6: Review Separation Boundaries & Save Profile
```

### Detailed Steps:

### Step 1: Ambient Noise Floor Baseline
- Remain quiet for 3 seconds while TapDeck measures the background acoustic RMS energy and ambient frequency distribution.
- **Tip**: Keep keyboard typing and background speech paused during this step.

### Step 2: Zone LT (Left Desk Surface)
- Tap your fingertip firmly on the desk surface approximately 10–15 cm to the left of your laptop keyboard.
- Perform 5 distinct taps spaced roughly 1 second apart when prompted on screen.

### Step 3: Zone LB (Left Chassis Palm Rest)
- Tap on the left corner of your laptop chassis palm rest (adjacent to or just below the trackpad level).
- Perform 5 distinct taps when prompted.

### Step 4: Zone RT (Right Desk Surface)
- Tap on the desk surface approximately 10–15 cm to the right of your laptop keyboard.
- Perform 5 distinct taps when prompted.

### Step 5: Zone RB (Right Chassis Palm Rest)
- Tap on the right corner of your laptop chassis palm rest.
- Perform 5 distinct taps when prompted.

### Step 6: Review & Finalize
- TapDeck will plot your tap clusters on the 2D feature graph ($x$-axis: GCC-PHAT Delay, $y$-axis: HFR).
- Verify that the four clusters are distinct and separated by the decision boundaries.
- Click **Save Calibration Profile**.

---

## 3. Calibration Tips for Optimal Accuracy

- **Use Consistent Tapping Technique**: Tap with the fleshy pad of your index or middle finger rather than your fingernail. Fingernails create inconsistent high-frequency spikes.
- **Solid Desk Contact**: Ensure your laptop's rubber feet are resting flat on the desk surface. If using a laptop riser or stand, recalibration is required.
- **Desk Mat Considerations**: If using an extended mousepad or desk mat, tap directly on the mat if that is where you intend to trigger shortcuts. The mat will dampen high frequencies, which calibration will learn.
- **Windows Microphone Boost**: Set your Windows microphone input volume to 70–85%. Avoid 100% gain if it introduces static or saturation clipping.

---

## 4. Troubleshooting Calibration Issues

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| **"Audio Clipping Detected" Warning** | Input gain too high or tapping directly over mic capsule | Lower Windows mic volume in Sound Settings or tap slightly further away. |
| **"Low Confidence / Uncorrelated Peak"** | Stereo mic channel mapping reversed or mono input | Check Windows Sound properties to verify stereo or quad input is enabled. |
| **LT and LB Clusters Overlapping** | Chassis and desk producing identical acoustic spectra | Tap LB with a lighter touch or tap closer to the front chassis lip. |
| **RT Misclassified as Left** | Negative TDOA on right taps | Check if audio device is configured as mirrored stereo. Run `--diagnostics` to verify channel 0 is physical left mic. |
