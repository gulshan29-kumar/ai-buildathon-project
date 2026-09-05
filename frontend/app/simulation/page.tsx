'use client';

import React, { useState, useEffect } from 'react';
import {
  PlayCircle,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sliders,
  DollarSign,
  TrendingUp,
  Percent,
  Layers,
  ArrowRight,
  AlertCircle,
  Sparkles,
  ShieldCheck,
  ShieldAlert,
  Search,
  Eye,
  X,
  Clock,
  ArrowUpRight,
  Activity,
  Zap,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  Cell,
  PieChart,
  Pie,
} from 'recharts';
import MetricCard from '../../components/MetricCard';
import DecisionAuditStrip from '../../components/DecisionAuditStrip';
import {
  runSimulation,
  resetDemo,
  SimulationRunResponse,
  TransactionComparisonTrace,
  formatINR,
  formatNumber,
  formatPercent,
  getStatusBadge,
  getActionBadge,
} from '../../lib/api';

const PIPELINE_STAGES = [
  { step: 1, label: 'Synthetic Events', desc: 'Generating payment payloads' },
  { step: 2, label: 'ML Prediction', desc: 'XGBoost calibrated recoverability' },
  { step: 3, label: 'Root Cause', desc: 'Failure taxonomy diagnostic' },
  { step: 4, label: 'Action Ranking', desc: 'Expected value ordering' },
  { step: 5, label: 'Policy Guardrails', desc: 'Enforcing 12 safety rules' },
  { step: 6, label: 'Simulator Execution', desc: 'State machine execution' },
  { step: 7, label: 'SHA-256 Audit', desc: 'Cryptographic ledger chaining' },
];

export default function SimulationPage() {
  // Config state
  const [txnCount, setTxnCount] = useState<number>(50);
  const [seed, setSeed] = useState<number>(42);
  const [scenario, setScenario] = useState<string>('mixed_failures');

  // Execution & Progress state
  const [isRunning, setIsRunning] = useState(false);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [isResetting, setIsResetting] = useState(false);
  const [simResult, setSimResult] = useState<SimulationRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Inspection Drawer & Filter state
  const [selectedTxn, setSelectedTxn] = useState<TransactionComparisonTrace | null>(null);
  const [txnSearch, setTxnSearch] = useState('');
  const [txnFilter, setTxnFilter] = useState<'all' | 'ai_recovered' | 'ai_won' | 'escalated' | 'failed'>('all');

  // Run comparative simulation
  const handleRunSimulation = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setError(null);
    setNotice(null);
    setCurrentProgress(10);
    setActiveStageIndex(0);

    // Progress animation intervals
    const progressTimer = setInterval(() => {
      setCurrentProgress((prev) => {
        if (prev < 90) {
          const next = prev + Math.floor(Math.random() * 15 + 10);
          setActiveStageIndex(Math.min(6, Math.floor((next / 100) * 7)));
          return next;
        }
        return prev;
      });
    }, 200);

    try {
      const res = await runSimulation({
        transaction_count: txnCount,
        seed,
        scenario,
      });

      clearInterval(progressTimer);
      setCurrentProgress(100);
      setActiveStageIndex(6);
      setSimResult(res);

      const upliftGain = res.uplift?.revenue_gain ? formatINR(res.uplift.revenue_gain) : '₹0';
      const upliftPct = res.uplift?.revenue_uplift_pct ? `+${res.uplift.revenue_uplift_pct}%` : '';
      setNotice(
        `Simulation completed: AI recovered ${res.ai_metrics?.recovered_count || res.recovered_count}/${res.total_transactions || res.transaction_count} payments (${formatPercent(res.ai_metrics?.recovery_rate || res.recovery_rate)}), capturing ${upliftGain} net uplift (${upliftPct}).`
      );
    } catch (err: any) {
      clearInterval(progressTimer);
      setError(err.message || 'Simulation execution failed.');
    } finally {
      setTimeout(() => {
        setIsRunning(false);
      }, 400);
    }
  };

  // Reset sandbox
  const handleReset = async () => {
    if (isResetting) return;
    setIsResetting(true);
    try {
      await resetDemo(true);
      setSimResult(null);
      setCurrentProgress(0);
      setNotice('Sandbox cleared and reseeded with 30 authentic baseline transactions.');
    } catch (err: any) {
      setError(`Reset error: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  // Filter transactions
  const filteredTransactions = (simResult?.transactions || []).filter((t) => {
    // Search query
    const q = txnSearch.toLowerCase();
    const matchesSearch =
      !q ||
      t.transaction_id.toLowerCase().includes(q) ||
      t.customer_id.toLowerCase().includes(q) ||
      t.failure_code.toLowerCase().includes(q);

    if (!matchesSearch) return false;

    // Filter pill
    if (txnFilter === 'ai_recovered') return t.ai.recovered;
    if (txnFilter === 'ai_won') return t.ai_won;
    if (txnFilter === 'escalated') return t.ai.escalated;
    if (txnFilter === 'failed') return !t.ai.recovered;
    return true;
  });

  // Chart data: Revenue Comparison
  const revenueChartData = simResult
    ? [
        {
          name: 'Revenue at Risk',
          amount: simResult.revenue_at_risk || 0,
          fill: '#EF4444',
        },
        {
          name: 'Baseline Recovered',
          amount: simResult.baseline_metrics?.recovered_revenue || 0,
          fill: '#64748B',
        },
        {
          name: 'RazorRecover AI',
          amount: simResult.ai_metrics?.recovered_revenue || 0,
          fill: '#10B981',
        },
      ]
    : [];

  // Chart data: Efficiency Rates
  const rateChartData = simResult
    ? [
        {
          category: 'Recovery Rate',
          Baseline: ((simResult.baseline_metrics?.recovery_rate || 0) * 100),
          'RazorRecover AI': ((simResult.ai_metrics?.recovery_rate || 0) * 100),
        },
        {
          category: 'Unnecessary Intervention Rate',
          Baseline: ((simResult.baseline_metrics?.unnecessary_intervention_rate || 0) * 100),
          'RazorRecover AI': ((simResult.ai_metrics?.unnecessary_intervention_rate || 0) * 100),
        },
      ]
    : [];

  // Chart data: Category Resolution Breakdown
  const categoryChartData = simResult?.category_breakdown
    ? Object.entries(simResult.category_breakdown).map(([code, stats]: [string, any]) => ({
        code: code.replace(/_/g, ' '),
        Total: stats.total,
        Baseline: stats.baseline_recovered,
        'RazorRecover AI': stats.ai_recovered,
      }))
    : [];

  // Chart data: AI Actions Distribution
  const actionChartData = simResult?.ai_actions_distribution
    ? Object.entries(simResult.ai_actions_distribution).map(([action, count]) => ({
        name: action.replace(/_/g, ' '),
        count,
      }))
    : [];

  const ACTION_COLORS = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Large-Scale Revenue Recovery Simulation
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-500/40 flex items-center gap-1">
              <Sparkles className="h-3 w-3 text-indigo-400" /> Phase 16 Benchmark
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Simulate high-concurrency payment failures and compare a non-intelligent baseline against autonomous RazorRecover AI across 11 financial metrics.
          </p>
        </div>

        <button
          onClick={handleReset}
          disabled={isResetting}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition active:scale-95 disabled:opacity-50"
        >
          <RotateCcw className={`h-3.5 w-3.5 ${isResetting ? 'animate-spin text-indigo-400' : ''}`} />
          <span>{isResetting ? 'Resetting...' : 'Reset Sandbox'}</span>
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-4 flex items-center gap-3 text-rose-300 text-sm">
          <AlertCircle className="h-5 w-5 text-rose-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {notice && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/40 p-4 flex items-center gap-3 text-emerald-300 text-sm">
          <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {/* Parameters & Simulation Control Panel */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="h-4 w-4 text-indigo-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Simulation Parameters & Scenario Setup
            </h2>
          </div>
          <span className="text-xs font-mono text-slate-400">Deterministic PRNG Simulator</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Transaction Count */}
          <div className="space-y-2">
            <label className="text-xs text-slate-400 font-medium">Transaction Count:</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="10"
                max="500"
                step="10"
                value={txnCount}
                onChange={(e) => setTxnCount(Math.max(10, Math.min(500, Number(e.target.value))))}
                className="w-24 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
              />
              <div className="flex gap-1">
                {[25, 50, 100, 250].map((c) => (
                  <button
                    key={c}
                    onClick={() => setTxnCount(c)}
                    className={`px-2 py-1 rounded text-[11px] font-mono transition ${
                      txnCount === c
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Random Seed */}
          <div className="space-y-2">
            <label className="text-xs text-slate-400 font-medium">Random Seed (Reproducibility):</label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Scenario Selector */}
          <div className="space-y-2">
            <label className="text-xs text-slate-400 font-medium">Failure Scenario:</label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
            >
              <option value="mixed_failures">Mixed Production Failures</option>
              <option value="gateway_outage">Gateway Outage Spike (Timeouts)</option>
              <option value="abandonment_surge">Cart Abandonment Wave</option>
              <option value="high_risk_influx">High Risk Fraud Influx</option>
            </select>
          </div>

          {/* Run Button */}
          <div className="flex items-end">
            <button
              onClick={handleRunSimulation}
              disabled={isRunning}
              className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 shadow-fintech-glow transition active:scale-95 disabled:opacity-50"
            >
              <PlayCircle className={`h-4 w-4 ${isRunning ? 'animate-spin' : ''}`} />
              <span>{isRunning ? 'Running Large-Scale Simulation...' : 'Run Simulation'}</span>
            </button>
          </div>
        </div>

        {/* Live Stepped Progress Tracker */}
        {(isRunning || currentProgress > 0) && (
          <div className="pt-2 border-t border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
                Pipeline Execution Progress:
              </span>
              <span className="font-mono text-indigo-300 font-bold">{currentProgress}% Complete</span>
            </div>

            {/* Glowing progress bar */}
            <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 transition-all duration-300 rounded-full shadow-fintech-glow"
                style={{ width: `${currentProgress}%` }}
              />
            </div>

            {/* 7 Pipeline Stages */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-1">
              {PIPELINE_STAGES.map((s, idx) => {
                const isPassed = activeStageIndex > idx || currentProgress === 100;
                const isCurrent = activeStageIndex === idx && isRunning;

                return (
                  <div
                    key={s.step}
                    className={`p-2 rounded-lg border text-[11px] transition-all ${
                      isCurrent
                        ? 'border-amber-500/60 bg-amber-950/20 text-amber-300 animate-pulse'
                        : isPassed
                        ? 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300'
                        : 'border-slate-800/60 bg-slate-900/30 text-slate-500'
                    }`}
                  >
                    <div className="flex items-center gap-1 font-mono font-bold">
                      <span>{s.step}.</span>
                      <span className="truncate">{s.label}</span>
                    </div>
                    <p className="text-[10px] text-slate-400 truncate mt-0.5">{s.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Results Section */}
      {simResult && (
        <div className="space-y-8 animate-fadeIn">
          {/* Executive Financial Uplift Banner */}
          <div className="rounded-2xl border border-emerald-500/40 bg-gradient-to-b from-emerald-950/30 to-slate-950 p-6 shadow-fintech-glow-emerald">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <span className="p-2.5 rounded-xl bg-emerald-950 border border-emerald-500/40 text-emerald-400">
                  <ShieldCheck className="h-6 w-6" />
                </span>
                <div>
                  <h3 className="text-lg font-bold text-white tracking-tight">
                    Simulation Comparative Financial Yield
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5 font-mono">
                    Run ID: {simResult.run_id} &bull; Seed: {simResult.seed} &bull; Scenario: {simResult.scenario}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                  <ArrowUpRight className="h-3.5 w-3.5" /> Net Revenue Uplift: +{simResult.uplift?.revenue_uplift_pct || 0}%
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4">
              <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-4 space-y-1">
                <span className="text-[11px] uppercase tracking-wider text-slate-400">Revenue at Risk</span>
                <p className="text-xl font-bold font-tabular text-white">{formatINR(simResult.revenue_at_risk || 0)}</p>
                <span className="text-[10px] text-slate-500 font-mono">
                  {simResult.total_transactions} at-risk payment events
                </span>
              </div>

              <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-4 space-y-1">
                <span className="text-[11px] uppercase tracking-wider text-slate-400">Baseline Naive Recovered</span>
                <p className="text-xl font-bold font-tabular text-slate-300">
                  {formatINR(simResult.baseline_metrics?.recovered_revenue || 0)}
                </p>
                <span className="text-[10px] text-slate-400 font-mono">
                  {simResult.baseline_metrics?.recovered_count} recovered &bull; {formatPercent(simResult.baseline_metrics?.recovery_rate || 0)}
                </span>
              </div>

              <div className="rounded-xl bg-emerald-950/30 border border-emerald-500/30 p-4 space-y-1">
                <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-semibold">
                  RazorRecover AI Recovered
                </span>
                <p className="text-xl font-bold font-tabular text-emerald-400">
                  {formatINR(simResult.ai_metrics?.recovered_revenue || simResult.recovered_revenue)}
                </p>
                <span className="text-[10px] text-emerald-300 font-mono">
                  {simResult.ai_metrics?.recovered_count} recovered &bull; {formatPercent(simResult.ai_metrics?.recovery_rate || simResult.recovery_rate)}
                </span>
              </div>

              <div className="rounded-xl bg-indigo-950/30 border border-indigo-500/30 p-4 space-y-1">
                <span className="text-[11px] uppercase tracking-wider text-indigo-400 font-semibold">
                  Net Revenue Uplift Gain
                </span>
                <p className="text-xl font-bold font-tabular text-indigo-300">
                  +{formatINR(simResult.uplift?.revenue_gain || 0)}
                </p>
                <span className="text-[10px] text-indigo-400 font-mono">
                  +{simResult.uplift?.recovery_rate_diff_pct}% recovery rate uplift
                </span>
              </div>
            </div>
          </div>

          {/* 11-Metric Detailed Side-by-Side Comparison Table */}
          <div className="rounded-xl border border-fintech-border bg-fintech-card/80 shadow-fintech-card overflow-hidden">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Percent className="h-4 w-4 text-indigo-400" />
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                  Comparative Dimension Matrix: Baseline vs. RazorRecover AI
                </h3>
              </div>
              <span className="text-xs text-slate-400 font-mono">11 Analytical Metrics</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/90 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-5 py-3.5">Metric Dimension</th>
                    <th className="px-5 py-3.5 text-slate-400">Baseline (Blind 1-Time Retry)</th>
                    <th className="px-5 py-3.5 text-emerald-400">RazorRecover AI (Autonomous)</th>
                    <th className="px-5 py-3.5 text-right">AI Advantage / Delta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {/* 1. Total Transactions */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">1. Total Transactions</td>
                    <td className="px-5 py-3 text-slate-400">{simResult.baseline_metrics?.total_transactions}</td>
                    <td className="px-5 py-3 text-white font-bold">{simResult.ai_metrics?.total_transactions}</td>
                    <td className="px-5 py-3 text-right text-slate-500">Benchmark identical</td>
                  </tr>

                  {/* 2. Failed Transactions */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">2. Failed Transactions</td>
                    <td className="px-5 py-3 text-slate-400">{simResult.baseline_metrics?.failed_transactions}</td>
                    <td className="px-5 py-3 text-white font-bold">{simResult.ai_metrics?.failed_transactions}</td>
                    <td className="px-5 py-3 text-right text-slate-500">Initial failures needing intervention</td>
                  </tr>

                  {/* 3. Recoverable Opportunities */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">3. Recoverable Opportunities</td>
                    <td className="px-5 py-3 text-slate-400">{simResult.baseline_metrics?.recoverable_opportunities}</td>
                    <td className="px-5 py-3 text-white font-bold">{simResult.ai_metrics?.recoverable_opportunities}</td>
                    <td className="px-5 py-3 text-right text-slate-500">Non-fraud opportunities</td>
                  </tr>

                  {/* 4. Revenue at Risk */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">4. Revenue at Risk</td>
                    <td className="px-5 py-3 text-slate-400">{formatINR(simResult.baseline_metrics?.revenue_at_risk || 0)}</td>
                    <td className="px-5 py-3 text-white font-bold">{formatINR(simResult.ai_metrics?.revenue_at_risk || 0)}</td>
                    <td className="px-5 py-3 text-right text-slate-500">Total at-risk capital pool</td>
                  </tr>

                  {/* 5. Recovered Revenue */}
                  <tr className="hover:bg-slate-900/40 transition bg-emerald-950/10">
                    <td className="px-5 py-3 font-medium text-slate-200 font-sans">5. Recovered Revenue</td>
                    <td className="px-5 py-3 text-slate-400">{formatINR(simResult.baseline_metrics?.recovered_revenue || 0)}</td>
                    <td className="px-5 py-3 text-emerald-400 font-bold">{formatINR(simResult.ai_metrics?.recovered_revenue || 0)}</td>
                    <td className="px-5 py-3 text-right text-emerald-400 font-bold">
                      +{formatINR(simResult.uplift?.revenue_gain || 0)} (+{simResult.uplift?.revenue_uplift_pct}%)
                    </td>
                  </tr>

                  {/* 6. Recovery Rate */}
                  <tr className="hover:bg-slate-900/40 transition bg-emerald-950/10">
                    <td className="px-5 py-3 font-medium text-slate-200 font-sans">6. Recovery Rate</td>
                    <td className="px-5 py-3 text-slate-400">{formatPercent(simResult.baseline_metrics?.recovery_rate || 0)}</td>
                    <td className="px-5 py-3 text-emerald-400 font-bold">{formatPercent(simResult.ai_metrics?.recovery_rate || 0)}</td>
                    <td className="px-5 py-3 text-right text-emerald-400 font-bold">
                      +{simResult.uplift?.recovery_rate_diff_pct}% Absolute Lift
                    </td>
                  </tr>

                  {/* 7. Average Recovery Time */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">7. Average Recovery Time</td>
                    <td className="px-5 py-3 text-slate-400">{simResult.baseline_metrics?.average_recovery_time_ms} ms</td>
                    <td className="px-5 py-3 text-white font-bold">{simResult.ai_metrics?.average_recovery_time_ms} ms</td>
                    <td className="px-5 py-3 text-right text-indigo-400">Optimal exponential backoff</td>
                  </tr>

                  {/* 8. Retry Attempts */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">8. Retry Attempts Dispatched</td>
                    <td className="px-5 py-3 text-slate-400">{simResult.baseline_metrics?.retry_attempts} (Blind)</td>
                    <td className="px-5 py-3 text-white font-bold">{simResult.ai_metrics?.retry_attempts} (Selective)</td>
                    <td className="px-5 py-3 text-right text-emerald-400">
                      -{Math.round(((simResult.baseline_metrics?.retry_attempts || 1) - (simResult.ai_metrics?.retry_attempts || 0)) / (simResult.baseline_metrics?.retry_attempts || 1) * 100)}% Fewer Blind Attempts
                    </td>
                  </tr>

                  {/* 9. Blocked Actions */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">9. Blocked Actions (Policy Interventions)</td>
                    <td className="px-5 py-3 text-rose-400">{simResult.baseline_metrics?.blocked_actions} (0 guardrails)</td>
                    <td className="px-5 py-3 text-indigo-400 font-bold">{simResult.ai_metrics?.blocked_actions} (12 deterministic rules)</td>
                    <td className="px-5 py-3 text-right text-indigo-400">Protected merchant rails</td>
                  </tr>

                  {/* 10. Escalations */}
                  <tr className="hover:bg-slate-900/40 transition">
                    <td className="px-5 py-3 font-medium text-slate-300 font-sans">10. Escalations (High Risk / Fraud)</td>
                    <td className="px-5 py-3 text-slate-400">{simResult.baseline_metrics?.escalations} (Ignored risk)</td>
                    <td className="px-5 py-3 text-amber-400 font-bold">{simResult.ai_metrics?.escalations} routed to review</td>
                    <td className="px-5 py-3 text-right text-amber-400">Safe compliance gating</td>
                  </tr>

                  {/* 11. Unnecessary Intervention Rate */}
                  <tr className="hover:bg-slate-900/40 transition bg-rose-950/10">
                    <td className="px-5 py-3 font-medium text-slate-200 font-sans">11. Unnecessary Intervention Rate</td>
                    <td className="px-5 py-3 text-rose-400 font-bold">{formatPercent(simResult.baseline_metrics?.unnecessary_intervention_rate || 0)}</td>
                    <td className="px-5 py-3 text-emerald-400 font-bold">{formatPercent(simResult.ai_metrics?.unnecessary_intervention_rate || 0)}</td>
                    <td className="px-5 py-3 text-right text-emerald-400 font-bold">
                      -{simResult.uplift?.intervention_reduction_pct}% Reduction in Waste
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Visual Recharts Comparison Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Chart 1: Revenue Comparison */}
            <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-emerald-400" /> Revenue Recovered: Baseline vs. RazorRecover AI
              </h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={revenueChartData} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="name" stroke="#94A3B8" fontSize={11} />
                    <YAxis stroke="#94A3B8" fontSize={11} tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`} />
                    <Tooltip
                      formatter={(val: any) => [formatINR(Number(val)), 'Amount']}
                      contentStyle={{ backgroundColor: '#090D16', borderColor: '#1E293B', borderRadius: '8px' }}
                    />
                    <Bar dataKey="amount" radius={[6, 6, 0, 0]}>
                      {revenueChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 2: Efficiency & Rates */}
            <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
                <Percent className="h-4 w-4 text-indigo-400" /> Operational Efficiency & Rate Comparison (%)
              </h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rateChartData} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="category" stroke="#94A3B8" fontSize={11} />
                    <YAxis stroke="#94A3B8" fontSize={11} unit="%" />
                    <Tooltip
                      formatter={(val: any) => [`${Number(val).toFixed(1)}%`, '']}
                      contentStyle={{ backgroundColor: '#090D16', borderColor: '#1E293B', borderRadius: '8px' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Bar dataKey="Baseline" fill="#64748B" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="RazorRecover AI" fill="#10B981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 3: Failure Code Resolution Breakdown */}
            <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
                <Layers className="h-4 w-4 text-purple-400" /> Resolution Yield by Failure Reason (Volume)
              </h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoryChartData} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="code" stroke="#94A3B8" fontSize={10} angle={-15} textAnchor="end" />
                    <YAxis stroke="#94A3B8" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: '#090D16', borderColor: '#1E293B', borderRadius: '8px' }} />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    <Bar dataKey="Baseline" fill="#64748B" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="RazorRecover AI" fill="#6366F1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 4: AI Actions Distribution */}
            <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" /> RazorRecover AI: Actions Mix Breakdown
              </h4>
              <div className="h-64 flex items-center justify-center">
                {actionChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={actionChartData}
                        dataKey="count"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={(entry) => `${entry.name} (${entry.count})`}
                        labelLine={false}
                        fontSize={10}
                      >
                        {actionChartData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={ACTION_COLORS[index % ACTION_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: '#090D16', borderColor: '#1E293B', borderRadius: '8px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-xs text-slate-500">No actions to display</p>
                )}
              </div>
            </div>
          </div>

          {/* Interactive Individual Transaction Inspector Table */}
          <div className="rounded-xl border border-fintech-border bg-fintech-card/80 shadow-fintech-card space-y-4 p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                  Inspect Individual Simulated Transactions
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Granular side-by-side audit trace of every simulated payment and policy intervention.
                </p>
              </div>

              {/* Search & Filters */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search ID, customer, code..."
                    value={txnSearch}
                    onChange={(e) => setTxnSearch(e.target.value)}
                    className="bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono w-48"
                  />
                </div>

                <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 text-[11px]">
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'ai_recovered', label: 'AI Recovered' },
                    { id: 'ai_won', label: 'AI Won Only' },
                    { id: 'escalated', label: 'Escalated' },
                    { id: 'failed', label: 'Unrecovered' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setTxnFilter(tab.id as any)}
                      className={`px-2.5 py-1 rounded font-medium transition ${
                        txnFilter === tab.id ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Transactions Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Transaction ID</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Failure Reason</th>
                    <th className="px-4 py-3">Customer / Risk</th>
                    <th className="px-4 py-3">Baseline Result</th>
                    <th className="px-4 py-3">AI Selected Action</th>
                    <th className="px-4 py-3">AI Outcome</th>
                    <th className="px-4 py-3 text-center">Uplift</th>
                    <th className="px-4 py-3 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {filteredTransactions.slice(0, 50).map((t) => (
                    <tr key={t.transaction_id} className="hover:bg-slate-900/50 transition">
                      <td className="px-4 py-3 text-indigo-300 font-bold">{t.transaction_id}</td>
                      <td className="px-4 py-3 text-white font-tabular font-bold">{formatINR(t.amount)}</td>
                      <td className="px-4 py-3 text-rose-400">{t.failure_code}</td>
                      <td className="px-4 py-3 text-slate-400 font-sans">
                        <span className="font-mono text-slate-300">{t.customer_id}</span>
                        <span
                          className={`ml-1.5 text-[10px] font-mono px-1 rounded ${
                            t.risk_score > 0.8
                              ? 'bg-rose-950 text-rose-400'
                              : t.risk_score > 0.3
                              ? 'bg-amber-950 text-amber-400'
                              : 'bg-emerald-950 text-emerald-400'
                          }`}
                        >
                          {t.risk_score}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            t.baseline.recovered
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30'
                              : 'bg-slate-900 text-slate-400 border border-slate-800'
                          }`}
                        >
                          {t.baseline.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-500/30">
                          {t.ai.action}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            t.ai.recovered
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30 font-bold'
                              : t.ai.escalated
                              ? 'bg-rose-950 text-rose-400 border border-rose-500/30'
                              : 'bg-slate-900 text-slate-400 border border-slate-800'
                          }`}
                        >
                          {t.ai.recovered ? 'RECOVERED' : t.ai.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {t.ai_won ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-bold">
                            AI WON
                          </span>
                        ) : t.ai.recovered && t.baseline.recovered ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-900 text-slate-400 border border-slate-800">
                            BOTH
                          </span>
                        ) : t.ai.escalated ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-950 text-rose-400 border border-rose-500/30">
                            BLOCKED
                          </span>
                        ) : (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setSelectedTxn(t)}
                          className="flex items-center gap-1 ml-auto px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition"
                        >
                          <Eye className="h-3 w-3" />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filteredTransactions.length > 50 && (
              <p className="text-center text-xs text-slate-500 pt-2 font-mono">
                Showing top 50 of {filteredTransactions.length} transactions. Refine search for specific transactions.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Slide-over Inspection Drawer */}
      {selectedTxn && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-950/70 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-xl h-full bg-slate-950 border-l border-slate-800 p-6 overflow-y-auto space-y-6 shadow-2xl">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-[11px] font-mono text-slate-400">Transaction Deep-Dive Audit</span>
                <h3 className="text-lg font-bold text-white font-mono mt-0.5">{selectedTxn.transaction_id}</h3>
              </div>
              <button
                onClick={() => setSelectedTxn(null)}
                className="p-1.5 rounded-lg bg-slate-900 text-slate-400 hover:text-white border border-slate-800 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Executive Decision & Policy Audit Strip */}
            <DecisionAuditStrip
              revenueAtRisk={selectedTxn.amount}
              recoverableRevenue={Math.round(selectedTxn.amount * (selectedTxn.ai.recovery_probability || 0.75))}
              revenueRecovered={selectedTxn.ai.recovered ? selectedTxn.ai.recovered_amount : 0}
              recoveryRate={(selectedTxn.ai.recovery_probability || 0.75) * 100}
              agentDecision={selectedTxn.ai.action}
              policyDecision={selectedTxn.ai.policy_decision}
              policyRuleId={selectedTxn.ai.policy_rule_id}
              reason={`Root cause categorized as ${selectedTxn.ai.root_cause}. Model estimated ${formatPercent(
                selectedTxn.ai.recovery_probability
              )} recovery probability. Policy verified Rule ${selectedTxn.ai.policy_rule_id} [${
                selectedTxn.ai.policy_decision
              }].`}
              auditHash={selectedTxn.ai.audit_hash}
              verifiedIntegrity={true}
              title="Simulated Transaction Decision Audit"
            />

            {/* Context Summary Cards */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-0.5">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Amount</span>
                <p className="text-lg font-bold font-tabular text-white">{formatINR(selectedTxn.amount)}</p>
                <span className="text-[10px] text-slate-500 font-mono">Rail: {selectedTxn.payment_method}</span>
              </div>

              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-0.5">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Failure Reason</span>
                <p className="text-xs font-bold font-mono text-rose-400 truncate">{selectedTxn.failure_code}</p>
                <span className="text-[10px] text-slate-500 font-mono">Recoverable: {selectedTxn.recoverable ? 'YES' : 'NO'}</span>
              </div>
            </div>

            {/* Customer & Risk Profile */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Customer Profile:</span>
                <span className="font-mono text-slate-200">{selectedTxn.customer_id}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Risk Score & Tier:</span>
                <span className="font-mono font-bold text-rose-400">
                  {selectedTxn.risk_score} ({selectedTxn.customer_history?.risk_tier || 'LOW'})
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Historical Orders / Success:</span>
                <span className="font-mono text-slate-300">
                  {selectedTxn.customer_history?.total_orders || 10} orders &bull;{' '}
                  {formatPercent(selectedTxn.customer_history?.success_rate || 0.88)}
                </span>
              </div>
            </div>

            {/* Baseline vs AI Comparative Lifecycle */}
            <div className="space-y-4">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <TrendingUp className="h-4 w-4 text-indigo-400" /> Comparative Lifecycle Analysis
              </h4>

              {/* Baseline Card */}
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-2 text-xs">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="font-bold text-slate-300 font-mono">Strategy: BASELINE (Naive)</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      selectedTxn.baseline.recovered
                        ? 'bg-emerald-950 text-emerald-400'
                        : 'bg-rose-950 text-rose-400'
                    }`}
                  >
                    {selectedTxn.baseline.recovered ? 'RECOVERED' : 'FAILED'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                  <div>
                    <span className="text-slate-500">Action:</span> {selectedTxn.baseline.action}
                  </div>
                  <div>
                    <span className="text-slate-500">Time:</span> {selectedTxn.baseline.time_ms} ms
                  </div>
                  <div>
                    <span className="text-slate-500">Status:</span> {selectedTxn.baseline.status}
                  </div>
                  <div>
                    <span className="text-slate-500">Unnecessary:</span> {selectedTxn.baseline.unnecessary ? 'YES' : 'NO'}
                  </div>
                </div>
              </div>

              {/* AI Card */}
              <div
                className={`p-4 rounded-xl border space-y-2 text-xs ${
                  selectedTxn.ai.recovered
                    ? 'border-emerald-500/40 bg-emerald-950/20'
                    : selectedTxn.ai.escalated
                    ? 'border-rose-500/40 bg-rose-950/20'
                    : 'border-indigo-500/40 bg-indigo-950/20'
                }`}
              >
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="font-bold text-emerald-400 font-mono flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-indigo-400" /> Strategy: RAZORRECOVER AI
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      selectedTxn.ai.recovered
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                        : selectedTxn.ai.escalated
                        ? 'bg-rose-950 text-rose-300 border border-rose-500/40'
                        : 'bg-slate-900 text-slate-300'
                    }`}
                  >
                    {selectedTxn.ai.recovered ? 'RECOVERED' : selectedTxn.ai.status}
                  </span>
                </div>

                <div className="space-y-1.5 pt-1 text-[11px] font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Root Cause Category:</span>
                    <strong className="text-white">{selectedTxn.ai.root_cause}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">ML Predicted Probability:</span>
                    <strong className="text-emerald-400 font-bold">
                      {formatPercent(selectedTxn.ai.recovery_probability)}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Selected Action:</span>
                    <strong className="text-indigo-300">{selectedTxn.ai.action}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Policy Guardrail Checked:</span>
                    <span className="text-white">
                      Rule <strong>{selectedTxn.ai.policy_rule_id}</strong> &bull;{' '}
                      <strong
                        className={selectedTxn.ai.policy_decision === 'ALLOWED' ? 'text-emerald-400' : 'text-rose-400'}
                      >
                        {selectedTxn.ai.policy_decision}
                      </strong>
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Execution Status:</span>
                    <span className="text-white font-bold">{selectedTxn.ai.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Recovered Revenue:</span>
                    <strong className="text-emerald-400 font-tabular font-bold">
                      {formatINR(selectedTxn.ai.recovered_amount)}
                    </strong>
                  </div>
                </div>

                {/* Audit Hash */}
                {selectedTxn.ai.audit_hash && (
                  <div className="pt-2 border-t border-slate-800 text-[10px] font-mono flex items-center justify-between text-slate-400">
                    <span>SHA-256 Audit Hash:</span>
                    <span className="text-indigo-300 truncate max-w-[200px]" title={selectedTxn.ai.audit_hash}>
                      {selectedTxn.ai.audit_hash}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
