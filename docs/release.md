# TapDeck Release & Deployment Process

This document details the standardized release engineering workflow for TapDeck 2.0, covering versioning, automated testing, compilation, packaging, and distribution.

---

## 1. Versioning Specification

TapDeck adheres strictly to [Semantic Versioning 2.0.0](https://semver.org/):
$$\text{MAJOR}.\text{MINOR}.\text{PATCH}[-\text{PRERELEASE}]$$

- **MAJOR**: Breaking configuration changes, architectural changes, or dropped OS compatibility.
- **MINOR**: New detection algorithms, new action categories, or major UI additions.
- **PATCH**: Bug fixes, DSP stability patches, or documentation improvements.
- **PRERELEASE**: Pre-release tags such as `-alpha.1`, `-beta.2`, or `-rc.1`.

Version strings are managed via `setuptools-scm` and git tags, with `pyproject.toml` tracking version metadata.

---

## 2. Release Lifecycle Stages

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Code & Quality  │ ----> │ Automated Tests │ ----> │ PyInstaller Pkg │
│  (Ruff & Mypy)  │       │ (Pytest Suite)  │       │  (Single Exe)   │
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                             │
                                                             ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  GitHub Release │ <---- │ Checksums & Sig │ <---- │ Smoke Test VM   │
│ & Documentation │       │   (SHA256)      │       │ (Win 10/11 x64) │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

---

## 3. Step-by-Step Release Workflow

### Step 1: Pre-flight Quality Verification
Run the unified build verification script to execute linting, type checks, and full test suite:
```powershell
.\scripts\build.ps1
```
This runs:
1. `ruff check .` — Lint checks
2. `ruff format --check .` — Style verification
3. `mypy src` — Static type analysis
4. `pytest -m "not hardware"` — Unit and integration test pass

### Step 2: Tag the Release Commit
Ensure working directory is clean and create a signed git tag:
```powershell
git checkout master
git pull origin master
git tag -a v2.0.0 -m "TapDeck 2.0.0 GA Release"
git push origin v2.0.0
```

### Step 3: Compile Standalone Executable
Execute the packaging script to generate the self-contained Windows executable via PyInstaller:
```powershell
.\scripts\package.ps1
```
The compiled output is located at:
`dist\TapDeck\TapDeck.exe` (or `dist\TapDeck.exe`)

### Step 4: Validate Checksums & Packaging
Generate SHA-256 integrity checksums:
```powershell
Get-FileHash dist\TapDeck.exe -Algorithm SHA256 | Export-Csv -Path dist\checksums.csv
```

### Step 5: Smoke Test on Clean Machine
1. Copy the packaged executable to a clean Windows 10/11 VM or secondary laptop.
2. Verify:
   - System tray icon launches cleanly.
   - Microphone input is detected without crashes.
   - `tapdeck_bindings.json` is generated properly in `%APPDATA%\TapDeck\`.
   - Test mode actions log events correctly.

### Step 6: Publish Distribution
1. Create a new GitHub Release corresponding to the git tag `v2.0.0`.
2. Attach `TapDeck.exe`, `tapdeck_bindings.example.json`, and `checksums.csv`.
3. Include release notes detailing:
   - What's New
   - Acoustic DSP & Accuracy Improvements
   - Breaking Changes / Migration Guide
