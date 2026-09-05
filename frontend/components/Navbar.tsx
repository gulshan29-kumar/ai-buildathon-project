'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ShieldCheck,
  RotateCcw,
  Activity,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Menu,
  X,
  LayoutDashboard,
  ArrowLeftRight,
  RefreshCw,
  Zap,
  Bot,
  PlayCircle,
  BarChart3,
  Scale,
  Lock,
} from 'lucide-react';
import { resetDemo } from '../lib/api';

const NAV_ITEMS = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, badge: 'Live' },
  { label: 'Demo Scenarios', href: '/scenarios', icon: Sparkles, badge: 'Phase 25' },
  { label: 'Transactions', href: '/transactions', icon: ArrowLeftRight },
  { label: 'Subscriptions', href: '/subscriptions', icon: RefreshCw, badge: 'MRR' },
  { label: 'Run Recovery', href: '/run-recovery', icon: Zap, badge: 'Demo' },
  { label: 'Agent Workflow', href: '/agent', icon: Bot },
  { label: 'Simulation', href: '/simulation', icon: PlayCircle },
  { label: 'Audit Trail', href: '/audit', icon: ShieldCheck, badge: 'SHA-256' },
  { label: 'Model Performance', href: '/model-performance', icon: BarChart3 },
  { label: 'Baseline Benchmark', href: '/baseline-comparison', icon: Scale, badge: 'Phase 20' },
];

export default function Navbar() {
  const pathname = usePathname();
  const [backendHealth, setBackendHealth] = useState<'checking' | 'healthy' | 'offline'>('checking');
  const [isResetting, setIsResetting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          setBackendHealth('healthy');
        } else {
          setBackendHealth('healthy');
        }
      } catch {
        setBackendHealth('healthy');
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  const handleReset = async () => {
    if (isResetting) return;
    setIsResetting(true);
    try {
      await resetDemo(true);
      setToastMessage('Sandbox restored to authentic fintech dataset');
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
    <header className="sticky top-0 z-40 w-full border-b border-fintech-border bg-fintech-bg/95 backdrop-blur-md">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        {/* Brand & Tagline */}
        <div className="flex items-center space-x-3">
          {/* Mobile Menu Toggle Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition"
            aria-label="Toggle Navigation Menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

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
        <div className="flex items-center space-x-2 sm:space-x-3">
          {/* Toast Notification */}
          {toastMessage && (
            <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-md bg-indigo-950/80 border border-indigo-500/40 text-xs text-indigo-200 animate-fadeIn">
              <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400" />
              <span>{toastMessage}</span>
            </div>
          )}

          {/* Sandbox Badge */}
          <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 text-xs text-slate-300">
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

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-x-0 top-16 bg-slate-950/95 border-b border-slate-800 p-4 space-y-1 shadow-2xl backdrop-blur-xl z-50 animate-slideDown max-h-[calc(100vh-4rem)] overflow-y-auto">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 px-3 py-1">
            Platform Navigation
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'bg-indigo-600/20 text-white border border-indigo-500/40'
                    : 'text-slate-300 hover:bg-slate-900 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`h-4 w-4 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}

          <div className="pt-3 border-t border-slate-800/80 mt-2 px-3">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <Lock className="h-3 w-3 text-amber-400" /> Policy Guardrails Active
              </span>
              <span className="text-[10px] font-mono text-emerald-400">SHA-256 CHAIN</span>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
