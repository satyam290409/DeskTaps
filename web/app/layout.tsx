import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "TapDeck 2.0 — Acoustic Tap Detection for Windows",
  description: "Convert intentional physical taps on and around your laptop into 8 programmable desktop automation triggers using default stereo microphone input.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased font-sans flex flex-col min-h-screen">
        <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 font-bold text-lg tracking-tight text-emerald-400">
              <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span>
              TapDeck 2.0
            </Link>
            <nav className="flex items-center gap-6 text-sm font-medium text-slate-300">
              <Link href="/" className="hover:text-emerald-400 transition-colors">Overview</Link>
              <Link href="/docs" className="hover:text-emerald-400 transition-colors">Documentation</Link>
              <Link href="/download" className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-all shadow-lg shadow-emerald-900/40">
                Download v2.0
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-slate-800 py-8 bg-slate-950 text-slate-400 text-sm">
          <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row justify-between items-center gap-4">
            <div>© 2024–2026 TapDeck Contributors. MIT Licensed.</div>
            <div className="flex gap-6">
              <Link href="/docs" className="hover:text-slate-200">Docs</Link>
              <Link href="/download" className="hover:text-slate-200">Download</Link>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="hover:text-slate-200">GitHub</a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
