'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ArrowRight,
  Shield,
  CreditCard,
  UserCheck,
  Zap,
  ChevronRight,
  ExternalLink,
  Lock,
  Layers,
  Sparkles,
} from 'lucide-react';
import {
  getSubscriptions,
  getSubscription,
  runSubscriptionRecovery,
  recordSubscriptionEvent,
  Subscription,
  SubscriptionRecoveryResponse,
  formatINR,
  formatPercent,
  getStatusBadge,
  getActionBadge,
} from '../../lib/api';

export default function SubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Recovery execution state
  const [recoveringId, setRecoveringId] = useState<string | null>(null);
  const [selectedSub, setSelectedSub] = useState<Subscription | null>(null);
  const [recoveryResult, setRecoveryResult] = useState<SubscriptionRecoveryResponse | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  const fetchSubscriptions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSubscriptions({
        state: statusFilter === 'ALL' ? undefined : statusFilter,
        limit: 100,
      });
      setSubscriptions(res.subscriptions || []);
      setMetrics(res.metrics || null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch subscriptions.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  const handleRunRecovery = async (e: React.MouseEvent, sub: Subscription) => {
    e.stopPropagation();
    setRecoveringId(sub.subscription_id);
    setSelectedSub(sub);
    setRecoveryResult(null);
    setNotification(null);

    try {
      const res = await runSubscriptionRecovery(sub.subscription_id);
      setRecoveryResult(res);
      setModalOpen(true);
      setNotification(`Recovery action '${res.selected_action}' executed successfully.`);
      await fetchSubscriptions();
    } catch (err: any) {
      setNotification(`Recovery failed: ${err.message}`);
    } finally {
      setRecoveringId(null);
    }
  };

  const handleInspect = (sub: Subscription) => {
    setSelectedSub(sub);
    setRecoveryResult(null);
    setModalOpen(true);
  };

  const filteredSubs = subscriptions.filter((sub) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      sub.subscription_id.toLowerCase().includes(q) ||
      sub.customer_id.toLowerCase().includes(q) ||
      sub.plan_name.toLowerCase().includes(q) ||
      (sub.last_failure_code && sub.last_failure_code.toLowerCase().includes(q))
    );
  });

  const lifecycleTabs = [
    { id: 'ALL', label: 'All Subscriptions' },
    { id: 'PAYMENT_FAILED', label: 'Payment Failed', badge: metrics?.payment_failed_subscriptions },
    { id: 'RETRY_SCHEDULED', label: 'Retry Scheduled', badge: metrics?.retry_scheduled_subscriptions },
    { id: 'SUBSCRIPTION_RECOVERED', label: 'Recovered', badge: metrics?.recovered_subscriptions },
    { id: 'SUBSCRIPTION_CANCELLED', label: 'Cancelled', badge: metrics?.cancelled_subscriptions },
  ];

  return (
    <div className="space-y-8 animate-fadeIn pb-16">
      {/* Top Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">
            <Sparkles className="h-4 w-4" />
            <span>Phase 18 Implementation</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            Subscription Payment Recovery
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Lifecycle tracking, customer history weighting, automated payment method switching, and churn prevention.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchSubscriptions}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/90 px-3.5 py-2 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Subscriptions</span>
          </button>
        </div>
      </div>

      {/* Metric Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* MRR at Risk */}
        <div className="relative overflow-hidden rounded-xl border border-rose-500/20 bg-gradient-to-br from-rose-950/30 to-slate-900/80 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-rose-300">MRR at Risk</span>
            <AlertTriangle className="h-4 w-4 text-rose-400" />
          </div>
          <p className="mt-3 text-2xl font-bold tracking-tight text-white">
            {formatINR(metrics?.mrr_at_risk || 0)}
          </p>
          <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-400">
            <span>{metrics?.payment_failed_subscriptions || 0} renewals requiring intervention</span>
          </div>
        </div>

        {/* MRR Recovered */}
        <div className="relative overflow-hidden rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-950/30 to-slate-900/80 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">MRR Recovered</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <p className="mt-3 text-2xl font-bold tracking-tight text-emerald-400">
            {formatINR(metrics?.mrr_recovered || 0)}
          </p>
          <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-300/80">
            <span>{metrics?.recovered_subscriptions || 0} subscriptions salvaged</span>
          </div>
        </div>

        {/* Active Accounts */}
        <div className="relative overflow-hidden rounded-xl border border-indigo-500/20 bg-gradient-to-br from-indigo-950/30 to-slate-900/80 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-300">Active Pipeline</span>
            <Clock className="h-4 w-4 text-indigo-400" />
          </div>
          <p className="mt-3 text-2xl font-bold tracking-tight text-white">
            {metrics?.retry_scheduled_subscriptions || 0}
          </p>
          <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
            <span>Intelligent retries queued</span>
          </div>
        </div>

        {/* Churn Reduced */}
        <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Monitored</span>
            <Layers className="h-4 w-4 text-slate-400" />
          </div>
          <p className="mt-3 text-2xl font-bold tracking-tight text-white">
            {metrics?.total_subscriptions || subscriptions.length}
          </p>
          <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
            <span>{metrics?.cancelled_subscriptions || 0} cancelled to date</span>
          </div>
        </div>
      </div>

      {/* Global Notice / Notification */}
      {notification && (
        <div className="flex items-center justify-between rounded-lg border border-indigo-500/30 bg-indigo-950/40 px-4 py-3 text-xs text-indigo-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-indigo-400" />
            <span>{notification}</span>
          </div>
          <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        {/* Lifecycle Tabs */}
        <div className="flex flex-wrap items-center gap-2">
          {lifecycleTabs.map((tab) => {
            const active = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  active
                    ? 'bg-indigo-600 text-white shadow-fintech-glow'
                    : 'bg-slate-900/80 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`}
              >
                <span>{tab.label}</span>
                {tab.badge !== undefined && tab.badge > 0 && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                      active ? 'bg-indigo-900 text-indigo-200' : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative min-w-[260px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search plan, customer, ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-900/90 pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Subscriptions Table */}
      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 backdrop-blur-sm">
        {loading && subscriptions.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-slate-400">
            <RefreshCw className="h-6 w-6 animate-spin text-indigo-500 mb-2" />
            <p className="text-xs">Loading subscription accounts...</p>
          </div>
        ) : filteredSubs.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-slate-400">
            <p className="text-sm font-medium text-slate-300">No subscriptions found</p>
            <p className="text-xs text-slate-500 mt-1">Try selecting a different lifecycle status or clearing your search.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="border-b border-slate-800/80 bg-slate-950/60 font-semibold uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="py-3.5 pl-6 pr-3">Subscription</th>
                  <th className="px-3 py-3.5">Plan / MRR</th>
                  <th className="px-3 py-3.5">Lifecycle State</th>
                  <th className="px-3 py-3.5">Customer History</th>
                  <th className="px-3 py-3.5">Failure Diagnostic</th>
                  <th className="px-3 py-3.5">Payment Rails</th>
                  <th className="py-3.5 pl-3 pr-6 text-right">Recovery Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {filteredSubs.map((sub) => {
                  const stateBadge = getStatusBadge(sub.current_state);
                  const isRecovering = recoveringId === sub.subscription_id;
                  const canRecover = sub.current_state === 'PAYMENT_FAILED' || sub.current_state === 'RETRY_SCHEDULED';

                  return (
                    <tr
                      key={sub.subscription_id}
                      onClick={() => handleInspect(sub)}
                      className="group cursor-pointer transition-colors hover:bg-slate-800/40"
                    >
                      {/* Subscription ID & Customer */}
                      <td className="py-4 pl-6 pr-3">
                        <div className="font-mono font-medium text-slate-200 group-hover:text-indigo-300">
                          {sub.subscription_id}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                          {sub.customer_id}
                        </div>
                      </td>

                      {/* Plan / MRR */}
                      <td className="px-3 py-4">
                        <div className="font-semibold text-white">{sub.plan_name}</div>
                        <div className="text-[11px] text-emerald-400 font-mono font-semibold">
                          {formatINR(sub.renewal_amount)}
                          <span className="text-slate-400 text-[10px] font-normal"> / {sub.billing_cycle.toLowerCase()}</span>
                        </div>
                      </td>

                      {/* Lifecycle State */}
                      <td className="px-3 py-4">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium border ${stateBadge.bg} ${stateBadge.text} ${stateBadge.border}`}
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-current" />
                          {sub.current_state.replace('SUBSCRIPTION_', '')}
                        </span>
                        {sub.recovered && (
                          <span className="ml-1.5 text-[10px] text-emerald-400 font-semibold uppercase">
                            ✓ Saved
                          </span>
                        )}
                      </td>

                      {/* Customer History */}
                      <td className="px-3 py-4">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11px] font-medium text-slate-200">
                            {sub.customer_history?.tenure_months || 1} mos tenure
                          </span>
                          <span className="text-slate-600">•</span>
                          <span className="text-[11px] text-indigo-300">
                            {sub.customer_history?.consecutive_successful_renewals || 0} renewals
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-400">
                          <span
                            className={`rounded px-1 py-0.2 font-mono ${
                              (sub.customer_history?.risk_score || 0) > 0.8
                                ? 'bg-rose-950/80 text-rose-400'
                                : 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            Risk: {(sub.customer_history?.risk_score || 0).toFixed(2)}
                          </span>
                          {sub.customer_history?.dnd_enabled && (
                            <span className="rounded bg-amber-950/80 text-amber-400 px-1 py-0.2">
                              DND
                            </span>
                          )}
                          <span className="text-slate-400">
                            LTV: {formatINR(sub.customer_history?.total_lifetime_value || 0)}
                          </span>
                        </div>
                      </td>

                      {/* Failure Diagnostic */}
                      <td className="px-3 py-4">
                        {sub.last_failure_code ? (
                          <div>
                            <span className="rounded bg-rose-950/60 border border-rose-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-rose-300">
                              {sub.last_failure_code}
                            </span>
                            <div className="mt-1 text-[10px] text-slate-400">
                              Attempt {sub.current_attempt_count} of {sub.max_retry_attempts}
                            </div>
                          </div>
                        ) : (
                          <span className="text-[11px] text-emerald-400 font-medium">None (Healthy)</span>
                        )}
                      </td>

                      {/* Payment Rails */}
                      <td className="px-3 py-4">
                        <div className="flex items-center gap-1 text-[11px] text-slate-300">
                          <CreditCard className="h-3 w-3 text-slate-400" />
                          <span>{sub.primary_method}</span>
                        </div>
                        <div className="mt-0.5 text-[10px] text-slate-400">
                          {sub.backup_method ? (
                            <span className="text-cyan-400">Backup: {sub.backup_method}</span>
                          ) : (
                            <span className="text-slate-600">No backup rail</span>
                          )}
                        </div>
                      </td>

                      {/* Recovery Action */}
                      <td className="py-4 pl-3 pr-6 text-right">
                        {canRecover ? (
                          <button
                            onClick={(e) => handleRunRecovery(e, sub)}
                            disabled={isRecovering}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-fintech-glow transition-all hover:bg-indigo-500 disabled:opacity-50"
                          >
                            <Zap className={`h-3 w-3 ${isRecovering ? 'animate-bounce' : ''}`} />
                            <span>{isRecovering ? 'Recovering...' : 'Recover Renewal'}</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => handleInspect(sub)}
                            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200"
                          >
                            <span>Inspect</span>
                            <ChevronRight className="h-3 w-3" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Interactive Recovery / Account Details Modal */}
      {modalOpen && selectedSub && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">
                  <Shield className="h-3.5 w-3.5" />
                  <span>RazorRecover AI Autonomous Pipeline</span>
                </div>
                <h2 className="text-xl font-bold text-white">
                  Subscription {selectedSub.subscription_id}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Plan: <span className="text-slate-200 font-semibold">{selectedSub.plan_name}</span> ({formatINR(selectedSub.renewal_amount)} / {selectedSub.billing_cycle})
                </p>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {/* Customer History Context */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Customer Context & Billing History
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px]">Tenure</span>
                  <span className="font-semibold text-white">
                    {selectedSub.customer_history?.tenure_months} months
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Consecutive Renewals</span>
                  <span className="font-semibold text-indigo-300">
                    {selectedSub.customer_history?.consecutive_successful_renewals} cycles
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Backup Method</span>
                  <span className="font-semibold text-cyan-300">
                    {selectedSub.backup_method || 'None'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Risk Score</span>
                  <span className="font-semibold text-white">
                    {(selectedSub.customer_history?.risk_score || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Pipeline Execution Result (if just recovered or available) */}
            {recoveryResult ? (
              <div className="space-y-4 rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-4">
                <div className="flex items-center justify-between border-b border-indigo-500/20 pb-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span className="text-sm font-bold text-white">Autonomous Decision Result</span>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                      recoveryResult.policy_outcome === 'ALLOW'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30'
                        : 'bg-rose-950 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    Policy: {recoveryResult.policy_outcome} ({recoveryResult.policy_rule_id})
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
                  <div>
                    <span className="text-slate-400 block text-[10px]">Selected Action</span>
                    <span className="font-mono font-bold text-indigo-300">
                      {recoveryResult.selected_action}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">P(Recovery | Action)</span>
                    <span className="font-mono font-bold text-emerald-400">
                      {formatPercent(recoveryResult.recovery_probability)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Expected Value (EV)</span>
                    <span className="font-mono font-bold text-white">
                      {formatINR(recoveryResult.expected_recovery_value)}
                    </span>
                  </div>
                </div>

                {/* Candidate Action Ranking */}
                <div className="space-y-1.5 pt-2">
                  <div className="text-[11px] font-semibold text-slate-300">
                    Candidate Action Ranking (P(recovery) & Expected Value)
                  </div>
                  <div className="space-y-1">
                    {recoveryResult.candidates?.map((c) => (
                      <div
                        key={c.action}
                        className={`flex items-center justify-between rounded px-2.5 py-1.5 text-xs ${
                          c.action === recoveryResult.selected_action
                            ? 'bg-indigo-600/30 border border-indigo-500/40 text-white font-medium'
                            : 'bg-slate-900/60 text-slate-400'
                        }`}
                      >
                        <span className="font-mono text-[11px]">{c.action}</span>
                        <div className="flex items-center gap-3 font-mono text-[11px]">
                          <span>P: {formatPercent(c.probability)}</span>
                          <span>EV: {formatINR(c.expected_recovery_value)}</span>
                          <span
                            className={`text-[10px] ${
                              c.permitted ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {c.permitted ? 'ALLOWED' : 'BLOCKED'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Simulator Execution Output */}
                <div className="rounded-lg bg-slate-950/80 p-3 text-xs font-mono space-y-1">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Simulator Output:</div>
                  <div className="text-emerald-400">
                    Status: {recoveryResult.execution?.status || 'COMPLETED'}
                  </div>
                  <div className="text-slate-300">
                    Message: {recoveryResult.execution?.message || 'Action executed successfully.'}
                  </div>
                  {recoveryResult.audit_hash && (
                    <div className="text-slate-500 text-[10px] truncate pt-1 border-t border-slate-800">
                      Audit Hash: <span className="text-indigo-400">{recoveryResult.audit_hash}</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-xs font-semibold text-slate-300">
                  Lifecycle Event Timeline ({selectedSub.events?.length || 0} events)
                </div>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {selectedSub.events?.map((ev, idx) => (
                    <div
                      key={ev.event_id || idx}
                      className="flex items-start justify-between rounded-lg border border-slate-800 bg-slate-950/50 p-2.5 text-xs"
                    >
                      <div>
                        <span className="font-semibold text-slate-200">{ev.state}</span>
                        {ev.action && (
                          <span className="ml-2 font-mono text-[11px] text-indigo-400">
                            [{ev.action}]
                          </span>
                        )}
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {new Date(ev.timestamp).toLocaleString()}
                        </div>
                      </div>
                      {ev.audit_hash && (
                        <span className="font-mono text-[10px] text-slate-500 truncate max-w-[120px]">
                          {ev.audit_hash.slice(0, 8)}...
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between border-t border-slate-800 pt-4">
              <Link
                href="/audit"
                className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300"
              >
                <span>View in Cryptographic Audit Log</span>
                <ExternalLink className="h-3 w-3" />
              </Link>
              <button
                onClick={() => setModalOpen(false)}
                className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
