"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ReleaseMetadata {
  version: string;
  channel: string;
  releaseDate: string;
  minimumWindowsVersion: string;
  asset: {
    filename: string;
    url: string;
    sha256: string;
    sizeBytes?: number;
  };
  changelog: string[];
}

export default function DownloadPage() {
  const [release, setRelease] = useState<ReleaseMetadata | null>(null);
  const [isWindows, setIsWindows] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Detect OS for user convenience
    if (typeof window !== "undefined") {
      const ua = window.navigator.userAgent.toLowerCase();
      setIsWindows(ua.includes("win"));
    }

    // Load verified release metadata
    fetch("/releases/latest.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ReleaseMetadata) => setRelease(data))
      .catch((err) => {
        setError(`Unable to load latest release metadata (${err.message})`);
      });
  }, []);

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="py-12 px-6 max-w-4xl mx-auto space-y-12">
      <div className="text-center space-y-4">
        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Download TapDeck for Windows
        </h1>
        <p className="text-slate-400 max-w-xl mx-auto text-sm sm:text-base">
          Install the native x64 desktop application to enable acoustic physical tap detection and desktop automation.
        </p>
      </div>

      {!isWindows && (
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-800/50 text-amber-300 text-xs text-center">
          Note: Non-Windows operating system detected. TapDeck 2.0 requires 64-bit Windows 10 or Windows 11.
        </div>
      )}

      {error ? (
        <div className="p-6 rounded-2xl bg-red-950/40 border border-red-800/50 text-red-200 text-center space-y-3">
          <p className="font-semibold text-sm">{error}</p>
          <p className="text-xs text-slate-400">
            You can still inspect source code and build directly from GitHub.
          </p>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block px-4 py-2 text-xs bg-slate-800 rounded hover:bg-slate-700 text-white"
          >
            Visit GitHub Repository
          </a>
        </div>
      ) : release ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-8 shadow-xl">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-800">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white">TapDeck v{release.version}</h2>
                <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase bg-emerald-950 text-emerald-400 border border-emerald-800">
                  {release.channel}
                </span>
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Released {release.releaseDate} • Requires {release.minimumWindowsVersion}
              </div>
            </div>

            <a
              href={release.asset.url}
              className="px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition-all shadow-lg shadow-emerald-900/40 flex items-center gap-2 whitespace-nowrap"
            >
              Download {release.asset.filename}
            </a>
          </div>

          {/* SHA-256 Checksum Verification */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Cryptographic Integrity Verification (SHA-256)
            </h3>
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row gap-3 justify-between items-start sm:items-center">
              <code className="text-xs text-emerald-400 font-mono break-all">
                {release.asset.sha256}
              </code>
              <button
                onClick={() => copyHash(release.asset.sha256)}
                className="text-xs px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors whitespace-nowrap"
              >
                {copied ? "Copied!" : "Copy Hash"}
              </button>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <p>Verify your downloaded installer via PowerShell:</p>
              <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] text-slate-300 font-mono overflow-x-auto">
                Get-FileHash .\TapDeck-Setup.exe -Algorithm SHA256
              </pre>
            </div>
          </div>

          {/* What's New */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Release Notes</h3>
            <ul className="text-xs text-slate-400 space-y-2 list-disc list-inside">
              {release.changelog.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-slate-500 text-sm">Loading release metadata...</div>
      )}

      {/* Security & SmartScreen Notice */}
      <section className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 space-y-3 text-xs text-slate-400 leading-relaxed">
        <h4 className="font-semibold text-slate-200 text-sm">Windows SmartScreen Guidance</h4>
        <p>
          TapDeck binaries distributed via GitHub Releases are open-source and transparently built. Because community releases are signed with standard open-source certificates rather than enterprise EV credentials, Windows Defender SmartScreen may display an <em>&quot;Unrecognized app&quot;</em> prompt.
        </p>
        <p>
          To proceed: Click <strong className="text-slate-300">&quot;More info&quot;</strong>, verify the SHA-256 checksum matches above, and click <strong className="text-slate-300">&quot;Run anyway&quot;</strong>. TapDeck requires no administrator privileges and does not alter system registries.
        </p>
      </section>
    </div>
  );
}
