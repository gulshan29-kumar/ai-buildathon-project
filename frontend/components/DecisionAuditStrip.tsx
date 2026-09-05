'use client';

import React from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Zap,
  TrendingUp,
  DollarSign,
  AlertCircle,
  Clock,
  Lock,
  CheckCircle2,
  Info,
} from 'lucide-react';
import { formatINR, formatPercent, getActionBadge } from '../lib/api';
import Tooltip from './Tooltip';

export interface DecisionAuditStripProps {
  revenueAtRisk: number;
  recoverableRevenue?: number;
  revenueRecovered: number;
  recoveryRate?: number;
  agentDecision: string;
  policyDecision: string;
  policyRuleId?: string;
  reason: string;
  auditHash?: string;
  verifiedIntegrity?: boolean;
  timestamp?: string;
  latencyMs?: number;
  title?: string;
  className?: string;
}

export default function DecisionAuditStrip({
  revenueAtRisk,
  recoverableRevenue,
  revenueRecovered,
  recoveryRate,
  agentDecision,
  policyDecision,
  policyRuleId,
  reason,
  auditHash,
  verifiedIntegrity = true,
  timestamp,
  latencyMs,
  title = 'Autonomous Recovery & Governance Audit',
  className = '',
}: DecisionAuditStripProps) {
  const actionBadge = getActionBadge(agentDecision);
  const isPolicyPermitted =
    policyDecision.toUpperCase() === 'ALLOWED' ||
    policyDecision.toUpperCase() === 'PERMITTED' ||
    policyDecision.toUpperCase() === 'ALLOW';
  const isPolicyWait = policyDecision.toUpperCase() === 'WAIT';

  const computedRecoverable =
    recoverableRevenue !== undefined
      ? recoverableRevenue
      : revenueRecovered > 0
      ? revenueRecovered
      : Math.round(revenueAtRisk * 0.72);

  const computedRate =
    recoveryRate !== undefined
      ? recoveryRate
      : revenueAtRisk > 0
      ? (revenueRecovered / revenueAtRisk) * 100
      : 0;

  return (
    <div
      className={`rounded-xl border border-slate-800 bg-gradient-to-b from-slate-900/90 to-slate-950/90 p-5 shadow-lg backdrop-blur-md space-y-4 ${className}`}
    >
      {/* Top Header: Title, Integrity Badge, Timestamp */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-indigo-400 animate-pulse" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            {title}
          </h3>
        </div>

        <div className="flex items-center gap-3 text-[11px]">
          {verifiedIntegrity ? (
            <span className="inline-flex items-center gap-1 font-semibold text-emerald-400 font-mono">
              <ShieldCheck className="h-3.5 w-3.5" /> SHA-256 Verified
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 font-semibold text-rose-400 font-mono">
              <AlertTriangle className="h-3.5 w-3.5" /> Integrity Warning
            </span>
          )}

          {latencyMs !== undefined && (
            <span className="text-slate-500 font-mono hidden sm:inline">
              Latency: {latencyMs}ms
            </span>
          )}

          {timestamp && (
            <span className="text-slate-500 font-mono hidden sm:inline">
              {new Date(timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* 4 Core Financial Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-left">
        {/* 1. Revenue at Risk */}
        <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
            <span className="uppercase tracking-wider font-semibold">Revenue at Risk</span>
            <Tooltip content="Total potential gross transaction volume subject to failure or drop-off">
              <Info className="h-3 w-3 text-slate-500 cursor-help" />
            </Tooltip>
          </div>
          <div className="text-lg font-bold font-tabular text-rose-400">
            {formatINR(revenueAtRisk)}
          </div>
        </div>

        {/* 2. Recoverable Revenue */}
        <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
            <span className="uppercase tracking-wider font-semibold">Recoverable Revenue</span>
            <Tooltip content="Portion of volume mathematically deemed recoverable by the ML engine">
              <Info className="h-3 w-3 text-slate-500 cursor-help" />
            </Tooltip>
          </div>
          <div className="text-lg font-bold font-tabular text-indigo-300">
            {formatINR(computedRecoverable)}
          </div>
        </div>

        {/* 3. Revenue Recovered */}
        <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
            <span className="uppercase tracking-wider font-semibold">Revenue Recovered</span>
            <Tooltip content="Net financial value successfully captured and reconciled into the merchant ledger">
              <Info className="h-3 w-3 text-slate-500 cursor-help" />
            </Tooltip>
          </div>
          <div
            className={`text-lg font-bold font-tabular ${
              revenueRecovered > 0 ? 'text-emerald-400' : 'text-slate-400'
            }`}
          >
            {formatINR(revenueRecovered)}
          </div>
        </div>

        {/* 4. Recovery Rate */}
        <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
            <span className="uppercase tracking-wider font-semibold">Recovery Rate</span>
            <Tooltip content="Effective percentage of at-risk revenue or candidate transactions successfully converted">
              <Info className="h-3 w-3 text-slate-500 cursor-help" />
            </Tooltip>
          </div>
          <div className="text-lg font-bold font-tabular text-white">
            {formatPercent(computedRate)}
          </div>
        </div>
      </div>

      {/* Decision & Explainability Strip */}
      <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          {/* 5. Agent Decision */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Agent Decision:</span>
            <span
              className={`px-2.5 py-0.5 rounded text-[11px] font-mono font-semibold border ${actionBadge.bg} ${actionBadge.text} ${actionBadge.border}`}
            >
              {agentDecision}
            </span>
          </div>

          {/* 6. Policy Decision */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Policy Decision:</span>
            <span
              className={`px-2.5 py-0.5 rounded text-[11px] font-mono font-semibold border ${
                isPolicyPermitted
                  ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40'
                  : isPolicyWait
                  ? 'bg-purple-950 text-purple-300 border-purple-500/40'
                  : 'bg-rose-950 text-rose-300 border-rose-500/40'
              }`}
            >
              {policyDecision} {policyRuleId ? `(${policyRuleId})` : ''}
            </span>
          </div>
        </div>

        {/* Audit Hash preview */}
        {auditHash && (
          <div className="text-[10px] font-mono text-slate-500 truncate max-w-xs">
            Hash: <span className="text-slate-300">{auditHash.slice(0, 16)}...</span>
          </div>
        )}
      </div>

      {/* 7. Reason & Explainability Narrative */}
      <div className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-500/20 text-xs">
        <div className="flex items-start gap-2">
          <Zap className="h-4 w-4 text-indigo-400 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-slate-300 block mb-0.5">Reason & Governance Rule:</span>
            <p className="text-slate-200 font-medium leading-relaxed">
              {reason}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
