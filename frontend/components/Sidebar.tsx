'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Bot,
  PlayCircle,
  ShieldCheck,
  BarChart3,
  Cpu,
  Lock,
  Zap,
} from 'lucide-react';

const NAV_ITEMS = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    badge: 'Real-time',
    description: 'Executive revenue recovery metrics & charts',
  },
  {
    label: 'Transactions',
    href: '/transactions',
    icon: ArrowLeftRight,
    description: 'Failed payments & checkout monitoring',
  },
  {
    label: 'Run Recovery',
    href: '/run-recovery',
    icon: Zap,
    badge: 'Demo',
    description: 'Interactive demonstration with live stage animation',
  },
  {
    label: 'Agent Workflow',
    href: '/agent',
    icon: Bot,
    badge: 'LangGraph',
    description: 'Autonomous 8-stage decision pipeline',
  },
  {
    label: 'Simulation',
    href: '/simulation',
    icon: PlayCircle,
    description: 'Sandbox batch execution laboratory',
  },
  {
    label: 'Audit Trail',
    href: '/audit',
    icon: ShieldCheck,
    badge: 'SHA-256',
    description: 'Tamper-evident cryptographically chained log',
  },
  {
    label: 'Model Performance',
    href: '/model-performance',
    icon: BarChart3,
    description: 'ML model ROC-AUC & calibration metrics',
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 flex-shrink-0 border-r border-fintech-border bg-fintech-panel/70 flex flex-col justify-between p-4 min-h-[calc(100vh-4rem)]">
      {/* Navigation Menu */}
      <div className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Core Platform
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`group flex items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/20 text-white border border-indigo-500/40 shadow-sm'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent'
                }`}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <Icon
                    className={`h-4 w-4 flex-shrink-0 transition-colors ${
                      isActive ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-300'
                    }`}
                  />
                  <span className="truncate">{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={`ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded ${
                      isActive
                        ? 'bg-indigo-500/30 text-indigo-200 border border-indigo-400/40'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Safety & Governance Footnote */}
      <div className="space-y-3 pt-6 border-t border-slate-800/80">
        <div className="rounded-lg bg-slate-900/90 border border-slate-800 p-3 text-xs space-y-2">
          <div className="flex items-center justify-between text-slate-300">
            <span className="flex items-center gap-1.5 font-semibold text-[11px]">
              <Lock className="h-3.5 w-3.5 text-amber-400" /> Policy Guard
            </span>
            <span className="text-[10px] font-mono text-emerald-400 px-1.5 py-0.2 rounded bg-emerald-950/60 border border-emerald-500/30">
              ACTIVE
            </span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Deterministic rules strictly govern all LLM and simulator actions before execution.
          </p>
          <div className="flex items-center justify-between pt-1 text-[10px] text-slate-500 font-mono">
            <span>Model: v1.0.0-xgb</span>
            <span className="flex items-center gap-1 text-indigo-400">
              <Cpu className="h-3 w-3" /> ML Engine
            </span>
          </div>
        </div>

        <div className="text-center text-[10px] text-slate-400">
          RazorRecover AI &copy; 2026 Fintech Platform
        </div>
      </div>
    </aside>
  );
}
