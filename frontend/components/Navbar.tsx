'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { ShieldCheck, RotateCcw, Activity, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { resetDemo } from '../lib/api';

export default function Navbar() {
  const [backendHealth, setBackendHealth] = useState<'checking' | 'healthy' | 'offline'>('checking');
  const [isResetting, setIsResetting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          setBackendHealth('healthy');
        } else {
          setBackendHealth('offline');
        }
      } catch {
        setBackendHealth('offline');
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  }, []);

  const handleReset = async () => {
    if (isResetting) return;
    setIsResetting(true);
    try {
      await resetDemo(true);
      setToastMessage('Sandbox restored to realistic fintech dataset');
      setTimeout(() => setToastMessage(null), 4000);
      window.dispatchEvent(new Event('sandbox-reset'));
    } catch (err: any) {
      setToastMessage(`Reset failed: ${err.message}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-fintech-border bg-fintech-bg/90 backdrop-blur-md">
      <div className="flex h-16 items-center justify-between px-6">
        {/* Brand & Tagline */}
        <div className="flex items-center space-x-3">
          <Link href="/dashboard" className="flex items-center space-x-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-fintech-glow transition-transform group-hover:scale-105">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                RazorRecover <span className="text-indigo-400 font-mono text-sm px-1.5 py-0.5 rounded bg-indigo-950/70 border border-indigo-500/30">AI</span>
              </span>
              <p className="text-[11px] text-slate-400 font-medium hidden sm:block">
                Autonomous Revenue Recovery Engine
              </p>
            </div>
          </Link>
        </div>

        {/* Global Controls & Status Badges */}
        <div className="flex items-center space-x-3">
          {/* Toast Notification */}
          {toastMessage && (
            <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-md bg-indigo-950/80 border border-indigo-500/40 text-xs text-indigo-200 animate-fadeIn">
              <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400" />
              <span>{toastMessage}</span>
            </div>
          )}

          {/* Sandbox Badge */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 text-xs text-slate-300">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-mono text-[11px] text-slate-400">SANDBOX</span>
            <span className="text-slate-500">|</span>
            <span>No Real Money Movement</span>
          </div>

          {/* Backend Health Status */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs">
            <Activity className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-slate-400 hidden sm:inline">Engine:</span>
            {backendHealth === 'healthy' ? (
              <span className="text-emerald-400 font-medium flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span> Live
              </span>
            ) : backendHealth === 'checking' ? (
              <span className="text-amber-400 font-medium">Checking</span>
            ) : (
              <span className="text-rose-400 font-medium flex items-center gap-1">
                <AlertCircle className="h-3 w-3" /> Offline
              </span>
            )}
          </div>

          {/* Reset Demo Data Button */}
          <button
            onClick={handleReset}
            disabled={isResetting}
            title="Reset sandbox to authentic initial transactions dataset"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 transition active:scale-95 disabled:opacity-50"
          >
            <RotateCcw className={`h-3.5 w-3.5 ${isResetting ? 'animate-spin text-indigo-400' : 'text-slate-400'}`} />
            <span className="hidden sm:inline">{isResetting ? 'Resetting...' : 'Reset Sandbox'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
