import Link from "next/link";

export default function DocsPage() {
  return (
    <div className="py-12 px-6 max-w-4xl mx-auto space-y-12">
      <div className="space-y-3 pb-6 border-b border-slate-800">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          TapDeck 2.0 Documentation
        </h1>
        <p className="text-slate-400 text-sm">
          Complete guide to installation, acoustic calibration, trigger mappings, and privacy specifications.
        </p>
      </div>

      {/* 1. Requirements */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-emerald-400">1. System Requirements</h2>
        <ul className="text-sm text-slate-300 space-y-2 list-disc list-inside">
          <li><strong>OS:</strong> Microsoft Windows 10 (Build 19041+) or Windows 11 (64-bit).</li>
          <li><strong>Microphone:</strong> Built-in stereo microphone or quad-channel microphone array (Intel Smart Sound, Realtek, Cirrus).</li>
          <li><strong>Sample Rates:</strong> 44,100 Hz or 48,000 Hz, Float32.</li>
          <li><strong>Privileges:</strong> Standard non-elevated user account (no Administrator rights required).</li>
        </ul>
      </section>

      {/* 2. Microphone Permissions */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-emerald-400">2. Windows Microphone Permissions</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          TapDeck processes audio exclusively in local memory without saving continuous audio streams to disk or transmitting data over networks.
        </p>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400 space-y-2">
          <p className="font-semibold text-slate-200">How to verify Windows microphone access:</p>
          <ol className="list-decimal list-inside space-y-1">
            <li>Open Windows <strong>Settings</strong> &gt; <strong>Privacy &amp; Security</strong> &gt; <strong>Microphone</strong>.</li>
            <li>Ensure <strong>&quot;Microphone access&quot;</strong> and <strong>&quot;Let desktop apps access your microphone&quot;</strong> are enabled.</li>
            <li>If detection fails to start, launch with diagnostics: <code className="text-emerald-400 font-mono">python -m tapdeck --diagnostics</code>.</li>
          </ol>
        </div>
      </section>

      {/* 3. Calibration */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-emerald-400">3. Calibration Wizard</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Because desks vary across wood, laminate, and metal, TapDeck uses an empirical 6-step calibration state machine:
        </p>
        <div className="grid sm:grid-cols-2 gap-3 text-xs">
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-800 space-y-1">
            <span className="font-semibold text-white">1. Select Audio Device</span>
            <p className="text-slate-400">Verifies stereo/multi-channel format and baseline noise floor.</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-800 space-y-1">
            <span className="font-semibold text-white">2. Sequential Quadrant Taps</span>
            <p className="text-slate-400">Prompts 5 gentle taps for Left-Top, Left-Bottom, Right-Top, and Right-Bottom.</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-800 space-y-1">
            <span className="font-semibold text-white">3. Cluster Separability</span>
            <p className="text-slate-400">Computes median and MAD for delay and HFR distributions to guarantee no overlap.</p>
          </div>
          <div className="bg-slate-900 p-4 rounded-lg border border-slate-800 space-y-1">
            <span className="font-semibold text-white">4. Atomic Profile Storage</span>
            <p className="text-slate-400">Saves profile to <code className="text-emerald-400">%LOCALAPPDATA%\TapDeck\calibration\</code>.</p>
          </div>
        </div>
      </section>

      {/* 4. Trigger Map */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-emerald-400">4. Default Trigger Mappings</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-800">
            <thead className="bg-slate-900 text-slate-300 border-b border-slate-800">
              <tr>
                <th className="p-3">Trigger Token</th>
                <th className="p-3">Physical Location</th>
                <th className="p-3">Category</th>
                <th className="p-3">Default Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-400">
              <tr><td className="p-3 font-mono text-emerald-400">SINGLE_LT</td><td className="p-3">Desk Left-Top</td><td className="p-3">App Launch</td><td className="p-3">VS Code (<code className="text-slate-300">code</code>)</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">SINGLE_LB</td><td className="p-3">Palmrest Left-Bottom</td><td className="p-3">Media Control</td><td className="p-3">Play / Pause Media</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">SINGLE_RT</td><td className="p-3">Desk Right-Top</td><td className="p-3">App Launch</td><td className="p-3">Terminal (<code className="text-slate-300">wt.exe</code>)</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">SINGLE_RB</td><td className="p-3">Palmrest Right-Bottom</td><td className="p-3">System Toggle</td><td className="p-3">Mute Microphone (<code className="text-slate-300">Win+Alt+K</code>)</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">DUAL_LT_RT</td><td className="p-3">Chord LT + RT</td><td className="p-3">Window Action</td><td className="p-3">Desktop Right (<code className="text-slate-300">Ctrl+Win+Right</code>)</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">DUAL_LB_RB</td><td className="p-3">Chord LB + RB</td><td className="p-3">Window Action</td><td className="p-3">Desktop Left (<code className="text-slate-300">Ctrl+Win+Left</code>)</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">DUAL_LT_RB</td><td className="p-3">Chord LT + RB</td><td className="p-3">Focus / Utility</td><td className="p-3">Task View (<code className="text-slate-300">Win+Tab</code>)</td></tr>
              <tr><td className="p-3 font-mono text-emerald-400">DUAL_LB_RT</td><td className="p-3">Chord LB + RT</td><td className="p-3">System Action</td><td className="p-3">Minimize All / Boss Key (<code className="text-slate-300">Win+D</code>)</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* 5. Custom Actions */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-emerald-400">5. Custom Action Configuration</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Actions are defined in <code className="text-emerald-400 font-mono">%LOCALAPPDATA%\TapDeck\bindings.json</code>. You can customize keys, application paths, or shell commands:
        </p>
        <pre className="bg-slate-900 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 font-mono overflow-x-auto">
{`{
  "schema_version": 1,
  "bindings": {
    "SINGLE_LT": {
      "category": "app_launch",
      "action": "launch_app",
      "params": { "executable": "notepad.exe", "args": [] },
      "label": "Open Notepad"
    }
  }
}`}
        </pre>
      </section>

      {/* 6. Privacy & Security */}
      <section className="space-y-4 pb-12">
        <h2 className="text-xl font-bold text-emerald-400">6. Privacy &amp; Data Security</h2>
        <div className="space-y-2 text-sm text-slate-300">
          <p>TapDeck follows a strict privacy-by-design architecture:</p>
          <ul className="list-disc list-inside space-y-1 text-slate-400 text-xs">
            <li><strong>Zero Cloud Telemetry:</strong> No microphone recordings, analytics, or identifiers leave your device.</li>
            <li><strong>Transient Memory Only:</strong> Audio blocks are discarded immediately after FFT processing.</li>
            <li><strong>Non-Elevated:</strong> Runs with standard user privileges; cannot intercept UAC screens.</li>
            <li><strong>Total Cleanup:</strong> All runtime profiles and logs reside in <code className="text-slate-300">%LOCALAPPDATA%\TapDeck\</code>.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
