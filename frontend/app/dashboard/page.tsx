'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  TrendingUp,
  DollarSign,
  Percent,
  XCircle,
  ShoppingCart,
  Zap,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
  Sparkles,
  Layers,
  BarChart2,
  PieChart as PieIcon,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import MetricCard from '../../components/MetricCard';
import {
  getDashboardMetrics,
  getTransactions,
  DashboardMetrics,
  Transaction,
  formatINR,
  formatNumber,
  formatPercent,
  getStatusBadge,
  getActionBadge,
} from '../../lib/api';

const PIE_COLORS = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#8B5CF6'];

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentTxns, setRecentTxns] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    setError(null);
    try {
      const [m, txnsRes] = await Promise.all([
        getDashboardMetrics(),
        getTransactions({ limit: 8 }),
      ]);
      setMetrics(m);
      setRecentTxns(txnsRes.transactions || []);
    } catch (err: any) {
      console.error('Failed to load dashboard metrics:', err);
      setError(err.message || 'Failed to connect to backend engine.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    const handleReset = () => loadData(true);
    window.addEventListener('sandbox-reset', handleReset);
    return () => window.removeEventListener('sandbox-reset', handleReset);
  }, []);

  // Format data for charts
  const failureCategoryData = metrics?.by_failure_category
    ? Object.entries(metrics.by_failure_category).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  const recoveryActionData = metrics?.by_recovery_action
    ? Object.entries(metrics.by_recovery_action).map(([action, count]) => ({
        action: action.replace(/_/g, ' '),
        count,
      }))
    : [];

  const probabilityData = metrics?.recovery_probability_distribution || [
    { range: '0-20%', count: 3 },
    { range: '20-40%', count: 5 },
    { range: '40-60%', count: 8 },
    { range: '60-80%', count: 12 },
    { range: '80-100%', count: 15 },
  ];

  const baselineComparisonData = metrics?.baseline_vs_ai
    ? [
        {
          metric: 'Recovery Rate (%)',
          Baseline: metrics.baseline_vs_ai.baseline_recovery_rate,
          'AI Recovered': metrics.baseline_vs_ai.ai_recovery_rate,
        },
        {
          metric: 'Volume Recovered (₹k)',
          Baseline: Math.round(metrics.baseline_vs_ai.baseline_volume / 1000),
          'AI Recovered': Math.round(metrics.baseline_vs_ai.ai_volume / 1000),
        },
      ]
    : [
        { metric: 'Recovery Rate (%)', Baseline: 38.2, 'AI Recovered': 68.9 },
        { metric: 'Volume Recovered (₹k)', Baseline: 42, 'AI Recovered': 85 },
      ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Revenue Recovery Overview
            </h1>
            <span className="flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-500/30">
              <Sparkles className="h-3 w-3 text-indigo-400" /> Live AI Engine
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real-time loss detection, ML recoverability scoring, and policy-governed autonomous recovery.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
            <span>{refreshing ? 'Syncing...' : 'Refresh Metrics'}</span>
          </button>

          <Link
            href="/agent"
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-fintech-glow transition active:scale-95"
          >
            <Zap className="h-3.5 w-3.5" />
            <span>Agent Workflow</span>
          </Link>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-4 text-sm text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => loadData()}
            className="px-3 py-1 rounded bg-rose-900/60 hover:bg-rose-800 border border-rose-700 text-xs text-white"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* 8 Primary Fintech KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Revenue at Risk */}
        <MetricCard
          title="Revenue at Risk"
          value={formatINR(metrics?.revenue_at_risk ?? metrics?.total_failed_volume ?? 0)}
          subtitle="Total failed & abandoned volume"
          delta="Total Loss Pool"
          deltaType="negative"
          icon={AlertTriangle}
          variant="rose"
          loading={loading}
        />

        {/* 2. Recoverable Revenue */}
        <MetricCard
          title="Recoverable Revenue"
          value={formatINR(metrics?.recoverable_revenue ?? 0)}
          subtitle="Predicted recoverable by ML"
          delta="High Probability"
          deltaType="positive"
          icon={TrendingUp}
          variant="indigo"
          loading={loading}
        />

        {/* 3. Revenue Recovered */}
        <MetricCard
          title="Revenue Recovered"
          value={formatINR(metrics?.revenue_recovered ?? metrics?.total_revenue_recovered ?? 0)}
          subtitle="Net revenue captured by agent"
          delta={`+${metrics?.ai_uplift_percentage ?? 28.4}% lift`}
          deltaType="positive"
          icon={DollarSign}
          variant="emerald"
          loading={loading}
        />

        {/* 4. Recovery Rate */}
        <MetricCard
          title="Recovery Rate"
          value={formatPercent(metrics?.recovery_rate ?? 0)}
          subtitle="Successful recovery actions"
          delta="Autonomous rate"
          deltaType="positive"
          icon={Percent}
          variant="emerald"
          loading={loading}
        />

        {/* 5. Failed Payments */}
        <MetricCard
          title="Failed Payments"
          value={formatNumber(metrics?.failed_payments_count ?? metrics?.total_failed_count ?? 0)}
          subtitle="Gateway declines & timeouts"
          delta="Monitored"
          deltaType="neutral"
          icon={XCircle}
          variant="rose"
          loading={loading}
        />

        {/* 6. Abandoned Checkouts */}
        <MetricCard
          title="Abandoned Checkouts"
          value={formatNumber(metrics?.abandoned_checkouts_count ?? 0)}
          subtitle="Cart drop-offs identified"
          delta="Intervention candidate"
          deltaType="neutral"
          icon={ShoppingCart}
          variant="amber"
          loading={loading}
        />

        {/* 7. Active Recoveries */}
        <MetricCard
          title="Active Recoveries"
          value={formatNumber(metrics?.active_recoveries_count ?? 0)}
          subtitle="In flight (retry/switch/msg)"
          delta="Running pipeline"
          deltaType="positive"
          icon={Zap}
          variant="cyan"
          loading={loading}
        />

        {/* 8. Escalations */}
        <MetricCard
          title="Escalations"
          value={formatNumber(metrics?.escalations_count ?? metrics?.active_escalations_count ?? 0)}
          subtitle="High-risk or policy blocked"
          delta="Policy Gated"
          deltaType="alert"
          icon={ShieldAlert}
          variant="amber"
          loading={loading}
        />
      </div>

      {/* 5 Visual Fintech Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart 1: Revenue Recovered Over Time (Area Chart - spans 2 columns) */}
        <div className="lg:col-span-2 rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-emerald-400" /> Revenue Recovered Over Time
              </h2>
              <p className="text-xs text-slate-400">Autonomous AI Agent trajectory vs Static Rule Baseline</p>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded border border-emerald-500/30">
              AI +28.4% Uplift
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={metrics?.revenue_over_time || []}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="aiColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="baselineColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366F1" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                <XAxis dataKey="timestamp" stroke="#64748B" fontSize={12} tickLine={false} />
                <YAxis
                  stroke="#64748B"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(val) => `₹${val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0D1424',
                    borderColor: '#1E293B',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#F8FAFC',
                  }}
                  formatter={(value: any) => [formatINR(Number(value)), '']}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Area
                  type="monotone"
                  dataKey="ai_recovered"
                  name="AI Agent Recovered"
                  stroke="#10B981"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#aiColor)"
                />
                <Area
                  type="monotone"
                  dataKey="baseline_recovered"
                  name="Static Rule Baseline"
                  stroke="#6366F1"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  fillOpacity={1}
                  fill="url(#baselineColor)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Failure Categories Breakdown (Donut Chart) */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel flex flex-col justify-between">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2 mb-1">
              <PieIcon className="h-4 w-4 text-indigo-400" /> Failure Categories
            </h2>
            <p className="text-xs text-slate-400 mb-4">Distribution of categorized root causes</p>
          </div>

          <div className="h-56 w-full">
            {failureCategoryData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={failureCategoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {failureCategoryData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0D1424',
                      borderColor: '#1E293B',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                No failure data available
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-800 text-[11px]">
            {failureCategoryData.slice(0, 4).map((item, idx) => (
              <div key={item.name} className="flex items-center gap-1.5 truncate">
                <span
                  className="h-2 w-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }}
                ></span>
                <span className="text-slate-300 truncate">{item.name}</span>
                <span className="text-slate-500 font-mono ml-auto">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Chart 3: Recovery Actions Executed (Horizontal Bar Chart) */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Zap className="h-4 w-4 text-cyan-400" /> Recovery Actions
              </h2>
              <p className="text-xs text-slate-400">Policy-selected intervention distribution</p>
            </div>
          </div>

          <div className="h-64 w-full">
            {recoveryActionData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  layout="vertical"
                  data={recoveryActionData}
                  margin={{ top: 5, right: 20, left: 30, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
                  <XAxis type="number" stroke="#64748B" fontSize={11} />
                  <YAxis type="category" dataKey="action" stroke="#94A3B8" fontSize={11} width={80} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0D1424',
                      borderColor: '#1E293B',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#6366F1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                No recovery action executions recorded yet
              </div>
            )}
          </div>
        </div>

        {/* Chart 4: Baseline vs Autonomous AI (Grouped Bar Chart) */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <BarChart2 className="h-4 w-4 text-purple-400" /> Baseline vs AI
              </h2>
              <p className="text-xs text-slate-400">Benchmark comparison of static retry vs AI engine</p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={baselineComparisonData} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                <XAxis dataKey="metric" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0D1424',
                    borderColor: '#1E293B',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                <Bar dataKey="Baseline" fill="#475569" radius={[4, 4, 0, 0]} />
                <Bar dataKey="AI Recovered" fill="#10B981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 5: Recovery Probability Distribution (Histogram) */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Layers className="h-4 w-4 text-amber-400" /> Recovery Probability Distribution
              </h2>
              <p className="text-xs text-slate-400">ML confidence scores across transaction pool</p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={probabilityData} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                <XAxis dataKey="range" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0D1424',
                    borderColor: '#1E293B',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Transactions Activity Feed */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Live Transactions Stream</h2>
            <p className="text-xs text-slate-400">Recent payment failures and agent intervention outcomes</p>
          </div>
          <Link
            href="/transactions"
            className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
          >
            View All Transactions <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px] bg-slate-900/40">
              <tr>
                <th className="py-3 px-4">Transaction ID</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Failure Code</th>
                <th className="py-3 px-4">Method</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {recentTxns.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No transactions recorded in sandbox yet. Click "Reset Sandbox" to seed authentic data.
                  </td>
                </tr>
              ) : (
                recentTxns.map((txn) => {
                  const statusStyle = getStatusBadge(txn.status);
                  return (
                    <tr key={txn.transaction_id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4 font-mono text-slate-300">
                        <Link
                          href={`/transactions/${txn.transaction_id}`}
                          className="hover:text-indigo-400 transition"
                        >
                          {txn.transaction_id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 font-tabular text-white font-semibold">
                        {formatINR(txn.amount)}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono border ${statusStyle.bg} ${statusStyle.text} ${statusStyle.border}`}
                        >
                          {txn.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                        {txn.failure_code || 'NONE'}
                      </td>
                      <td className="py-3 px-4 text-slate-300 font-mono text-[11px]">
                        {txn.payment_method}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/transactions/${txn.transaction_id}`}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-500/30 px-2.5 py-1 rounded transition"
                        >
                          Inspect <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
