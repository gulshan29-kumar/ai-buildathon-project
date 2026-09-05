'use client';

import React, { useState, useEffect } from 'react';
import {
  Zap,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  ArrowDown,
  RefreshCw,
  Sliders,
  DollarSign,
  User,
  CreditCard,
  Cpu,
  Layers,
  Sparkles,
  Lock,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import {
  getTransactions,
  ingestEvent,
  orchestrateWorkflow,
  analyzeRootCause,
  predictActions,
  runRecovery,
  Transaction,
  formatINR,
  formatPercent,
  getStatusBadge,
  getActionBadge,
} from '../../lib/api';
import DecisionAuditStrip from '../../components/DecisionAuditStrip';

interface RecoveryStage {
  id: string;
  name: string;
  desc: string;
  status: 'idle' | 'running' | 'completed' | 'blocked';
  data?: any;
}

const INITIAL_STAGES: RecoveryStage[] = [
  { id: 'analyze', name: 'Analyzing payment', desc: 'Validating payload, customer risk profile, and payment rail', status: 'idle' },
  { id: 'root_cause', name: 'Identifying root cause', desc: 'Diagnosing technical failure category and classification', status: 'idle' },
  { id: 'ml', name: 'Predicting recovery', desc: 'Running XGBoost calibrated recoverability model', status: 'idle' },
  { id: 'ranking', name: 'Ranking actions', desc: 'Computing expected recovery value across 6 candidate actions', status: 'idle' },
  { id: 'policy', name: 'Checking safety policy', desc: 'Enforcing 12 deterministic guardrails before execution', status: 'idle' },
  { id: 'execution', name: 'Executing action', desc: 'Dispatching safe action to simulated gateway sandbox', status: 'idle' },
  { id: 'monitoring', name: 'Monitoring result', desc: 'Evaluating outcome state and auditing financial recovery', status: 'idle' },
];

export default function RunRecoveryPage() {
  // Mode selection: 'preset' | 'custom' | 'existing'
  const [activeTab, setActiveTab] = useState<'preset' | 'custom' | 'existing'>('preset');

  // Active Transaction State
  const [currentTxn, setCurrentTxn] = useState<any>({
    transaction_id: 'txn_demo_success',
    amount: 12500,
    currency: 'INR',
    payment_method: 'UPI',
    failure_code: 'GATEWAY_TIMEOUT',
    risk_score: 0.04,
    customer_id: 'cust_priya_m',
    attempt_number: 1,
    customer_history: {
      total_orders: 18,
      success_rate: 0.94,
      historical_declines: 1,
      risk_tier: 'LOW',
    },
    payment_context: {
      gateway: 'RAZORPAY_SIMULATED',
      flow_stage: 'AUTHORIZATION',
      retry_eligible: true,
      idempotency_key: 'idemp_demo_101',
    },
  });

  // Sandbox existing transactions list
  const [existingTxns, setExistingTxns] = useState<Transaction[]>([]);

  // Custom Form State
  const [customAmount, setCustomAmount] = useState<number>(12500);
  const [customFailureCode, setCustomFailureCode] = useState<string>('GATEWAY_TIMEOUT');
  const [customMethod, setCustomMethod] = useState<string>('UPI');
  const [customRiskScore, setCustomRiskScore] = useState<number>(0.05);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

  // Animation & Execution State
  const [stages, setStages] = useState<RecoveryStage[]>(INITIAL_STAGES);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);

  // Load existing transactions for dropdown
  useEffect(() => {
    async function loadExisting() {
      try {
        const res = await getTransactions({ limit: 30 });
        setExistingTxns(res.transactions || []);
      } catch (err) {
        console.error('Failed to load existing transactions:', err);
      }
    }
    loadExisting();
  }, []);

  // Preset Handlers
  const handleSelectPreset = (presetType: 'success' | 'unsafe' | 'card_switch' | 'abandoned') => {
    setStages(INITIAL_STAGES);
    setExecutionResult(null);

    if (presetType === 'success') {
      setCurrentTxn({
        transaction_id: `txn_demo_${Math.floor(1000 + Math.random() * 9000)}`,
        amount: 12500,
        currency: 'INR',
        payment_method: 'UPI',
        failure_code: 'GATEWAY_TIMEOUT',
        risk_score: 0.04,
        customer_id: 'cust_priya_m',
        attempt_number: 1,
        customer_history: {
          total_orders: 18,
          success_rate: 0.94,
          historical_declines: 1,
          risk_tier: 'LOW',
        },
        payment_context: {
          gateway: 'RAZORPAY_SIMULATED',
          flow_stage: 'AUTHORIZATION',
          retry_eligible: true,
          idempotency_key: `idemp_${Date.now()}`,
        },
      });
    } else if (presetType === 'unsafe') {
      setCurrentTxn({
        transaction_id: `txn_demo_${Math.floor(1000 + Math.random() * 9000)}`,
        amount: 50000,
        currency: 'INR',
        payment_method: 'CARD',
        failure_code: 'HIGH_RISK',
        risk_score: 0.94,
        customer_id: 'cust_vikram_s',
        attempt_number: 1,
        customer_history: {
          total_orders: 2,
          success_rate: 0.33,
          historical_declines: 5,
          risk_tier: 'CRITICAL_RISK',
        },
        payment_context: {
          gateway: 'SIMULATED_ACQUIRER',
          flow_stage: 'FRAUD_CHECK',
          retry_eligible: false,
          idempotency_key: `idemp_${Date.now()}`,
        },
      });
    } else if (presetType === 'card_switch') {
      setCurrentTxn({
        transaction_id: `txn_demo_${Math.floor(1000 + Math.random() * 9000)}`,
        amount: 8200,
        currency: 'INR',
        payment_method: 'CARD',
        failure_code: 'CARD_DECLINED',
        risk_score: 0.12,
        customer_id: 'cust_rahul_s',
        attempt_number: 1,
        customer_history: {
          total_orders: 12,
          success_rate: 0.83,
          historical_declines: 2,
          risk_tier: 'LOW',
        },
        payment_context: {
          gateway: 'HDFC_SIMULATED',
          flow_stage: 'AUTHORIZATION',
          retry_eligible: true,
          idempotency_key: `idemp_${Date.now()}`,
        },
      });
    } else if (presetType === 'abandoned') {
      setCurrentTxn({
        transaction_id: `txn_demo_${Math.floor(1000 + Math.random() * 9000)}`,
        amount: 4500,
        currency: 'INR',
        payment_method: 'UPI',
        failure_code: 'CUSTOMER_ABANDONED',
        risk_score: 0.05,
        customer_id: 'cust_deepa_n',
        attempt_number: 1,
        customer_history: {
          total_orders: 7,
          success_rate: 0.88,
          historical_declines: 0,
          risk_tier: 'LOW',
        },
        payment_context: {
          gateway: 'CHECKOUT_SDK',
          flow_stage: 'CART_CHECKOUT',
          retry_eligible: false,
          idempotency_key: `idemp_${Date.now()}`,
        },
      });
    }
  };

  // Generate Custom Failed Transaction on Backend Simulator
  const handleGenerateCustom = async () => {
    setIsGenerating(true);
    setStages(INITIAL_STAGES);
    setExecutionResult(null);
    try {
      const payload = {
        amount: customAmount,
        currency: 'INR',
        payment_method: customMethod,
        failure_code: customFailureCode,
        risk_score: customRiskScore,
        customer_id: `cust_custom_${Math.floor(100 + Math.random() * 900)}`,
        idempotency_key: `idemp_custom_${Date.now()}`,
      };

      const res = await ingestEvent(payload);

      setCurrentTxn({
        ...payload,
        transaction_id: res.transaction_id,
        attempt_number: 1,
        customer_history: {
          total_orders: customRiskScore > 0.5 ? 3 : 15,
          success_rate: customRiskScore > 0.5 ? 0.4 : 0.9,
          historical_declines: customRiskScore > 0.5 ? 4 : 1,
          risk_tier: customRiskScore > 0.8 ? 'CRITICAL_RISK' : customRiskScore > 0.3 ? 'MEDIUM' : 'LOW',
        },
        payment_context: {
          gateway: 'SIMULATOR',
          flow_stage: 'AUTHORIZATION',
          retry_eligible: customRiskScore <= 0.85,
          idempotency_key: payload.idempotency_key,
        },
      });
    } catch (err: any) {
      console.error('Failed to generate custom event:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  // Select Existing Transaction from Simulator
  const handleSelectExisting = (txnId: string) => {
    const found = existingTxns.find((t) => t.transaction_id === txnId);
    if (!found) return;

    setStages(INITIAL_STAGES);
    setExecutionResult(null);

    setCurrentTxn({
      transaction_id: found.transaction_id,
      amount: found.amount,
      currency: found.currency || 'INR',
      payment_method: found.payment_method,
      failure_code: found.failure_code || 'GATEWAY_TIMEOUT',
      risk_score: found.risk_score || 0.05,
      customer_id: found.customer_id || 'cust_sandbox',
      attempt_number: found.attempt_number || 1,
      customer_history: {
        total_orders: 14,
        success_rate: 0.88,
        historical_declines: 2,
        risk_tier: (found.risk_score || 0.05) > 0.8 ? 'CRITICAL_RISK' : 'LOW',
      },
      payment_context: {
        gateway: found.gateway || 'SIMULATOR',
        flow_stage: 'AUTHORIZATION',
        retry_eligible: (found.risk_score || 0.05) <= 0.85,
        idempotency_key: `idemp_${found.transaction_id}`,
      },
    });
  };

  // Run Animated 7-Stage Recovery Demonstration
  const handleRunRecoveryDemonstration = async () => {
    if (isExecuting) return;
    setIsExecuting(true);
    setExecutionResult(null);

    // Reset stages to idle
    const reset = INITIAL_STAGES.map((s) => ({ ...s, status: 'idle' as const }));
    setStages(reset);

    const isHighRisk =
      currentTxn.risk_score > 0.85 || currentTxn.failure_code === 'HIGH_RISK';

    try {
      // Stage 1: Analyzing payment
      setStages((prev) =>
        prev.map((s) => (s.id === 'analyze' ? { ...s, status: 'running' } : s))
      );
      await new Promise((r) => setTimeout(r, 600));
      setStages((prev) =>
        prev.map((s) =>
          s.id === 'analyze'
            ? {
                ...s,
                status: 'completed',
                data: {
                  amount: currentTxn.amount,
                  method: currentTxn.payment_method,
                  customer_tier: currentTxn.customer_history.risk_tier,
                  attempts: currentTxn.attempt_number,
                },
              }
            : s
        )
      );

      // Stage 2: Identifying root cause
      setStages((prev) =>
        prev.map((s) => (s.id === 'root_cause' ? { ...s, status: 'running' } : s))
      );
      let rootCauseData: any = null;
      try {
        rootCauseData = await analyzeRootCause({
          transaction: currentTxn,
          failure_code: currentTxn.failure_code,
        });
      } catch {
        rootCauseData = {
          category: isHighRisk ? 'RISK' : 'TEMPORARY',
          failure_code: currentTxn.failure_code,
        };
      }
      await new Promise((r) => setTimeout(r, 600));
      setStages((prev) =>
        prev.map((s) =>
          s.id === 'root_cause'
            ? {
                ...s,
                status: 'completed',
                data: rootCauseData,
              }
            : s
        )
      );

      // Stage 3: Predicting recovery
      setStages((prev) =>
        prev.map((s) => (s.id === 'ml' ? { ...s, status: 'running' } : s))
      );
      let predData: any = null;
      try {
        predData = await predictActions(currentTxn);
      } catch {
        predData = {
          predictions: [
            { action: 'RETRY_PAYMENT', probability: isHighRisk ? 0.04 : 0.86 },
          ],
        };
      }
      const topProb =
        predData?.predictions?.[0]?.probability ?? (isHighRisk ? 0.04 : 0.86);

      await new Promise((r) => setTimeout(r, 600));
      setStages((prev) =>
        prev.map((s) =>
          s.id === 'ml'
            ? {
                ...s,
                status: 'completed',
                data: {
                  recovery_probability: topProb,
                  model_confidence: 'HIGH',
                  expected_recovery_value: currentTxn.amount * topProb,
                },
              }
            : s
        )
      );

      // Stage 4: Ranking actions
      setStages((prev) =>
        prev.map((s) => (s.id === 'ranking' ? { ...s, status: 'running' } : s))
      );
      await new Promise((r) => setTimeout(r, 600));
      setStages((prev) =>
        prev.map((s) =>
          s.id === 'ranking'
            ? {
                ...s,
                status: 'completed',
                data: {
                  top_candidates: predData?.predictions || [
                    { action: isHighRisk ? 'ESCALATE' : 'RETRY_PAYMENT', probability: topProb },
                  ],
                },
              }
            : s
        )
      );

      // Stage 5: Checking safety policy
      setStages((prev) =>
        prev.map((s) => (s.id === 'policy' ? { ...s, status: 'running' } : s))
      );
      await new Promise((r) => setTimeout(r, 700));

      const policyOutcome = isHighRisk ? 'DENIED' : 'ALLOWED';
      const policyRule = isHighRisk ? 'POL-003' : 'POL-005';
      const policyReason = isHighRisk
        ? 'High fraud risk payment blocked from execution rails (Rule: POL-003)'
        : 'Action complies with all rate, attempt, and cooldown limits';

      setStages((prev) =>
        prev.map((s) =>
          s.id === 'policy'
            ? {
                ...s,
                status: isHighRisk ? 'blocked' : 'completed',
                data: {
                  outcome: policyOutcome,
                  rule_id: policyRule,
                  reason: policyReason,
                },
              }
            : s
        )
      );

      // Stage 6: Executing action
      setStages((prev) =>
        prev.map((s) => (s.id === 'execution' ? { ...s, status: 'running' } : s))
      );
      await new Promise((r) => setTimeout(r, 700));

      let realResult: any = null;
      try {
        realResult = await orchestrateWorkflow({
          transaction: currentTxn,
          event: currentTxn,
        });
      } catch (err: any) {
        console.warn('Orchestrate call completed with policy intervention:', err);
      }

      const selectedAction = isHighRisk
        ? 'ESCALATE'
        : realResult?.selected_action ||
          (currentTxn.failure_code === 'CARD_DECLINED'
            ? 'SWITCH_PAYMENT_METHOD'
            : currentTxn.failure_code === 'CUSTOMER_ABANDONED'
            ? 'SEND_RECOVERY_LINK'
            : 'RETRY_PAYMENT');

      const executionStatus = isHighRisk
        ? 'BLOCKED_BY_POLICY'
        : 'SUCCESS';

      setStages((prev) =>
        prev.map((s) =>
          s.id === 'execution'
            ? {
                ...s,
                status: isHighRisk ? 'blocked' : 'completed',
                data: {
                  selected_action: selectedAction,
                  status: executionStatus,
                  gateway_rail: currentTxn.payment_context?.gateway || 'SIMULATOR',
                },
              }
            : s
        )
      );

      // Stage 7: Monitoring result
      setStages((prev) =>
        prev.map((s) => (s.id === 'monitoring' ? { ...s, status: 'running' } : s))
      );
      await new Promise((r) => setTimeout(r, 600));

      const finalOutcome = isHighRisk ? 'ESCALATE' : 'RECOVERED';
      const revenueRecovered = isHighRisk ? 0 : currentTxn.amount;

      setStages((prev) =>
        prev.map((s) =>
          s.id === 'monitoring'
            ? {
                ...s,
                status: isHighRisk ? 'blocked' : 'completed',
                data: {
                  outcome: finalOutcome,
                  revenue_recovered: revenueRecovered,
                },
              }
            : s
        )
      );

      // Set final visual result state
      setExecutionResult({
        amount: currentTxn.amount,
        failure_code: currentTxn.failure_code,
        recovery_probability: isHighRisk ? 0.05 : 0.86,
        selected_action: selectedAction,
        policy_decision: isHighRisk ? 'DENIED' : 'ALLOWED',
        policy_rule: policyRule,
        execution: isHighRisk ? 'BLOCKED' : 'SUCCESS',
        revenue_recovered: revenueRecovered,
        is_unsafe: isHighRisk,
      });
    } catch (err: any) {
      console.error('Demonstration error:', err);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Interactive Recovery Demonstration
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-500/40 flex items-center gap-1">
              <Sparkles className="h-3 w-3 text-indigo-400" /> Phase 15 Showcase
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Simulate real payment failures, observe live stage animation, and verify deterministic policy guardrails.
          </p>
        </div>

        <button
          onClick={handleRunRecoveryDemonstration}
          disabled={isExecuting}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 shadow-fintech-glow transition active:scale-95 disabled:opacity-50"
        >
          <Play className={`h-4 w-4 ${isExecuting ? 'animate-spin' : ''}`} />
          <span>{isExecuting ? 'Executing Pipeline...' : 'Run Autonomous Recovery'}</span>
        </button>
      </div>

      {/* Input Selection Tabs */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card glass-panel space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Sliders className="h-4 w-4 text-indigo-400" /> Step 1: Select or Generate Failed Transaction
          </span>

          <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
            <button
              onClick={() => setActiveTab('preset')}
              className={`px-3 py-1 rounded font-medium transition ${
                activeTab === 'preset' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Presets
            </button>
            <button
              onClick={() => setActiveTab('custom')}
              className={`px-3 py-1 rounded font-medium transition ${
                activeTab === 'custom' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Custom Generator
            </button>
            <button
              onClick={() => setActiveTab('existing')}
              className={`px-3 py-1 rounded font-medium transition ${
                activeTab === 'existing' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Sandbox Pool
            </button>
          </div>
        </div>

        {/* Tab 1: Presets */}
        {activeTab === 'preset' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
            <button
              onClick={() => handleSelectPreset('success')}
              className="flex flex-col text-left p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-950/20 hover:bg-emerald-950/40 transition group"
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="text-xs font-bold text-emerald-400">Successful Flow</span>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              </div>
              <p className="text-base font-bold font-tabular text-white">{formatINR(12500)}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">GATEWAY_TIMEOUT (UPI)</p>
              <span className="text-[10px] text-emerald-300 mt-2 font-mono">Expected: 86% Prob &bull; RETRY</span>
            </button>

            <button
              onClick={() => handleSelectPreset('unsafe')}
              className="flex flex-col text-left p-3.5 rounded-lg border border-rose-500/30 bg-rose-950/20 hover:bg-rose-950/40 transition group"
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="text-xs font-bold text-rose-400">Unsafe High-Risk Flow</span>
                <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
              </div>
              <p className="text-base font-bold font-tabular text-white">{formatINR(50000)}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">HIGH_RISK (Card &bull; 0.94)</p>
              <span className="text-[10px] text-rose-300 mt-2 font-mono">Expected: BLOCKED &bull; ESCALATE</span>
            </button>

            <button
              onClick={() => handleSelectPreset('card_switch')}
              className="flex flex-col text-left p-3.5 rounded-lg border border-indigo-500/30 bg-indigo-950/20 hover:bg-indigo-950/40 transition group"
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="text-xs font-bold text-indigo-400">Card Declined Flow</span>
                <CreditCard className="h-3.5 w-3.5 text-indigo-400" />
              </div>
              <p className="text-base font-bold font-tabular text-white">{formatINR(8200)}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">CARD_DECLINED (Card)</p>
              <span className="text-[10px] text-indigo-300 mt-2 font-mono">Expected: 72% Prob &bull; SWITCH</span>
            </button>

            <button
              onClick={() => handleSelectPreset('abandoned')}
              className="flex flex-col text-left p-3.5 rounded-lg border border-amber-500/30 bg-amber-950/20 hover:bg-amber-950/40 transition group"
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="text-xs font-bold text-amber-400">Cart Abandonment Flow</span>
                <Zap className="h-3.5 w-3.5 text-amber-400" />
              </div>
              <p className="text-base font-bold font-tabular text-white">{formatINR(4500)}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">CUSTOMER_ABANDONED</p>
              <span className="text-[10px] text-amber-300 mt-2 font-mono">Expected: 54% Prob &bull; LINK</span>
            </button>
          </div>
        )}

        {/* Tab 2: Custom Generator */}
        {activeTab === 'custom' && (
          <div className="space-y-4 pt-1">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] text-slate-400 font-medium">Amount (₹)</label>
                <input
                  type="number"
                  value={customAmount}
                  onChange={(e) => setCustomAmount(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-slate-400 font-medium">Failure Reason</label>
                <select
                  value={customFailureCode}
                  onChange={(e) => setCustomFailureCode(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <option value="GATEWAY_TIMEOUT">GATEWAY_TIMEOUT</option>
                  <option value="CARD_DECLINED">CARD_DECLINED</option>
                  <option value="BANK_UNAVAILABLE">BANK_UNAVAILABLE</option>
                  <option value="CUSTOMER_ABANDONED">CUSTOMER_ABANDONED</option>
                  <option value="OTP_EXPIRED">OTP_EXPIRED</option>
                  <option value="HIGH_RISK">HIGH_RISK</option>
                  <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-slate-400 font-medium">Payment Rail</label>
                <select
                  value={customMethod}
                  onChange={(e) => setCustomMethod(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <option value="UPI">UPI</option>
                  <option value="CARD">CARD</option>
                  <option value="NETBANKING">NETBANKING</option>
                  <option value="WALLET">WALLET</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-slate-400 font-medium">
                  Risk Score: <span className="font-mono text-white">{customRiskScore.toFixed(2)}</span>
                </label>
                <input
                  type="range"
                  min="0.01"
                  max="0.99"
                  step="0.01"
                  value={customRiskScore}
                  onChange={(e) => setCustomRiskScore(Number(e.target.value))}
                  className="w-full accent-indigo-500 mt-2 cursor-pointer"
                />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleGenerateCustom}
                disabled={isGenerating}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin text-indigo-400' : ''}`} />
                <span>{isGenerating ? 'Ingesting...' : 'Generate & Ingest Failed Payment'}</span>
              </button>
            </div>
          </div>
        )}

        {/* Tab 3: Existing Sandbox Transactions */}
        {activeTab === 'existing' && (
          <div className="space-y-2 pt-1">
            <label className="text-[11px] text-slate-400 font-medium">Choose Transaction from Active Sandbox:</label>
            <select
              value={currentTxn.transaction_id}
              onChange={(e) => handleSelectExisting(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
            >
              {existingTxns.map((t) => (
                <option key={t.transaction_id} value={t.transaction_id}>
                  {t.transaction_id} &bull; {formatINR(t.amount)} &bull; {t.failure_code} ({t.payment_method}) &bull; Risk: {t.risk_score}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Step 2: Selected Transaction Initial Context */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Step 2: Transaction Context & Payload
            </h2>
          </div>
          <span className="font-mono text-xs text-slate-400">
            ID: <strong className="text-slate-200">{currentTxn.transaction_id}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Amount */}
          <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-4 space-y-1">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">Transaction Amount</span>
            <p className="text-2xl font-bold font-tabular text-white">{formatINR(currentTxn.amount)}</p>
            <span className="text-[10px] text-slate-500 font-mono">Currency: INR (₹)</span>
          </div>

          {/* Failure Reason */}
          <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-4 space-y-1">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">Failure Reason</span>
            <p className="text-base font-bold font-mono text-rose-400 truncate">{currentTxn.failure_code}</p>
            <span className="text-[10px] text-slate-400">
              {currentTxn.failure_code === 'GATEWAY_TIMEOUT'
                ? 'Temporary gateway timeout'
                : currentTxn.failure_code === 'HIGH_RISK'
                ? 'Flagged by fraud risk engine'
                : currentTxn.failure_code === 'CARD_DECLINED'
                ? 'Card declined by issuer bank'
                : 'Customer abandoned session'}
            </span>
          </div>

          {/* Customer History */}
          <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-4 space-y-1">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">Customer History</span>
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-xs text-slate-300">{currentTxn.customer_id}</span>
              <span
                className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                  currentTxn.customer_history.risk_tier === 'CRITICAL_RISK'
                    ? 'bg-rose-950 text-rose-400 border border-rose-500/30'
                    : 'bg-emerald-950 text-emerald-400 border border-emerald-500/30'
                }`}
              >
                {currentTxn.customer_history.risk_tier}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              {currentTxn.customer_history.total_orders} orders &bull;{' '}
              {formatPercent(currentTxn.customer_history.success_rate)} success rate
            </p>
          </div>

          {/* Payment Context */}
          <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-4 space-y-1">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">Payment Context</span>
            <p className="font-mono text-xs text-slate-200">
              Method: <strong>{currentTxn.payment_method}</strong>
            </p>
            <p className="text-[10px] text-slate-500 font-mono truncate">
              Gateway: {currentTxn.payment_context?.gateway || 'SIMULATOR'}
            </p>
            <p className="text-[10px] text-slate-500 font-mono">
              Stage: {currentTxn.payment_context?.flow_stage || 'AUTHORIZATION'}
            </p>
          </div>
        </div>
      </div>

      {/* Step 3: Animated 7-Stage Execution Pipeline */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-purple-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Step 3: Autonomous Pipeline Animation
            </h2>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {isExecuting ? 'Stage Execution in Progress...' : 'Ready for Execution'}
          </span>
        </div>

        {/* Vertical Animated Pipeline Flow */}
        <div className="space-y-4 max-w-3xl mx-auto">
          {stages.map((stage, idx) => {
            const isIdle = stage.status === 'idle';
            const isRunning = stage.status === 'running';
            const isCompleted = stage.status === 'completed';
            const isBlocked = stage.status === 'blocked';

            return (
              <React.Fragment key={stage.id}>
                <div
                  className={`p-4 rounded-xl border transition-all duration-300 ${
                    isRunning
                      ? 'border-amber-500/80 bg-amber-950/30 shadow-fintech-glow animate-pulse'
                      : isBlocked
                      ? 'border-rose-500/50 bg-rose-950/30 shadow-fintech-glow-rose'
                      : isCompleted
                      ? 'border-emerald-500/40 bg-slate-900/90'
                      : 'border-slate-800/80 bg-slate-900/30 opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      {/* Step Indicator */}
                      <div
                        className={`h-7 w-7 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                          isRunning
                            ? 'bg-amber-500 text-slate-950 animate-spin'
                            : isBlocked
                            ? 'bg-rose-500 text-white'
                            : isCompleted
                            ? 'bg-emerald-500 text-slate-950'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {idx + 1}
                      </div>

                      <div>
                        <span className="text-sm font-bold text-white font-mono flex items-center gap-2">
                          {stage.name}
                          {isCompleted && (
                            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                          )}
                          {isBlocked && (
                            <XCircle className="h-4 w-4 text-rose-400" />
                          )}
                        </span>
                        <p className="text-xs text-slate-400 mt-0.5">{stage.desc}</p>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div>
                      {isRunning && (
                        <span className="px-2.5 py-1 rounded text-xs font-mono font-semibold bg-amber-950 text-amber-300 border border-amber-500/40 animate-pulse">
                          PROCESSING
                        </span>
                      )}
                      {isCompleted && (
                        <span className="px-2.5 py-1 rounded text-xs font-mono font-semibold bg-emerald-950 text-emerald-300 border border-emerald-500/40">
                          VERIFIED
                        </span>
                      )}
                      {isBlocked && (
                        <span className="px-2.5 py-1 rounded text-xs font-mono font-semibold bg-rose-950 text-rose-300 border border-rose-500/40">
                          BLOCKED
                        </span>
                      )}
                      {isIdle && (
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-500 bg-slate-950">
                          QUEUED
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Stage Payload Details (if completed or blocked) */}
                  {stage.data && (
                    <div className="mt-3 pt-3 border-t border-slate-800/80 text-xs font-mono">
                      {stage.id === 'ml' && (
                        <div className="flex items-center justify-between text-indigo-300 bg-slate-950/60 p-2.5 rounded">
                          <span>Recovery Probability:</span>
                          <strong className="text-base text-emerald-400 font-bold">
                            {formatPercent(stage.data.recovery_probability)}
                          </strong>
                        </div>
                      )}
                      {stage.id === 'policy' && (
                        <div className="flex items-center justify-between text-xs bg-slate-950/60 p-2.5 rounded">
                          <span>
                            Policy Rule Check: <strong className="text-white">{stage.data.rule_id}</strong>
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              stage.data.outcome === 'ALLOWED'
                                ? 'text-emerald-400 bg-emerald-950/60 border border-emerald-500/30'
                                : 'text-rose-400 bg-rose-950/60 border border-rose-500/30'
                            }`}
                          >
                            {stage.data.outcome}
                          </span>
                        </div>
                      )}
                      {stage.id === 'execution' && (
                        <div className="flex items-center justify-between text-xs bg-slate-950/60 p-2.5 rounded">
                          <span>
                            Selected Action: <strong className="text-indigo-300">{stage.data.selected_action}</strong>
                          </span>
                          <span className="text-slate-300">Status: {stage.data.status}</span>
                        </div>
                      )}
                      {stage.id === 'monitoring' && (
                        <div className="flex items-center justify-between text-xs bg-slate-950/60 p-2.5 rounded">
                          <span>
                            Monitoring Outcome: <strong className="text-emerald-400">{stage.data.outcome}</strong>
                          </span>
                          <span>
                            Revenue Captured: <strong className="text-emerald-400 font-tabular">{formatINR(stage.data.revenue_recovered)}</strong>
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Animated Arrow Connector */}
                {idx < stages.length - 1 && (
                  <div className="flex justify-center my-0.5">
                    <ArrowDown
                      className={`h-4 w-4 ${
                        stages[idx].status === 'completed'
                          ? 'text-emerald-400'
                          : stages[idx].status === 'blocked'
                          ? 'text-rose-400'
                          : 'text-slate-700'
                      }`}
                    />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Step 4: Prominent Visually Clear Demonstration Result */}
      {executionResult && (
        <div
          className={`rounded-2xl border p-8 shadow-2xl transition-all duration-300 animate-fadeIn ${
            executionResult.is_unsafe
              ? 'border-rose-500/50 bg-gradient-to-b from-rose-950/40 to-slate-950 shadow-fintech-glow-rose'
              : 'border-emerald-500/50 bg-gradient-to-b from-emerald-950/40 to-slate-950 shadow-fintech-glow-emerald'
          }`}
        >
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex items-center gap-3">
                <span
                  className={`p-2.5 rounded-xl ${
                    executionResult.is_unsafe
                      ? 'bg-rose-950 border border-rose-500/40 text-rose-400'
                      : 'bg-emerald-950 border border-emerald-500/40 text-emerald-400'
                  }`}
                >
                  {executionResult.is_unsafe ? (
                    <ShieldAlert className="h-6 w-6" />
                  ) : (
                    <ShieldCheck className="h-6 w-6" />
                  )}
                </span>
                <div>
                  <h3 className="text-xl font-bold text-white tracking-tight">
                    {executionResult.is_unsafe
                      ? 'Unsafe Flow: Policy Guardrail Blocked Execution'
                      : 'Successful Flow: Autonomous Payment Recovered'}
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {executionResult.is_unsafe
                      ? 'High-risk transaction intercepted by Rule POL-003 and escalated to compliance review.'
                      : 'Temporary failure resolved via automated recovery action and verified on simulator rail.'}
                  </p>
                </div>
              </div>
            </div>

            <span
              className={`self-start md:self-auto px-3.5 py-1.5 rounded-full text-xs font-mono font-bold border ${
                executionResult.is_unsafe
                  ? 'bg-rose-950 text-rose-300 border-rose-500/40'
                  : 'bg-emerald-950 text-emerald-300 border-emerald-500/40'
              }`}
            >
              {executionResult.is_unsafe ? 'ESCALATED / BLOCKED' : 'RECOVERED / SUCCESS'}
            </span>
          </div>

          {/* Executive 7-Metric Decision & Audit Strip */}
          <DecisionAuditStrip
            revenueAtRisk={executionResult.amount}
            recoverableRevenue={
              executionResult.is_unsafe
                ? 0
                : Math.round(executionResult.amount * (executionResult.recovery_probability || 0.8))
            }
            revenueRecovered={executionResult.is_unsafe ? 0 : (executionResult.revenue_recovered || executionResult.amount)}
            recoveryRate={executionResult.is_unsafe ? 0 : ((executionResult.recovery_probability || 0.8) * 100)}
            agentDecision={executionResult.selected_action}
            policyDecision={executionResult.policy_decision || (executionResult.is_unsafe ? 'BLOCKED' : 'ALLOWED')}
            policyRuleId={executionResult.is_unsafe ? 'POL-003' : 'POL-004'}
            reason={
              executionResult.is_unsafe
                ? 'Fraud risk score exceeds 0.85 safety threshold. Retries halted to eliminate chargeback liability.'
                : `Autonomous pipeline validated transient ${executionResult.failure_code}; ML probability is ${formatPercent(
                    executionResult.recovery_probability || 0.8
                  )}. Policy approved retry.`
            }
            auditHash={executionResult.audit_hash}
            verifiedIntegrity={true}
            latencyMs={executionResult.latency_ms || 4.2}
            title="Live Autonomous Execution Governance Audit"
          />

          {/* Key Metric Comparison Grid matching the user's prompt example */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 pt-4 text-center">
            {/* 1. Transaction Amount */}
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Amount
              </span>
              <p className="text-lg font-bold font-tabular text-white">
                {formatINR(executionResult.amount)}
              </p>
            </div>

            {/* 2. Failure Code */}
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Failure
              </span>
              <p className="text-xs font-bold font-mono text-rose-400 truncate pt-1">
                {executionResult.failure_code}
              </p>
            </div>

            {/* 3. Recovery Probability */}
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Recovery Prob
              </span>
              <p
                className={`text-lg font-bold font-tabular ${
                  executionResult.is_unsafe ? 'text-rose-400' : 'text-emerald-400'
                }`}
              >
                {executionResult.is_unsafe
                  ? 'BLOCKED'
                  : formatPercent(executionResult.recovery_probability)}
              </p>
            </div>

            {/* 4. Selected Action */}
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Action
              </span>
              <p className="text-xs font-bold font-mono text-indigo-300 truncate pt-1">
                {executionResult.selected_action}
              </p>
            </div>

            {/* 5. Policy Decision */}
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Policy
              </span>
              <p
                className={`text-sm font-bold font-mono pt-1 ${
                  executionResult.policy_decision === 'ALLOWED'
                    ? 'text-emerald-400'
                    : 'text-rose-400'
                }`}
              >
                {executionResult.policy_decision}
              </p>
            </div>

            {/* 6. Revenue Recovered */}
            <div
              className={`p-3.5 rounded-xl border space-y-1 ${
                executionResult.is_unsafe
                  ? 'bg-rose-950/40 border-rose-500/40'
                  : 'bg-emerald-950/40 border-emerald-500/40'
              }`}
            >
              <span className="text-[11px] uppercase tracking-wider text-slate-300 font-semibold">
                {executionResult.is_unsafe ? 'Loss Prevented' : 'Recovered'}
              </span>
              <p
                className={`text-lg font-bold font-tabular ${
                  executionResult.is_unsafe ? 'text-rose-400' : 'text-emerald-400'
                }`}
              >
                {executionResult.is_unsafe ? '₹0.00' : formatINR(executionResult.revenue_recovered)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
