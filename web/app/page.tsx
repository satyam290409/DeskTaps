"use client";

import { useState } from "react";
import Link from "next/link";

interface TriggerCard {
  token: string;
  category: string;
  defaultAction: string;
  keys: string;
  zone: string;
}

const TRIGGERS: TriggerCard[] = [
  { token: "SINGLE_LT", category: "App Launch", defaultAction: "Open Workspace", keys: "code", zone: "Left-Top (LT)" },
  { token: "SINGLE_LB", category: "Media Control", defaultAction: "Play / Pause", keys: "VK_MEDIA_PLAY_PAUSE", zone: "Left-Bottom (LB)" },
  { token: "SINGLE_RT", category: "App Launch", defaultAction: "Open Terminal", keys: "wt.exe", zone: "Right-Top (RT)" },
  { token: "SINGLE_RB", category: "System Toggle", defaultAction: "Mute / Unmute Mic", keys: "Win+Alt+K", zone: "Right-Bottom (RB)" },
  { token: "DUAL_LT_RT", category: "Window Action", defaultAction: "Virtual Desktop Right", keys: "Ctrl+Win+Right", zone: "Chord LT + RT" },
  { token: "DUAL_LB_RB", category: "Window Action", defaultAction: "Virtual Desktop Left", keys: "Ctrl+Win+Left", zone: "Chord LB + RB" },
  { token: "DUAL_LT_RB", category: "Focus / Utility", defaultAction: "Task View", keys: "Win+Tab", zone: "Chord LT + RB" },
  { token: "DUAL_LB_RT", category: "System Action", defaultAction: "Minimize All", keys: "Win+D", zone: "Chord LB + RT" },
];

export default function HomePage() {
  const [activeZone, setActiveZone] = useState<string | null>(null);
  const [simulatedToken, setSimulatedToken] = useState<string>("Click any quadrant to simulate");

  const handleSimulate = (zoneKey: string, token: string) => {
    setActiveZone(zoneKey);
    setSimulatedToken(`Triggered: ${token} (Confidence: 0.94)`);
    setTimeout(() => {
      setActiveZone(null);
    }, 1200);
  };

  return (
    <div className="py-12 px-6 max-w-6xl mx-auto space-y-20">
      {/* Hero Section */}
      <section className="text-center space-y-6 pt-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
          Acoustic Spatial Signal Processing for Windows 10/11
        </div>
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-tight">
          Turn your desk into an <span className="text-emerald-400">invisible acoustic trackpad</span>.
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
          TapDeck uses your laptop's standard stereo microphone array to calculate inter-channel time delays and spectral ratios, recognizing 8 discrete tap gestures without special sensors.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
          <Link
            href="/download"
            className="px-6 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-lg shadow-emerald-900/50 transition-all flex items-center gap-2"
          >
            Download TapDeck for Windows
          </Link>
          <Link
            href="/docs"
            className="px-6 py-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold border border-slate-700 transition-all"
          >
            Read Architecture & Specs
          </Link>
        </div>
      </section>

      {/* Interactive 2D Acoustic Radar Simulation */}
      <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="text-xs uppercase font-bold tracking-wider text-amber-400">
            Interactive Illustrative Simulation
          </div>
          <h2 className="text-2xl font-bold text-white">4-Zone Acoustic Radar Visualizer</h2>
          <p className="text-sm text-slate-400 max-w-xl mx-auto">
            Click any spatial quadrant around the laptop below to simulate real-time GCC-PHAT delay and HFR transient classification.
          </p>
        </div>

        <div className="max-w-xl mx-auto bg-slate-950 border border-slate-800 rounded-xl p-6 relative">
          {/* Laptop Mockup in Center */}
          <div className="grid grid-cols-2 gap-4 h-64">
            <button
              onClick={() => handleSimulate("LT", "SINGLE_LT")}
              className={`rounded-lg border p-4 flex flex-col justify-between transition-all text-left ${
                activeZone === "LT"
                  ? "bg-emerald-600/30 border-emerald-400 text-emerald-200 ring-2 ring-emerald-500/50"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700 text-slate-400"
              }`}
            >
              <div className="text-xs font-bold uppercase">Left-Top (LT)</div>
              <div className="text-sm font-semibold text-white">Desk Left</div>
              <div className="text-[11px] text-slate-500">Delay &lt; 0 | Low HFR</div>
            </button>

            <button
              onClick={() => handleSimulate("RT", "SINGLE_RT")}
              className={`rounded-lg border p-4 flex flex-col justify-between transition-all text-left ${
                activeZone === "RT"
                  ? "bg-emerald-600/30 border-emerald-400 text-emerald-200 ring-2 ring-emerald-500/50"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700 text-slate-400"
              }`}
            >
              <div className="text-xs font-bold uppercase">Right-Top (RT)</div>
              <div className="text-sm font-semibold text-white">Desk Right</div>
              <div className="text-[11px] text-slate-500">Delay &gt; 0 | Low HFR</div>
            </button>

            <button
              onClick={() => handleSimulate("LB", "SINGLE_LB")}
              className={`rounded-lg border p-4 flex flex-col justify-between transition-all text-left ${
                activeZone === "LB"
                  ? "bg-emerald-600/30 border-emerald-400 text-emerald-200 ring-2 ring-emerald-500/50"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700 text-slate-400"
              }`}
            >
              <div className="text-xs font-bold uppercase">Left-Bottom (LB)</div>
              <div className="text-sm font-semibold text-white">Palmrest Left</div>
              <div className="text-[11px] text-slate-500">Delay &lt; 0 | High HFR</div>
            </button>

            <button
              onClick={() => handleSimulate("RB", "SINGLE_RB")}
              className={`rounded-lg border p-4 flex flex-col justify-between transition-all text-left ${
                activeZone === "RB"
                  ? "bg-emerald-600/30 border-emerald-400 text-emerald-200 ring-2 ring-emerald-500/50"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700 text-slate-400"
              }`}
            >
              <div className="text-xs font-bold uppercase">Right-Bottom (RB)</div>
              <div className="text-sm font-semibold text-white">Palmrest Right</div>
              <div className="text-[11px] text-slate-500">Delay &gt; 0 | High HFR</div>
            </button>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-xs text-slate-400">
            <div>Status: <span className="text-emerald-400 font-mono font-medium">{simulatedToken}</span></div>
            <div className="text-slate-500 italic">Simulated DSP Pipeline</div>
          </div>
        </div>
      </section>

      {/* 8 Trigger Tokens Grid */}
      <section className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-white">The Eight Logical Trigger Tokens</h2>
          <p className="text-sm text-slate-400 max-w-xl mx-auto">
            Configurable triggers matching single impacts and dual-tap chords within a 120ms coincidence window.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TRIGGERS.map((t) => (
            <div key={t.token} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3 hover:border-slate-700 transition-colors">
              <div className="flex justify-between items-start">
                <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                  {t.token}
                </span>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider">{t.category}</span>
              </div>
              <div>
                <div className="text-base font-semibold text-white">{t.defaultAction}</div>
                <div className="text-xs text-slate-400 font-mono mt-1">{t.keys}</div>
              </div>
              <div className="text-[11px] text-slate-500 pt-2 border-t border-slate-800/60">
                Position: <span className="text-slate-400">{t.zone}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Honest Compatibility & Feasibility Notes */}
      <section className="bg-slate-900/50 border border-amber-900/30 rounded-2xl p-8 space-y-4">
        <h3 className="text-lg font-bold text-amber-300 flex items-center gap-2">
          <span>⚠️</span> Technical Feasibility & Environmental Limitations
        </h3>
        <p className="text-sm text-slate-300 leading-relaxed">
          Spatial tap localization relies on physical acoustics: microphone geometry, inter-channel time difference of arrival (GCC-PHAT), and surface acoustic dispersion (HFR). Built-in laptop microphones closely spaced together (&lt;10cm) or mono microphones cannot resolve 4 distinct zones.
        </p>
        <div className="grid sm:grid-cols-2 gap-4 text-xs text-slate-400 pt-2">
          <div className="bg-slate-950/80 p-4 rounded-lg border border-slate-800 space-y-1">
            <span className="font-semibold text-slate-200">Supported Devices</span>
            <p>Windows 10/11 x64 laptops with built-in stereo or quad-channel microphone arrays (WASAPI/MME at 44.1kHz or 48kHz).</p>
          </div>
          <div className="bg-slate-950/80 p-4 rounded-lg border border-slate-800 space-y-1">
            <span className="font-semibold text-slate-200">Graceful 2-Zone Fallback</span>
            <p>If vertical desk attenuation cannot be calibrated reliably on glass or metal surfaces, TapDeck provides an automatic 2-Zone mode (Left vs Right).</p>
          </div>
        </div>
      </section>
    </div>
  );
}
