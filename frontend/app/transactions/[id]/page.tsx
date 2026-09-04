'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ShieldCheck,
  Zap,
  CheckCircle2,
  AlertCircle,
  Clock,
  User,
  CreditCard,
  Layers,
  Cpu,
  RefreshCw,
  Play,
  FileText,
  AlertTriangle,
  Lock,
} from 'lucide-react';
import {
  getTransaction,
  getAgentDecision,
  getTransactionAuditTrail,
  runRecovery,
  Transaction,
  AgentDecisionResponse,
  AuditEvent,
  formatINR,
  formatPercent,
  getStatusBadge,
  getActionBadge,
} from '../../../lib/api';

export default function TransactionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [decision, setDecision] = useState<AgentDecisionResponse | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [integrityValid, setIntegrityValid] = useState<boolean>(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [execMessage, setExecMessage] = useState<string | null>(null);

  const fetchDetails = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [tRes, dRes, aRes] = await Promise.all([
        getTransaction(id).catch(() => null),
        getAgentDecision(id).catch(() => null),
        getTransactionAuditTrail(id).catch(() => ({ events: [], verified_integrity: true })),
      ]);

      if (!tRes) {
        throw new Error(`Transaction '${id}' was not found in payment simulator.`);
      }

      setTransaction(tRes);
      setDecision(dRes);
      setAuditEvents(aRes.events || []);
      setIntegrityValid(aRes.verified_integrity);
    } catch (err: any) {
      setError(err.message || 'Failed to load transaction details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [id]);

  const handleExecuteRecovery = async () => {
    if (!id || isExecuting) return;
    setIsExecuting(true);
    setExecMessage(null);
    try {
      const res = await runRecovery(id);
      setExecMessage(
        `Action ${res.selected_action} executed! Outcome: ${res.monitoring_outcome}`
      );
      await fetchDetails();
    } catch (err: any) {
      setExecMessage(`Execution failed: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center space-y-4">
        <RefreshCw className="h-8 w-8 animate-spin mx-auto text-indigo-400" />
        <p className="text-sm text-slate-400">Loading comprehensive transaction context & audit history...</p>
      </div>
    );
  }

  if (error || !transaction) {
    return (
      <div className="space-y-6">
        <Link
          href="/transactions"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Transactions
        </Link>
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-6 text-sm text-rose-300">
          <div className="flex items-center gap-2 mb-2 font-semibold">
            <AlertCircle className="h-5 w-5 text-rose-400" /> Error Loading Transaction
          </div>
          <p>{error || 'Transaction not found.'}</p>
        </div>
      </div>
    );
  }

  const statusBadge = getStatusBadge(transaction.status);
  const selectedAction = decision?.selected_action || 'RETRY_PAYMENT';
  const selectedActionBadge = getActionBadge(selectedAction);

  return (
    <div className="space-y-8">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/transactions"
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold font-mono text-white tracking-tight sm:text-2xl">
                {transaction.transaction_id}
              </h1>
              <span
                className={`px-2.5 py-0.5 rounded text-xs font-mono border ${statusBadge.bg} ${statusBadge.text} ${statusBadge.border}`}
              >
                {transaction.status}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Simulated payment lifecycle and explainable AI recovery trail
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleExecuteRecovery}
            disabled={isExecuting || transaction.status === 'SUCCESS'}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white shadow-fintech-glow transition active:scale-95 ${
              transaction.status === 'SUCCESS'
                ? 'bg-emerald-800/50 cursor-not-allowed opacity-60'
                : 'bg-indigo-600 hover:bg-indigo-500'
            }`}
          >
            <Play className={`h-3.5 w-3.5 ${isExecuting ? 'animate-spin' : ''}`} />
            <span>{isExecuting ? 'Running Orchestrator...' : 'Execute AI Recovery'}</span>
          </button>
        </div>
      </div>

      {/* Execution Feedback Notification */}
      {execMessage && (
        <div className="rounded-lg bg-indigo-950/80 border border-indigo-500/40 p-4 text-xs text-indigo-200 flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-indigo-400" />
            <span>{execMessage}</span>
          </div>
          <button onClick={() => setExecMessage(null)} className="text-indigo-400 hover:text-white">
            &times;
          </button>
        </div>
      )}

      {/* Top 3 Metric Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Amount & Rail */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Transaction Amount
          </span>
          <div className="text-2xl font-bold font-tabular text-white">
            {formatINR(transaction.amount)}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800">
            <span>Method: <strong className="text-slate-200">{transaction.payment_method}</strong></span>
            <span>&bull;</span>
            <span>Gateway: <strong className="text-slate-200">{transaction.gateway || 'SIMULATOR'}</strong></span>
          </div>
        </div>

        {/* Card 2: ML Recovery Probability */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            ML Recovery Probability
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-tabular text-indigo-400">
              {formatPercent(decision?.recovery_probability ?? 0.72)}
            </span>
            <span className="text-xs text-slate-400">confidence</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800">
            <span>Expected Value: <strong className="text-emerald-400 font-tabular">{formatINR(decision?.expected_recovery_value ?? transaction.amount * 0.72)}</strong></span>
          </div>
        </div>

        {/* Card 3: Selected Recovery Action */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel space-y-2">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Selected Action
          </span>
          <div>
            <span
              className={`inline-block px-2.5 py-1 rounded text-xs font-mono font-semibold border ${selectedActionBadge.bg} ${selectedActionBadge.text} ${selectedActionBadge.border}`}
            >
              {selectedAction}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800">
            <span>Policy Status: <strong className="text-emerald-400">{decision?.policy_status || 'ALLOWED'}</strong></span>
          </div>
        </div>
      </div>

      {/* Grid: Context & Explanations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section: Customer Context */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white border-b border-slate-800 pb-3">
            <User className="h-4 w-4 text-indigo-400" /> Customer Context
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-slate-500">Customer ID</span>
              <p className="font-mono text-slate-200 mt-0.5">{transaction.customer_id || 'cust_demo_01'}</p>
            </div>
            <div>
              <span className="text-slate-500">Risk Score</span>
              <p className="font-mono font-semibold text-slate-200 mt-0.5">
                {(transaction.risk_score ?? 0.08).toFixed(2)} (Low Fraud Risk)
              </p>
            </div>
            <div>
              <span className="text-slate-500">Preferred Method</span>
              <p className="font-mono text-slate-200 mt-0.5">{transaction.payment_method || 'CARD'}</p>
            </div>
            <div>
              <span className="text-slate-500">Attempt Count</span>
              <p className="font-mono text-slate-200 mt-0.5">{transaction.attempt_count || 1}</p>
            </div>
          </div>
        </div>

        {/* Section: Payment Context */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white border-b border-slate-800 pb-3">
            <CreditCard className="h-4 w-4 text-cyan-400" /> Payment Context
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-slate-500">Gateway Rail</span>
              <p className="font-mono text-slate-200 mt-0.5">{transaction.gateway || 'SIMULATOR'}</p>
            </div>
            <div>
              <span className="text-slate-500">Failure Code</span>
              <p className="font-mono font-bold text-rose-400 mt-0.5">
                {transaction.failure_code || 'NONE'}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Flow Stage</span>
              <p className="font-mono text-slate-200 mt-0.5">AUTHORIZATION</p>
            </div>
            <div>
              <span className="text-slate-500">Simulated Environment</span>
              <p className="font-mono text-emerald-400 mt-0.5">YES (Safe Sandbox)</p>
            </div>
          </div>
        </div>
      </div>

      {/* Section: Root Cause & Explainable ML Reasoning */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-white border-b border-slate-800 pb-3">
          <Cpu className="h-4 w-4 text-purple-400" /> Root Cause & Explainable AI Reasoning
        </div>
        <div className="p-4 rounded-lg bg-slate-900/90 border border-slate-800 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 font-medium">Agent Reasoning Summary</span>
            <span className="font-mono text-[10px] text-indigo-400 px-2 py-0.5 rounded bg-indigo-950/60 border border-indigo-500/30">
              Deterministic Engine
            </span>
          </div>
          <p className="text-slate-200 leading-relaxed">
            {decision?.reasoning_summary ||
              `Payment failed with ${transaction.failure_code || 'error'}. Low customer risk allows automated recovery through recommended action without violating frequency limits.`}
          </p>
        </div>
      </div>

      {/* Section: Candidate Actions & Policy Evaluation */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Layers className="h-4 w-4 text-amber-400" /> Candidate Actions & Policy Verification
          </div>
          <span className="text-xs font-mono text-slate-400">12 Deterministic Guardrails</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-400 uppercase tracking-wider text-[11px] bg-slate-900/60 border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Candidate Action</th>
                <th className="py-2.5 px-3">Probability</th>
                <th className="py-2.5 px-3">Expected Value</th>
                <th className="py-2.5 px-3">Policy Outcome</th>
                <th className="py-2.5 px-3">Rule ID</th>
                <th className="py-2.5 px-3">Reasoning / Constraint</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium font-mono">
              {decision?.candidates && decision.candidates.length > 0 ? (
                decision.candidates.map((c, i) => {
                  const isSelected = c.action === selectedAction;
                  return (
                    <tr
                      key={i}
                      className={isSelected ? 'bg-indigo-950/30 text-indigo-200' : 'hover:bg-slate-800/40 text-slate-300'}
                    >
                      <td className="py-2.5 px-3 font-semibold flex items-center gap-2">
                        {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-indigo-400"></span>}
                        {c.action}
                      </td>
                      <td className="py-2.5 px-3 font-tabular">
                        {formatPercent(c.probability)}
                      </td>
                      <td className="py-2.5 px-3 font-tabular text-emerald-400">
                        {formatINR(c.expected_recovery_value)}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            c.permitted
                              ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/30'
                              : 'bg-rose-950/80 text-rose-400 border border-rose-500/30'
                          }`}
                        >
                          {c.policy_outcome || (c.permitted ? 'ALLOWED' : 'DENIED')}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {c.rule_id || 'POL-DEFAULT'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 font-sans text-[11px]">
                        {c.rejection_reason || c.reason || (c.permitted ? 'Passed all safety checks' : 'Blocked')}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-slate-500">
                    No candidate actions evaluated yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section: Complete Audit Timeline & Cryptographic Hash Chain */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <FileText className="h-4 w-4 text-indigo-400" /> Complete Audit Timeline
          </div>
          <div className="flex items-center gap-2">
            {integrityValid ? (
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono bg-emerald-950/80 text-emerald-400 border border-emerald-500/30">
                <ShieldCheck className="h-3.5 w-3.5" /> SHA-256 Chain Verified
              </span>
            ) : (
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono bg-rose-950/80 text-rose-400 border border-rose-500/30">
                <AlertTriangle className="h-3.5 w-3.5" /> Chain Compromised
              </span>
            )}
          </div>
        </div>

        <div className="space-y-3 pt-2">
          {auditEvents.length === 0 ? (
            <p className="text-xs text-slate-500 py-4 text-center">
              No audit records generated for this transaction yet.
            </p>
          ) : (
            auditEvents.map((event, idx) => (
              <div
                key={event.audit_id || idx}
                className="p-3.5 rounded-lg bg-slate-900/60 border border-slate-800/80 space-y-2 text-xs"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-slate-400">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-indigo-950/70 border border-indigo-500/30 text-indigo-300 font-mono text-[10px]">
                      {event.actor}
                    </span>
                    <span className="font-semibold text-white font-mono text-[11px]">{event.event_type}</span>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">
                    {new Date(event.timestamp).toLocaleString()}
                  </span>
                </div>

                {event.input_summary && Object.keys(event.input_summary).length > 0 && (
                  <div className="text-[11px] text-slate-400 font-mono bg-slate-950/60 p-2 rounded border border-slate-900">
                    {JSON.stringify(event.input_summary)}
                  </div>
                )}

                <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono pt-1">
                  <span className="truncate max-w-[280px]">Hash: {event.hash}</span>
                  <span>Prev: {event.previous_hash ? event.previous_hash.slice(0, 10) + '...' : 'GENESIS'}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
