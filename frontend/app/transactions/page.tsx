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

  const fetchTxns = async () => {
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
  };

  useEffect(() => {
    fetchTxns();
  }, [statusFilter, failureFilter]);

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

  // Calculate default estimated recovery probability and recommended action if not attached
  const enrichedTransactions = filteredTransactions.map((t) => {
    let prob = t.predicted_recovery_prob ?? 0.65;
    let recAction = t.recommended_action ?? 'RETRY_PAYMENT';
    let revRecovered = t.revenue_recovered ?? (t.status === 'SUCCESS' && (t.attempt_count || 1) > 1 ? t.amount : 0);

    const fcode = t.failure_code || '';
    if (fcode === 'HIGH_RISK' || fcode === 'DUPLICATE_ORDER') {
      prob = 0.05;
      recAction = 'ESCALATE';
    } else if (fcode === 'CARD_DECLINED') {
      prob = 0.72;
      recAction = 'SWITCH_PAYMENT_METHOD';
    } else if (fcode === 'CUSTOMER_ABANDONED') {
      prob = 0.54;
      recAction = 'SEND_RECOVERY_LINK';
    } else if (fcode === 'GATEWAY_TIMEOUT' || fcode === 'OTP_EXPIRED') {
      prob = 0.88;
      recAction = 'RETRY_PAYMENT';
    } else if (fcode === 'INSUFFICIENT_FUNDS') {
      prob = 0.45;
      recAction = 'OFFER_INCENTIVE';
    }

    return {
      ...t,
      computedProb: prob,
      computedAction: recAction,
      computedRevenueRecovered: revRecovered,
    };
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Transactions & Recoveries
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time feed of failed payments, checkout drop-offs, and agent decisions.
          </p>
        </div>

        <button
          onClick={fetchTxns}
          disabled={loading}
          className="self-start md:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Action Notice Banner */}
      {actionNotice && (
        <div className="rounded-lg bg-indigo-950/80 border border-indigo-500/50 p-3 text-xs text-indigo-200 flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-indigo-400" />
            <span>{actionNotice}</span>
          </div>
          <button onClick={() => setActionNotice(null)} className="text-indigo-400 hover:text-white">
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
            placeholder="Search Transaction ID, Customer..."
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
            {['ALL', 'FAILED', 'SUCCESS', 'ESCALATED'].map((st) => (
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
              <option value="BANK_UNAVAILABLE">BANK_UNAVAILABLE</option>
              <option value="CUSTOMER_ABANDONED">CUSTOMER_ABANDONED</option>
              <option value="OTP_EXPIRED">OTP_EXPIRED</option>
              <option value="HIGH_RISK">HIGH_RISK</option>
              <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Transactions Table */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 shadow-fintech-card glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px] bg-slate-900/60">
              <tr>
                <th className="py-3.5 px-4 font-semibold">Transaction ID</th>
                <th className="py-3.5 px-4 font-semibold">Amount</th>
                <th className="py-3.5 px-4 font-semibold">Status</th>
                <th className="py-3.5 px-4 font-semibold">Failure</th>
                <th className="py-3.5 px-4 font-semibold">Recovery Probability</th>
                <th className="py-3.5 px-4 font-semibold">Recommended Action</th>
                <th className="py-3.5 px-4 font-semibold">Revenue Recovered</th>
                <th className="py-3.5 px-4 font-semibold text-right">Intervention</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto text-indigo-400 mb-2" />
                    Loading simulated transactions from engine...
                  </td>
                </tr>
              ) : enrichedTransactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <AlertTriangle className="h-6 w-6 text-amber-500 mx-auto mb-2" />
                    No transactions match the selected criteria.
                  </td>
                </tr>
              ) : (
                enrichedTransactions.map((txn) => {
                  const statusBadge = getStatusBadge(txn.status);
                  const actionBadge = getActionBadge(txn.computedAction);
                  const isRecovering = recoveringId === txn.transaction_id;

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
                          <span>{txn.transaction_id}</span>
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
                          className={`px-2.5 py-0.5 rounded text-[10px] font-mono border ${statusBadge.bg} ${statusBadge.text} ${statusBadge.border}`}
                        >
                          {txn.status}
                        </span>
                      </td>

                      {/* Failure */}
                      <td className="py-3.5 px-4">
                        <div className="font-mono text-slate-300 text-[11px]">
                          {txn.failure_code || 'NONE'}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">
                          {txn.payment_method}
                        </div>
                      </td>

                      {/* Recovery Probability */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                txn.computedProb >= 0.7
                                  ? 'bg-emerald-400'
                                  : txn.computedProb >= 0.4
                                  ? 'bg-amber-400'
                                  : 'bg-rose-400'
                              }`}
                              style={{ width: `${txn.computedProb * 100}%` }}
                            ></div>
                          </div>
                          <span className="font-tabular font-mono text-xs text-slate-300">
                            {formatPercent(txn.computedProb)}
                          </span>
                        </div>
                      </td>

                      {/* Recommended Action */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono border ${actionBadge.bg} ${actionBadge.text} ${actionBadge.border}`}
                        >
                          {txn.computedAction}
                        </span>
                      </td>

                      {/* Revenue Recovered */}
                      <td className="py-3.5 px-4 font-tabular">
                        {txn.computedRevenueRecovered > 0 ? (
                          <span className="text-emerald-400 font-bold">
                            {formatINR(txn.computedRevenueRecovered)}
                          </span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {txn.status !== 'SUCCESS' && txn.status !== 'ESCALATED' ? (
                            <button
                              onClick={(e) => handleRunRecovery(e, txn.transaction_id)}
                              disabled={isRecovering}
                              className="flex items-center gap-1 text-[10px] font-semibold text-white bg-indigo-600 hover:bg-indigo-500 px-2 py-1 rounded transition disabled:opacity-50"
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

        {/* Footer Summary */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800/80 bg-slate-900/40 text-xs text-slate-400 font-mono">
          <span>Showing {enrichedTransactions.length} of {total} transactions</span>
          <span>Environment: SIMULATED_GATEWAY</span>
        </div>
      </div>
    </div>
  );
}
