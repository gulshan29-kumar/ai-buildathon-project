'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Play,
  RotateCcw,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Zap,
  ArrowRight,
  Info,
  Layers,
  Lock,
  Cpu,
  Database,
  ChevronDown,
  ChevronRight,
  FileText,
  Check,
  X,
  Clock,
  BarChart3,
  ShieldAlert,
  HelpCircle,
  Hash,
  Download,
  Terminal,
  Activity,
  User,
  Store,
  DollarSign,
  AlertCircle,
  Copy,
} from 'lucide-react';
import {
  CuratedScenarioSummary,
  CuratedScenarioTrace,
  CuratedScenariosBatchSummary,
  getCuratedScenarios,
  getCuratedScenarioTrace,
  runCuratedScenario,
  runAllCuratedScenarios,
  resetCuratedScenarios,
  formatINR,
  formatPercent,
  getActionBadge,
  getStatusBadge,
} from '../../lib/api';

export default function DemoScenariosPage() {
  const [scenarios, setScenarios] = useState<CuratedScenarioSummary[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('scenario_gateway_timeout');
  const [currentTrace, setCurrentTrace] = useState<CuratedScenarioTrace | null>(null);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingTrace, setLoadingTrace] = useState<boolean>(false);
  const [runningScenario, setRunningScenario] = useState<boolean>(false);
  const [runningAll, setRunningAll] = useState<boolean>(false);
  const [filterCategory, setFilterCategory] = useState<string>('ALL');
  const [activeTab, setActiveTab] = useState<'pipeline' | 'json'>('pipeline');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);

  // Show Toast
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Fetch individual trace
  const loadScenarioTrace = React.useCallback(async (id: string) => {
    setLoadingTrace(true);
    try {
      const trace = await getCuratedScenarioTrace(id);
      setCurrentTrace(trace);
    } catch (err: any) {
      showToast(`Failed to load trace for ${id}: ${err.message}`);
    } finally {
      setLoadingTrace(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    async function loadData() {
      setLoadingList(true);
      try {
        const res = await getCuratedScenarios();
        setScenarios(res.scenarios);
        if (res.scenarios.length > 0) {
          const firstId = res.scenarios[0].scenario_id;
          setSelectedScenarioId(firstId);
          loadScenarioTrace(firstId);
        }
      } catch (err: any) {
        showToast(`Failed to load scenarios: ${err.message}`);
      } finally {
        setLoadingList(false);
      }
    }
    loadData();
  }, [loadScenarioTrace]);

  // Select scenario
  const handleSelectScenario = (id: string) => {
    setSelectedScenarioId(id);
    loadScenarioTrace(id);
  };

  // Run single scenario
  const handleRunSingle = async (id: string) => {
    if (runningScenario) return;
    setRunningScenario(true);
    try {
      const updated = await runCuratedScenario(id);
      setCurrentTrace(updated);
      // Update in summary list as well
      setScenarios((prev) =>
        prev.map((s) =>
          s.scenario_id === id
            ? {
                ...s,
                is_executed: true,
                recovered: updated.revenue_recovered.recovered,
                revenue_recovered: updated.revenue_recovered.amount,
                selected_action: updated.agent_decision.selected_action,
                last_run_timestamp: updated.executed_at,
              }
            : s
        )
      );
      showToast(`Scenario #${updated.index} executed deterministically.`);
    } catch (err: any) {
      showToast(`Run failed: ${err.message}`);
    } finally {
      setRunningScenario(false);
    }
  };

  // Run all 8 scenarios
  const handleRunAll = async () => {
    if (runningAll) return;
    setRunningAll(true);
    try {
      const batch: CuratedScenariosBatchSummary = await runAllCuratedScenarios();
      const res = await getCuratedScenarios();
      setScenarios(res.scenarios);
      if (selectedScenarioId) {
        const matchingTrace = batch.traces.find((t) => t.scenario_id === selectedScenarioId);
        if (matchingTrace) {
          setCurrentTrace(matchingTrace);
        } else {
          loadScenarioTrace(selectedScenarioId);
        }
      }
      showToast(`All 8 curated scenarios executed deterministically (${batch.recovered_count}/8 recovered).`);
    } catch (err: any) {
      showToast(`Batch run failed: ${err.message}`);
    } finally {
      setRunningAll(false);
    }
  };

  // Reset sandbox seeds
  const handleReset = async () => {
    try {
      await resetCuratedScenarios();
      const res = await getCuratedScenarios();
      setScenarios(res.scenarios);
      if (selectedScenarioId) {
        loadScenarioTrace(selectedScenarioId);
      }
      showToast('Sandbox reset to original deterministic seeds.');
    } catch (err: any) {
      showToast(`Reset failed: ${err.message}`);
    }
  };

  // Copy raw JSON
  const handleCopyJson = () => {
    if (!currentTrace) return;
    navigator.clipboard.writeText(JSON.stringify(currentTrace, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
    showToast('Trace JSON copied to clipboard.');
  };

  // Download all traces JSON
  const handleDownloadJson = () => {
    if (!currentTrace) return;
    const blob = new Blob([JSON.stringify(currentTrace, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentTrace.scenario_id}_trace.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Derived metrics
  const totalScenarios = scenarios.length;
  const recoveredCount = scenarios.filter((s) => s.recovered).length;
  const recoveryRate = totalScenarios > 0 ? (recoveredCount / totalScenarios) * 100 : 0;
  const totalRevenueRecovered = scenarios.reduce((acc, s) => acc + (s.revenue_recovered || 0), 0);
  const totalRevenueAtRisk = scenarios.reduce((acc, s) => acc + (s.amount || 0), 0);
  const preventedFraud = 85000;

  // Filtered scenarios
  const filteredScenarios = scenarios.filter((s) => {
    if (filterCategory === 'ALL') return true;
    return s.category === filterCategory;
  });

  const categories = ['ALL', 'TEMPORARY', 'BANK', 'PAYMENT_METHOD', 'ABANDONMENT', 'RISK', 'PENDING', 'DUPLICATE', 'MERCHANT'];

  return (
    <div className="space-y-8 animate-fadeIn pb-16">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-indigo-950/90 border border-indigo-500/50 text-sm text-indigo-200 shadow-xl backdrop-blur-md animate-slideUp">
          <CheckCircle2 className="h-4 w-4 text-indigo-400 flex-shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-fintech-border pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-indigo-400" /> Phase 25
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
              <ShieldCheck className="h-3 w-3 text-emerald-400" /> 100% Deterministic & Reproducible
            </span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
            Curated Demo Scenarios
          </h1>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            8 deterministic payment failure and abandonment recovery transactions showcasing end-to-end autonomous decisioning with 9 forensic pipeline stages.
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-700 hover:border-slate-600 text-xs font-medium text-slate-300 transition-all hover:bg-slate-800/80 shadow-sm"
            title="Reset to default initial seeds"
          >
            <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
            <span>Reset Seeds</span>
          </button>

          <button
            onClick={handleRunAll}
            disabled={runningAll}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all hover:scale-[1.02] active:scale-[0.98] ${
              runningAll ? 'opacity-70 cursor-not-allowed' : ''
            }`}
          >
            {runningAll ? (
              <>
                <div className="h-3.5 w-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Running 8 Scenarios...</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Run All 8 Scenarios</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Top Metrics Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/90 shadow-sm">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Curated Scenarios</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold font-tabular text-white">{totalScenarios}</span>
            <span className="text-xs text-slate-500">total scenarios</span>
          </div>
          <p className="text-[11px] text-indigo-400 mt-1 flex items-center gap-1">
            <Check className="h-3 w-3" /> All 8 deterministic
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/90 shadow-sm">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Recovered Count</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold font-tabular text-emerald-400">{recoveredCount}</span>
            <span className="text-xs text-slate-500">/ {totalScenarios} captured</span>
          </div>
          <p className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> 100% eligible recovered
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/90 shadow-sm">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Recovery Rate</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold font-tabular text-white">{recoveryRate.toFixed(1)}%</span>
            <span className="text-xs text-slate-500">aggregate</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Excludes intentional blocks
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/90 shadow-sm">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Revenue Recovered</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold font-tabular text-emerald-400">{formatINR(totalRevenueRecovered)}</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            of {formatINR(totalRevenueAtRisk)} at risk
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/90 shadow-sm col-span-2 md:col-span-1">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Prevented Fraud Loss</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold font-tabular text-rose-400">{formatINR(preventedFraud)}</span>
          </div>
          <p className="text-[11px] text-rose-300 mt-1 flex items-center gap-1">
            <Lock className="h-3 w-3" /> POL-003 strict block
          </p>
        </div>
      </div>

      {/* Category Filter Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
        <span className="text-slate-400 mr-2 font-medium">Filter Category:</span>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilterCategory(cat)}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              filterCategory === cat
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-slate-900/90 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Scenarios Selector Grid (8 Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {filteredScenarios.map((sc) => {
          const isSelected = sc.scenario_id === selectedScenarioId;
          const actionBadge = getActionBadge(sc.selected_action || sc.expected_action);
          return (
            <div
              key={sc.scenario_id}
              onClick={() => handleSelectScenario(sc.scenario_id)}
              className={`p-4 rounded-xl border transition-all cursor-pointer relative flex flex-col justify-between group ${
                isSelected
                  ? 'bg-gradient-to-b from-indigo-950/70 to-slate-900 border-indigo-500/80 shadow-lg shadow-indigo-950/40 ring-1 ring-indigo-500/40'
                  : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/90'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-slate-800 text-slate-300 border border-slate-700">
                    #{sc.index}
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                      sc.badge_color === 'emerald'
                        ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-500/30'
                        : sc.badge_color === 'rose'
                        ? 'bg-rose-950/70 text-rose-300 border border-rose-500/30'
                        : sc.badge_color === 'purple'
                        ? 'bg-purple-950/70 text-purple-300 border border-purple-500/30'
                        : sc.badge_color === 'indigo'
                        ? 'bg-indigo-950/70 text-indigo-300 border border-indigo-500/30'
                        : sc.badge_color === 'sky'
                        ? 'bg-sky-950/70 text-sky-300 border border-sky-500/30'
                        : sc.badge_color === 'orange'
                        ? 'bg-orange-950/70 text-orange-300 border border-orange-500/30'
                        : sc.badge_color === 'teal'
                        ? 'bg-teal-950/70 text-teal-300 border border-teal-500/30'
                        : 'bg-amber-950/70 text-amber-300 border border-amber-500/30'
                    }`}
                  >
                    {sc.category}
                  </span>
                </div>

                <h3 className="text-sm font-bold text-white group-hover:text-indigo-300 transition-colors line-clamp-2">
                  {sc.title}
                </h3>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                  {sc.description}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <div>
                  <span className="text-[11px] text-slate-500 block">Amount</span>
                  <span className="font-bold font-tabular text-white">{formatINR(sc.amount)}</span>
                </div>

                <div className="text-right">
                  <span className="text-[11px] text-slate-500 block">Decision</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${actionBadge.bg} ${actionBadge.text} ${actionBadge.border}`}>
                    {sc.selected_action || sc.expected_action}
                  </span>
                </div>
              </div>

              {isSelected && (
                <div className="absolute -top-1.5 -right-1.5 h-3 w-3 rounded-full bg-indigo-500 shadow-md ring-2 ring-slate-900" />
              )}
            </div>
          );
        })}
      </div>

      {/* Detailed 9-Stage Inspector for Selected Scenario */}
      {currentTrace ? (
        <div className="rounded-2xl border border-fintech-border bg-slate-900/80 backdrop-blur-md overflow-hidden shadow-2xl">
          {/* Detail Header */}
          <div className="p-6 border-b border-fintech-border bg-slate-950/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5 mb-1.5">
                <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-500/40">
                  Scenario #{currentTrace.index}
                </span>
                <span className="px-2.5 py-0.5 rounded text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800">
                  {currentTrace.scenario_id}
                </span>
                <span className="text-xs text-slate-500">
                  Executed: {new Date(currentTrace.executed_at).toLocaleTimeString()}
                </span>
              </div>
              <h2 className="text-2xl font-extrabold text-white">
                {currentTrace.title}
              </h2>
              <p className="text-sm text-slate-400 mt-1 max-w-3xl">
                {currentTrace.input.description}
              </p>
            </div>

            {/* Action Buttons for current scenario */}
            <div className="flex items-center gap-3 flex-shrink-0">
              <div className="flex items-center rounded-lg bg-slate-900 border border-slate-800 p-1">
                <button
                  onClick={() => setActiveTab('pipeline')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    activeTab === 'pipeline'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  9-Stage Pipeline
                </button>
                <button
                  onClick={() => setActiveTab('json')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    activeTab === 'json'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Raw JSON Trace
                </button>
              </div>

              <button
                onClick={() => handleRunSingle(currentTrace.scenario_id)}
                disabled={runningScenario}
                className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md transition-all"
              >
                {runningScenario ? (
                  <div className="h-3.5 w-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5 fill-current" />
                )}
                <span>Re-run Deterministic</span>
              </button>
            </div>
          </div>

          {activeTab === 'pipeline' ? (
            <div className="p-6 md:p-8 space-y-8">
              {/* Pipeline Step Indicators Bar */}
              <div className="grid grid-cols-3 sm:grid-cols-9 gap-2 text-center text-xs">
                {[
                  { num: 1, label: 'Input' },
                  { num: 2, label: 'Root Cause' },
                  { num: 3, label: 'ML Model' },
                  { num: 4, label: 'Candidates' },
                  { num: 5, label: 'Policy' },
                  { num: 6, label: 'Agent' },
                  { num: 7, label: 'Simulator' },
                  { num: 8, label: 'Revenue' },
                  { num: 9, label: 'Audit Trail' },
                ].map((st) => (
                  <div
                    key={st.num}
                    className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 flex flex-col items-center justify-center gap-1"
                  >
                    <span className="h-5 w-5 rounded-full bg-indigo-900/60 text-indigo-300 font-bold font-mono text-[11px] flex items-center justify-center border border-indigo-500/30">
                      {st.num}
                    </span>
                    <span className="text-[11px] font-medium text-slate-300">{st.label}</span>
                  </div>
                ))}
              </div>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 1: INPUT */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-blue-950 text-blue-300 font-bold font-mono text-xs flex items-center justify-center border border-blue-500/30">
                      1
                    </span>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      Input Event Ingestion
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    ID: {currentTrace.input.transaction_id}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800/80">
                    <span className="text-slate-400 text-[11px] block">Amount & Currency</span>
                    <span className="text-sm font-bold font-tabular text-white">
                      {formatINR(currentTrace.input.amount)} {currentTrace.input.currency}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800/80">
                    <span className="text-slate-400 text-[11px] block">Payment Method & Gateway</span>
                    <span className="text-sm font-bold text-indigo-300">
                      {currentTrace.input.payment_method} ({currentTrace.input.gateway})
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800/80">
                    <span className="text-slate-400 text-[11px] block">Reported Failure Code</span>
                    <span className="text-sm font-bold font-mono text-rose-300">
                      {currentTrace.input.failure_code}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800/80">
                    <span className="text-slate-400 text-[11px] block">Risk Score</span>
                    <span
                      className={`text-sm font-bold font-tabular ${
                        currentTrace.input.risk_score > 0.5 ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {currentTrace.input.risk_score.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Customer & Merchant Metadata */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-1">
                  <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 flex items-start gap-3">
                    <div className="p-2 rounded-md bg-indigo-950 text-indigo-400 mt-0.5">
                      <User className="h-4 w-4" />
                    </div>
                    <div>
                      <span className="font-semibold text-slate-200">
                        {currentTrace.input.customer.name} ({currentTrace.input.customer.customer_id})
                      </span>
                      <p className="text-slate-400 mt-0.5">
                        Preferred: <strong className="text-slate-200">{currentTrace.input.customer.preferred_payment_method}</strong> • Success Rate: {(currentTrace.input.customer.success_rate * 100).toFixed(0)}% • Total Txns: {currentTrace.input.customer.total_transactions}
                      </p>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 flex items-start gap-3">
                    <div className="p-2 rounded-md bg-purple-950 text-purple-400 mt-0.5">
                      <Store className="h-4 w-4" />
                    </div>
                    <div>
                      <span className="font-semibold text-slate-200">
                        {currentTrace.input.merchant.name} ({currentTrace.input.merchant.merchant_id})
                      </span>
                      <p className="text-slate-400 mt-0.5">
                        Vertical: <strong className="text-slate-200">{currentTrace.input.merchant.business_type}</strong> • Idempotency: <span className="font-mono text-[10px] text-indigo-300">{currentTrace.input.idempotency_key}</span>
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 2: ROOT CAUSE */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-amber-950 text-amber-300 font-bold font-mono text-xs flex items-center justify-center border border-amber-500/30">
                      2
                    </span>
                    <h3 className="text-base font-bold text-white">
                      Root Cause Diagnostics
                    </h3>
                  </div>
                  <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-500/30">
                    Category: {currentTrace.root_cause.category}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="md:col-span-2 p-3.5 rounded-lg bg-slate-900/80 border border-slate-800/80 space-y-1.5">
                    <span className="text-slate-400 text-[11px] block font-medium">Diagnosed Cause & Forensics</span>
                    <p className="text-sm text-slate-200 font-medium">
                      {currentTrace.root_cause.diagnosed_cause}
                    </p>
                    <div className="flex items-center gap-3 pt-1 text-slate-400 text-[11px]">
                      <span>Layer: <strong className="text-indigo-300 font-mono">{currentTrace.root_cause.raw_attributes.layer}</strong></span>
                      <span>•</span>
                      <span>Recoverability: <strong className="text-slate-200">{currentTrace.root_cause.raw_attributes.recoverability_level}</strong></span>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800/80 space-y-2">
                    <span className="text-slate-400 text-[11px] block font-medium">Classification Confidence</span>
                    <div className="flex items-baseline justify-between">
                      <span className="text-xl font-bold font-tabular text-emerald-400">
                        {(currentTrace.root_cause.confidence * 100).toFixed(0)}%
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                        currentTrace.root_cause.is_retryable
                          ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/30'
                          : 'bg-rose-950/60 text-rose-300 border-rose-500/30'
                      }`}>
                        {currentTrace.root_cause.is_retryable ? 'Temporary / Retryable' : 'Terminal / Non-retryable'}
                      </span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-emerald-500 h-full rounded-full"
                        style={{ width: `${currentTrace.root_cause.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 3: ML PREDICTION */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-indigo-950 text-indigo-300 font-bold font-mono text-xs flex items-center justify-center border border-indigo-500/30">
                      3
                    </span>
                    <h3 className="text-base font-bold text-white">
                      ML Recovery Probability & Value Estimation
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    Model: {currentTrace.ml_prediction.model_version} • Latency: {currentTrace.ml_prediction.inference_latency_ms}ms
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  {/* Probability Gauge */}
                  <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
                    <div>
                      <span className="text-slate-400 text-[11px] block font-medium">Recovery Probability</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-3xl font-extrabold font-tabular text-white">
                          {(currentTrace.ml_prediction.recovery_probability * 100).toFixed(1)}%
                        </span>
                        <span className="text-xs text-slate-400">
                          (Expected Value: <strong className="text-emerald-400">{formatINR(currentTrace.ml_prediction.expected_value)}</strong>)
                        </span>
                      </div>
                    </div>

                    <div className="mt-4 space-y-1.5">
                      <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            currentTrace.ml_prediction.recovery_probability > 0.6
                              ? 'bg-emerald-500'
                              : currentTrace.ml_prediction.recovery_probability > 0.3
                              ? 'bg-amber-500'
                              : 'bg-rose-500'
                          }`}
                          style={{ width: `${currentTrace.ml_prediction.recovery_probability * 100}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>Low: {(currentTrace.ml_prediction.confidence_band.lower * 100).toFixed(1)}%</span>
                        <span>Band ±4%</span>
                        <span>High: {(currentTrace.ml_prediction.confidence_band.upper * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>

                  {/* Feature Contributions Breakdown */}
                  <div className="md:col-span-2 p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-3">
                    <span className="text-slate-400 text-[11px] block font-medium">Feature Importance / Contribution Breakdown</span>
                    <div className="space-y-2">
                      {Object.entries(currentTrace.ml_prediction.feature_contributions).map(([feat, val]) => {
                        const isPos = val >= 0;
                        const pct = Math.min(100, Math.abs(val) * 100);
                        return (
                          <div key={feat} className="flex items-center gap-3 text-xs">
                            <span className="w-36 font-mono text-slate-300 truncate text-[11px]">{feat}</span>
                            <div className="flex-1 bg-slate-800 h-2 rounded-full overflow-hidden relative">
                              <div
                                className={`h-full rounded-full ${isPos ? 'bg-emerald-500' : 'bg-rose-500'}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className={`w-14 text-right font-mono font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {isPos ? `+${(val * 100).toFixed(0)}%` : `${(val * 100).toFixed(0)}%`}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 4: CANDIDATE ACTIONS */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-cyan-950 text-cyan-300 font-bold font-mono text-xs flex items-center justify-center border border-cyan-500/30">
                      4
                    </span>
                    <h3 className="text-base font-bold text-white">
                      Candidate Actions & Ranking Space
                    </h3>
                  </div>
                  <span className="text-xs text-slate-400">
                    {currentTrace.candidate_actions.length} options evaluated
                  </span>
                </div>

                <div className="overflow-x-auto rounded-lg border border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                      <tr>
                        <th className="px-4 py-2.5">Rank</th>
                        <th className="px-4 py-2.5">Candidate Action</th>
                        <th className="px-4 py-2.5">Win Probability</th>
                        <th className="px-4 py-2.5">Expected Value</th>
                        <th className="px-4 py-2.5">Policy Check</th>
                        <th className="px-4 py-2.5">Reasoning / Policy Rule</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 bg-slate-950/30 font-medium">
                      {currentTrace.candidate_actions.map((cand) => {
                        const actBadge = getActionBadge(cand.action);
                        return (
                          <tr key={cand.action} className="hover:bg-slate-900/40 transition-colors">
                            <td className="px-4 py-3 font-mono text-slate-400">#{cand.rank}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${actBadge.bg} ${actBadge.text} ${actBadge.border}`}>
                                {cand.action}
                              </span>
                            </td>
                            <td className="px-4 py-3 font-mono text-white">
                              {(cand.probability * 100).toFixed(1)}%
                            </td>
                            <td className="px-4 py-3 font-mono font-bold text-emerald-400">
                              {formatINR(cand.expected_recovery_value)}
                            </td>
                            <td className="px-4 py-3">
                              {cand.permitted_by_policy ? (
                                <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold text-[11px]">
                                  <Check className="h-3.5 w-3.5" /> Permitted
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-rose-400 font-semibold text-[11px]">
                                  <X className="h-3.5 w-3.5" /> Denied
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-slate-300 max-w-xs truncate text-[11px]">
                              {cand.policy_reason}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 5: POLICY ENGINE */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-purple-950 text-purple-300 font-bold font-mono text-xs flex items-center justify-center border border-purple-500/30">
                      5
                    </span>
                    <h3 className="text-base font-bold text-white">
                      Policy Engine Guardrail Verification
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-500/40">
                      Rule: {currentTrace.policy.rule_id}
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                        currentTrace.policy.decision === 'PERMITTED'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                          : currentTrace.policy.decision === 'WAIT'
                          ? 'bg-purple-950 text-purple-300 border border-purple-500/40'
                          : 'bg-rose-950 text-rose-300 border border-rose-500/40'
                      }`}
                    >
                      {currentTrace.policy.decision}
                    </span>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-3 text-xs">
                  <div>
                    <span className="text-slate-400 text-[11px] block font-medium">Policy Rationale</span>
                    <p className="text-sm font-semibold text-slate-100 mt-0.5">
                      {currentTrace.policy.reason}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-800 flex flex-wrap gap-4 text-slate-400 text-[11px]">
                    <div>
                      <span>Severity: </span>
                      <strong className={`font-semibold ${
                        currentTrace.policy.severity === 'CRITICAL' ? 'text-rose-400' : 'text-amber-400'
                      }`}>
                        {currentTrace.policy.severity}
                      </strong>
                    </div>
                    <div>
                      <span>Max Retries: </span>
                      <strong className="text-slate-200">
                        {currentTrace.policy.enforced_constraints.max_retries_allowed}
                      </strong>
                    </div>
                    <div>
                      <span>Fraud Threshold: </span>
                      <strong className="text-slate-200">
                        {currentTrace.policy.enforced_constraints.fraud_threshold}
                      </strong>
                    </div>
                    <div>
                      <span>Cooling Window: </span>
                      <strong className="text-slate-200">
                        {currentTrace.policy.enforced_constraints.cooling_period_seconds}s
                      </strong>
                    </div>
                  </div>

                  {/* Evaluated Rules List */}
                  <div className="pt-2 border-t border-slate-800">
                    <span className="text-slate-400 text-[11px] block mb-1.5 font-medium">Evaluated Rules In Policy Hierarchy</span>
                    <div className="flex flex-wrap gap-2">
                      {currentTrace.policy.rules_evaluated.map((r) => (
                        <div
                          key={r.rule_id}
                          className="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-[11px] flex items-center gap-2"
                        >
                          <span className="font-mono font-bold text-indigo-400">{r.rule_id}</span>
                          <span className="text-slate-300">{r.title}</span>
                          <span className={`font-semibold ${
                            r.status === 'PERMITTED' ? 'text-emerald-400' : r.status === 'WAIT' ? 'text-purple-400' : 'text-rose-400'
                          }`}>
                            [{r.status}]
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 6: AGENT DECISION */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-teal-950 text-teal-300 font-bold font-mono text-xs flex items-center justify-center border border-teal-500/30">
                      6
                    </span>
                    <h3 className="text-base font-bold text-white">
                      Autonomous Agent Decision & Execution Plan
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Agent Latency: {currentTrace.agent_decision.agent_latency_ms}ms</span>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-bold border ${
                      getActionBadge(currentTrace.agent_decision.selected_action).bg
                    } ${getActionBadge(currentTrace.agent_decision.selected_action).text} ${
                      getActionBadge(currentTrace.agent_decision.selected_action).border
                    }`}>
                      {currentTrace.agent_decision.selected_action}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="md:col-span-2 p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-2">
                    <span className="text-slate-400 text-[11px] block font-medium">Agent Reasoning</span>
                    <p className="text-sm font-medium text-slate-200">
                      {currentTrace.agent_decision.reasoning}
                    </p>

                    <div className="pt-2 border-t border-slate-800">
                      <span className="text-slate-400 text-[11px] block mb-1">Execution Parameters</span>
                      <pre className="p-2.5 rounded bg-slate-950 text-[11px] text-emerald-400 font-mono overflow-x-auto border border-slate-800">
                        {JSON.stringify(currentTrace.agent_decision.execution_parameters, null, 2)}
                      </pre>
                    </div>
                  </div>

                  <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-2">
                    <span className="text-slate-400 text-[11px] block font-medium">Execution Pipeline Stages</span>
                    <div className="space-y-1.5">
                      {currentTrace.agent_decision.execution_pipeline.map((step, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-[11px] text-slate-300">
                          <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 flex-shrink-0" />
                          <span>{step}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 7: SIMULATOR RESULT */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-emerald-950 text-emerald-300 font-bold font-mono text-xs flex items-center justify-center border border-emerald-500/30">
                      7
                    </span>
                    <h3 className="text-base font-bold text-white">
                      Sandbox Payment Simulator Result
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    Rail: {currentTrace.simulator_result.gateway_response.simulated_rail} • Latency: {currentTrace.simulator_result.latency_ms}ms
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-slate-400 text-[11px] block">Execution Status</span>
                    <span className="text-xs font-bold font-mono text-white mt-0.5 block">
                      {currentTrace.simulator_result.execution_status}
                    </span>
                  </div>

                  <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-slate-400 text-[11px] block">State Transition</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="font-mono text-xs text-rose-400">
                        {currentTrace.simulator_result.from_state}
                      </span>
                      <ArrowRight className="h-3 w-3 text-slate-500" />
                      <span className={`font-mono text-xs font-bold ${
                        currentTrace.simulator_result.to_state === 'SUCCESS' ? 'text-emerald-400' : 'text-slate-300'
                      }`}>
                        {currentTrace.simulator_result.to_state}
                      </span>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-slate-400 text-[11px] block">Gateway Response Code</span>
                    <span className="text-xs font-bold font-mono text-indigo-300 mt-0.5 block">
                      {currentTrace.simulator_result.gateway_response.response_code}
                    </span>
                  </div>

                  <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-slate-400 text-[11px] block">Bank RRN</span>
                    <span className="text-xs font-mono text-slate-300 mt-0.5 block">
                      {currentTrace.simulator_result.gateway_response.rrn}
                    </span>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 8: REVENUE RECOVERED */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-green-950 text-green-300 font-bold font-mono text-xs flex items-center justify-center border border-green-500/30">
                      8
                    </span>
                    <h3 className="text-base font-bold text-white">
                      Financial Ledger Reconciliation & Revenue Recovered
                    </h3>
                  </div>
                  <span
                    className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                      currentTrace.revenue_recovered.recovered
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/30'
                        : 'bg-slate-800 text-slate-300 border border-slate-700'
                    }`}
                  >
                    Status: {currentTrace.revenue_recovered.status}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-slate-400 text-[11px] block">Revenue Recovered</span>
                    <span className={`text-2xl font-extrabold font-tabular ${
                      currentTrace.revenue_recovered.recovered ? 'text-emerald-400' : 'text-slate-400'
                    }`}>
                      {formatINR(currentTrace.revenue_recovered.amount)}
                    </span>
                    <span className="text-[11px] text-slate-500 block">
                      of {formatINR(currentTrace.revenue_recovered.revenue_at_risk)} at risk
                    </span>
                  </div>

                  <div className="md:col-span-2 p-4 rounded-lg bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
                    <div>
                      <span className="text-slate-400 text-[11px] block font-medium">Economic Impact Summary</span>
                      <p className="text-sm font-semibold text-slate-100 mt-1">
                        {currentTrace.revenue_recovered.economic_impact_summary}
                      </p>
                    </div>

                    <div className="pt-2 mt-2 border-t border-slate-800 text-slate-400 text-[11px] flex items-center justify-between">
                      <span>Ledger State: RECONCILED</span>
                      <span>Recovery Contribution: {(currentTrace.revenue_recovered.recovery_rate_contribution * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              </section>

              {/* ------------------------------------------------------------- */}
              {/* STAGE 9: AUDIT TRAIL */}
              {/* ------------------------------------------------------------- */}
              <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-6 w-6 rounded-full bg-rose-950 text-rose-300 font-bold font-mono text-xs flex items-center justify-center border border-rose-500/30">
                      9
                    </span>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      Cryptographic Audit Trail (SHA-256)
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    {currentTrace.audit_trail.verified_integrity ? (
                      <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
                        <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Tamper-Evident Integrity Verified
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-rose-950 text-rose-300 border border-rose-500/30 flex items-center gap-1">
                        <AlertTriangle className="h-3.5 w-3.5 text-rose-400" /> Hash Chain Broken
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  {currentTrace.audit_trail.events.map((evt) => (
                    <div
                      key={evt.event_id}
                      className="p-3 rounded-lg bg-slate-900/80 border border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-slate-500">#{evt.index + 1}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-indigo-950/80 text-indigo-300 border border-indigo-500/30">
                          {evt.actor}
                        </span>
                        <span className="font-semibold text-slate-200">
                          {evt.event_type}
                        </span>
                      </div>

                      <div className="flex items-center gap-4 text-slate-400 text-[11px] font-mono">
                        <span title={evt.hash}>
                          Hash: <strong className="text-slate-300">{evt.hash.slice(0, 10)}...{evt.hash.slice(-6)}</strong>
                        </span>
                        <span className="text-slate-500">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            /* Raw JSON Trace Tab */
            <div className="p-6 md:p-8 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  Full 9-stage deterministic forensic trace payload
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopyJson}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition-colors"
                  >
                    {copiedJson ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        <span>Copy JSON</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={handleDownloadJson}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>Download</span>
                  </button>
                </div>
              </div>

              <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto max-h-[650px] leading-relaxed">
                {JSON.stringify(currentTrace, null, 2)}
              </pre>
            </div>
          )}
        </div>
      ) : loadingTrace ? (
        <div className="p-16 text-center text-slate-400">
          <div className="h-8 w-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm">Loading scenario forensic trace...</p>
        </div>
      ) : null}
    </div>
  );
}
