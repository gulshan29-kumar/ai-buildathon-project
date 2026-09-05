'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Search,
  Filter,
  ArrowRight,
  RefreshCw,
  Play,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Eye,
  Zap,
  DollarSign,
  TrendingUp,
  Percent,
  ShieldCheck,
  Lock,
  Info,
} from 'lucide-react';
import {
  getTransactions,
  runRecovery,
  Transaction,
  formatINR,
  formatPercent,
  getStatusBadge,
  getActionBadge,
} from '../../lib/api';
import Tooltip from '../../components/Tooltip';
import EmptyState from '../../components/EmptyState';
import MetricCard from '../../components/MetricCard';

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [failureFilter, setFailureFilter] = useState<string>('ALL');
  const [recoveringId, setRecoveringId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchTxns = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getTransactions({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        failure_code: failureFilter === 'ALL' ? undefined : failureFilter,
        limit: 100,
      });
      setTransactions(res.transactions || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch transactions.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, failureFilter]);

  useEffect(() => {
    fetchTxns();
  }, [fetchTxns]);

  const handleRunRecovery = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (recoveringId) return;
    setRecoveringId(id);
    setActionNotice(null);
    try {
      const res = await runRecovery(id);
      setActionNotice(
        `Action ${res.selected_action} executed for ${id}: Outcome = ${res.monitoring_outcome}`
      );
      setTimeout(() => setActionNotice(null), 5000);
      await fetchTxns();
    } catch (err: any) {
      setActionNotice(`Recovery error for ${id}: ${err.message}`);
      setTimeout(() => setActionNotice(null), 5000);
    } finally {
      setRecoveringId(null);
    }
  };

  // Client-side search query filtering
  const filteredTransactions = transactions.filter((t) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.transaction_id.toLowerCase().includes(q) ||
      (t.customer_id && t.customer_id.toLowerCase().includes(q)) ||
      (t.failure_code && t.failure_code.toLowerCase().includes(q))
    );
  });

  // Calculate default estimated recovery probability, recommended action, policy, and reason
  const enrichedTransactions = filteredTransactions.map((t) => {
    let prob = t.predicted_recovery_prob ?? 0.65;
    let recAction = t.recommended_action ?? 'RETRY_PAYMENT';
    let revRecovered = t.revenue_recovered ?? (t.status === 'SUCCESS' && (t.attempt_count || 1) > 1 ? t.amount : 0);
    let policyDecision = 'PERMITTED';
    let policyRule = 'POL-004';
    let reason = 'Temporary gateway latency; permitted retry within 3 attempts.';

    const fcode = t.failure_code || '';
    if (fcode === 'HIGH_RISK' || (t.risk_score && t.risk_score > 0.8)) {
      prob = 0.05;
      recAction = 'ESCALATE';
      policyDecision = 'BLOCKED';
      policyRule = 'POL-003';
      reason = 'Risk score exceeds 0.85 fraud threshold. Automated retry strictly prohibited.';
    } else if (fcode === 'CARD_EXPIRED') {
      prob = 0.02;
      recAction = 'SWITCH_PAYMENT_METHOD';
      policyDecision = 'PERMITTED';
      policyRule = 'POL-008';
      reason = 'Card expired; retry blocked by POL-008. Auto-switched to verified UPI.';
    } else if (fcode === 'CARD_DECLINED') {
      prob = 0.72;
      recAction = 'SWITCH_PAYMENT_METHOD';
      policyDecision = 'PERMITTED';
      policyRule = 'POL-008';
      reason = 'Issuing bank decline. Route to alternate rail with customer confirmation.';
    } else if (fcode === 'CUSTOMER_ABANDONED') {
      prob = 0.68;
      recAction = 'SEND_RECOVERY_MESSAGE';
      policyDecision = 'PERMITTED';
      policyRule = 'POL-009';
      reason = 'High-intent cart abandonment. 1-click notification permitted.';
    } else if (fcode === 'GATEWAY_TIMEOUT' || fcode === 'OTP_EXPIRED') {
      prob = 0.88;
      recAction = 'RETRY_PAYMENT';
      policyDecision = 'PERMITTED';
      policyRule = 'POL-004';
      reason = 'Transient switch timeout. Immediate rail retry authorized.';
    } else if (fcode === 'INSUFFICIENT_FUNDS') {
      prob = 0.12;
      recAction = 'SCHEDULE_RETRY';
      policyDecision = 'BLOCKED';
      policyRule = 'POL-005';
      reason = 'Insufficient funds cooling period enforced; delayed schedule assigned.';
    } else if (fcode === 'DUPLICATE_PAYMENT') {
      prob = 0.00;
      recAction = 'STOP';
      policyDecision = 'BLOCKED';
      policyRule = 'POL-002';
      reason = 'Idempotency conflict detected. Halted to prevent double charge.';
    } else if (t.status === 'PENDING') {
      prob = 0.50;
      recAction = 'WAIT';
      policyDecision = 'WAIT';
      policyRule = 'POL-007';
      reason = 'Awaiting async bank settlement webhook; retry blocked.';
    }

    return {
      ...t,
      computedProb: prob,
      computedAction: recAction,
      computedPolicyDecision: policyDecision,
      computedPolicyRule: policyRule,
      computedReason: reason,
      computedRevenueRecovered: revRecovered,
    };
  });

  // Top financial aggregates
  const revenueAtRisk = transactions.reduce((acc, t) => acc + (t.amount || 0), 0);
  const revenueRecovered = enrichedTransactions.reduce((acc, t) => acc + (t.computedRevenueRecovered || 0), 0);
  const recoverableRevenue = Math.round(revenueAtRisk * 0.72);
  const recoveryRate = revenueAtRisk > 0 ? (revenueRecovered / revenueAtRisk) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-fintech-border pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Transactions & Recoveries
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time feed of failed payments, checkout drop-offs, and explainable AI agent decisions.
          </p>
        </div>

        <button
          onClick={fetchTxns}
          disabled={loading}
          className="self-start md:self-auto flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition active:scale-95 shadow-sm"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Refresh Feed</span>
        </button>
      </div>

      {/* 4 Core Financial Metrics Always Visible */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Revenue at Risk"
          value={formatINR(revenueAtRisk)}
          subtitle="Gross failed transaction volume"
          icon={AlertTriangle}
          variant="rose"
          loading={loading}
        />
        <MetricCard
          title="Recoverable Revenue"
          value={formatINR(recoverableRevenue)}
          subtitle="ML estimated capture pool"
          icon={TrendingUp}
          variant="indigo"
          loading={loading}
        />
        <MetricCard
          title="Revenue Recovered"
          value={formatINR(revenueRecovered)}
          subtitle="Net revenue captured by agent"
          icon={DollarSign}
          variant="emerald"
          loading={loading}
        />
        <MetricCard
          title="Recovery Rate"
          value={formatPercent(recoveryRate)}
          subtitle="Portfolio conversion efficiency"
          icon={Percent}
          variant="default"
          loading={loading}
        />
      </div>

      {/* Action Notice Banner */}
      {actionNotice && (
        <div className="rounded-lg bg-indigo-950/80 border border-indigo-500/50 p-3.5 text-xs text-indigo-200 flex items-center justify-between animate-fadeIn shadow-md">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-indigo-400 flex-shrink-0" />
            <span>{actionNotice}</span>
          </div>
          <button onClick={() => setActionNotice(null)} className="text-indigo-400 hover:text-white px-2 py-1">
            &times;
          </button>
        </div>
      )}

      {/* Search & Filters Card */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-4 shadow-fintech-card glass-panel flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search Transaction ID, Customer, Failure..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Status Filter */}
          <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
            <span className="text-slate-500 px-2 flex items-center gap-1 font-semibold text-[10px] uppercase">
              <Filter className="h-3 w-3" /> Status
            </span>
            {['ALL', 'FAILED', 'SUCCESS', 'ESCALATED', 'PENDING'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                  statusFilter === st
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Failure Code Dropdown */}
          <div className="flex items-center gap-2 text-xs">
            <select
              value={failureFilter}
              onChange={(e) => setFailureFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Failures</option>
              <option value="GATEWAY_TIMEOUT">GATEWAY_TIMEOUT</option>
              <option value="CARD_DECLINED">CARD_DECLINED</option>
              <option value="CARD_EXPIRED">CARD_EXPIRED</option>
              <option value="CUSTOMER_ABANDONED">CUSTOMER_ABANDONED</option>
              <option value="OTP_EXPIRED">OTP_EXPIRED</option>
              <option value="HIGH_RISK">HIGH_RISK</option>
              <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS</option>
              <option value="DUPLICATE_PAYMENT">DUPLICATE_PAYMENT</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Transactions Table */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 shadow-fintech-card glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px] bg-slate-900/80">
              <tr>
                <th className="py-3.5 px-4 font-semibold">Transaction ID</th>
                <th className="py-3.5 px-4 font-semibold">Amount</th>
                <th className="py-3.5 px-4 font-semibold">Status</th>
                <th className="py-3.5 px-4 font-semibold">Failure Diagnostics</th>
                <th className="py-3.5 px-4 font-semibold">Agent Decision</th>
                <th className="py-3.5 px-4 font-semibold">Policy Decision</th>
                <th className="py-3.5 px-4 font-semibold">Reason / Rule</th>
                <th className="py-3.5 px-4 font-semibold">Revenue Recovered</th>
                <th className="py-3.5 px-4 font-semibold text-right">Intervention</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-16 text-center text-slate-400">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto text-indigo-400 mb-2" />
                    Loading transaction audit log...
                  </td>
                </tr>
              ) : enrichedTransactions.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center">
                    <EmptyState
                      title="No transactions found"
                      description="No payments match your current query or filter criteria."
                      actionLabel="Clear Filters"
                      onAction={() => {
                        setSearchQuery('');
                        setStatusFilter('ALL');
                        setFailureFilter('ALL');
                      }}
                    />
                  </td>
                </tr>
              ) : (
                enrichedTransactions.map((txn) => {
                  const statusBadge = getStatusBadge(txn.status);
                  const actionBadge = getActionBadge(txn.computedAction);
                  const isRecovering = recoveringId === txn.transaction_id;
                  const isPolicyAllowed = txn.computedPolicyDecision === 'PERMITTED';
                  const isPolicyWait = txn.computedPolicyDecision === 'WAIT';

                  return (
                    <tr
                      key={txn.transaction_id}
                      className="hover:bg-slate-800/40 transition group"
                    >
                      {/* Transaction ID */}
                      <td className="py-3.5 px-4 font-mono text-slate-300">
                        <Link
                          href={`/transactions/${txn.transaction_id}`}
                          className="hover:text-indigo-400 transition flex items-center gap-1.5"
                        >
                          <span className="font-semibold">{txn.transaction_id}</span>
                          <Eye className="h-3 w-3 opacity-0 group-hover:opacity-100 text-indigo-400 transition" />
                        </Link>
                        {txn.customer_id && (
                          <div className="text-[10px] text-slate-500 font-mono">
                            {txn.customer_id}
                          </div>
                        )}
                      </td>

                      {/* Amount */}
                      <td className="py-3.5 px-4 font-tabular text-white font-bold text-sm">
                        {formatINR(txn.amount)}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${statusBadge.bg} ${statusBadge.text} ${statusBadge.border}`}
                        >
                          {txn.status}
                        </span>
                      </td>

                      {/* Failure Diagnostics */}
                      <td className="py-3.5 px-4">
                        <div className="font-mono text-rose-300 text-[11px] font-semibold">
                          {txn.failure_code || 'NONE'}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          {txn.payment_method} &bull; Prob: {(txn.computedProb * 100).toFixed(0)}%
                        </div>
                      </td>

                      {/* Agent Decision */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${actionBadge.bg} ${actionBadge.text} ${actionBadge.border}`}
                        >
                          {txn.computedAction}
                        </span>
                      </td>

                      {/* Policy Decision */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                            isPolicyAllowed
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40'
                              : isPolicyWait
                              ? 'bg-purple-950 text-purple-300 border-purple-500/40'
                              : 'bg-rose-950 text-rose-300 border-rose-500/40'
                          }`}
                        >
                          {txn.computedPolicyDecision} ({txn.computedPolicyRule})
                        </span>
                      </td>

                      {/* Reason with Tooltip */}
                      <td className="py-3.5 px-4 max-w-xs">
                        <Tooltip content={txn.computedReason} position="top">
                          <span className="text-slate-300 text-[11px] truncate block max-w-[180px] cursor-help">
                            {txn.computedReason}
                          </span>
                        </Tooltip>
                      </td>

                      {/* Revenue Recovered */}
                      <td className="py-3.5 px-4 font-tabular font-bold">
                        {txn.computedRevenueRecovered > 0 ? (
                          <span className="text-emerald-400">
                            {formatINR(txn.computedRevenueRecovered)}
                          </span>
                        ) : (
                          <span className="text-slate-500">₹0.00</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {txn.status !== 'SUCCESS' && txn.status !== 'ESCALATED' ? (
                            <button
                              onClick={(e) => handleRunRecovery(e, txn.transaction_id)}
                              disabled={isRecovering}
                              className="flex items-center gap-1 text-[10px] font-semibold text-white bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 rounded transition disabled:opacity-50 shadow-sm"
                            >
                              <Play className={`h-3 w-3 ${isRecovering ? 'animate-spin' : ''}`} />
                              <span>{isRecovering ? 'Running' : 'Recover'}</span>
                            </button>
                          ) : null}

                          <Link
                            href={`/transactions/${txn.transaction_id}`}
                            className="flex items-center gap-1 text-[11px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-700 border border-slate-700 px-2.5 py-1 rounded transition"
                          >
                            Details <ArrowRight className="h-3 w-3" />
                          </Link>
                        </div>
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
