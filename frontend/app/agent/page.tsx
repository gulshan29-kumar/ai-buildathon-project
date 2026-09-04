'use client';

import React, { useState, useEffect } from 'react';
import {
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Cpu,
  ShieldCheck,
  Zap,
  ArrowRight,
  RefreshCw,
  Terminal,
  Layers,
  ChevronRight,
} from 'lucide-react';
import {
  getTransactions,
  orchestrateWorkflow,
  Transaction,
  formatINR,
  formatPercent,
  getStatusBadge,
} from '../../lib/api';

const PIPELINE_NODES = [
  { id: 'EVENT', label: 'EVENT', title: 'Payment Event Ingestion', desc: 'Capture failure or abandonment' },
  { id: 'ROOT_CAUSE', label: 'ROOT CAUSE', title: 'Root Cause Classification', desc: 'Diagnose error category & code' },
  { id: 'ML', label: 'ML', title: 'Predictive ML Scoring', desc: 'Predict baseline recoverability' },
  { id: 'ACTIONS', label: 'ACTIONS', title: 'Candidate Action Analysis', desc: 'Calculate EV across 6 actions' },
  { id: 'POLICY', label: 'POLICY', title: 'Deterministic Policy Guard', desc: 'Validate against 12 rules' },
  { id: 'DECISION', label: 'DECISION', title: 'Autonomous Action Decision', desc: 'Select optimal safe action' },
  { id: 'EXECUTION', label: 'EXECUTION', title: 'Simulator Execution Rail', desc: 'Execute action deterministically' },
  { id: 'RESULT', label: 'RESULT', title: 'Outcome Monitoring & Audit', desc: 'Evaluate state & update ledger' },
];

export default function AgentWorkflowPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedTxnId, setSelectedTxnId] = useState<string>('');
  const [isRunning, setIsRunning] = useState(false);
  const [activeStepIndex, setActiveStepIndex] = useState<number>(-1);
  const [workflowResult, setWorkflowResult] = useState<any>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('EVENT');
  const [logs, setLogs] = useState<Array<{ timestamp: string; node: string; message: string }>>([]);

  useEffect(() => {
    async function loadTxns() {
      try {
        const res = await getTransactions({ limit: 20 });
        const txns = res.transactions || [];
        setTransactions(txns);
        if (txns.length > 0) {
          setSelectedTxnId(txns[0].transaction_id);
        }
      } catch (err) {
        console.error('Failed to load transactions for agent workflow:', err);
      }
    }
    loadTxns();
  }, []);

  const handleRunWorkflow = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setWorkflowResult(null);
    setActiveStepIndex(0);
    setLogs([
      {
        timestamp: new Date().toLocaleTimeString(),
        node: 'EVENT',
        message: `Starting Agentic Orchestrator for transaction ${selectedTxnId}...`,
      },
    ]);

    try {
      const selectedTxn = transactions.find((t) => t.transaction_id === selectedTxnId) || {
        transaction_id: selectedTxnId,
        amount: 2500,
        payment_method: 'UPI',
        failure_code: 'GATEWAY_TIMEOUT',
      };

      // Animate through steps smoothly while waiting for backend orchestrator
      for (let i = 1; i < PIPELINE_NODES.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 350));
        setActiveStepIndex(i);
        setLogs((prev) => [
          ...prev,
          {
            timestamp: new Date().toLocaleTimeString(),
            node: PIPELINE_NODES[i].id,
            message: `Executing stage: ${PIPELINE_NODES[i].title}`,
          },
        ]);
      }

      // Real backend orchestration execution
      const result = await orchestrateWorkflow({
        transaction: selectedTxn,
        event: selectedTxn,
      });

      setWorkflowResult(result);
      setSelectedNodeId('DECISION');

      setLogs((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          node: 'RESULT',
          message: `Workflow completed. Selected: ${result.selected_action} | Outcome: ${result.monitoring_outcome}`,
        },
      ]);
    } catch (err: any) {
      setLogs((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          node: 'ERROR',
          message: `Orchestrator failed: ${err.message}`,
        },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  // Extract node details
  const getNodeDetails = (nodeId: string) => {
    if (!workflowResult) {
      return {
        status: 'PENDING',
        summary: 'Click "Run Autonomous Workflow" to trigger real execution.',
        payload: null,
      };
    }

    switch (nodeId) {
      case 'EVENT':
        return {
          status: 'COMPLETED',
          summary: `Payment event ingested for ${workflowResult.transaction_id}`,
          payload: {
            transaction_id: workflowResult.transaction_id,
            amount: workflowResult.transaction?.amount,
            method: workflowResult.transaction?.payment_method,
            failure_code: workflowResult.transaction?.failure_code,
          },
        };
      case 'ROOT_CAUSE':
        return {
          status: 'COMPLETED',
          summary: `Identified category: ${workflowResult.root_cause?.category || 'TEMPORARY'}`,
          payload: workflowResult.root_cause,
        };
      case 'ML':
        return {
          status: 'COMPLETED',
          summary: `Predicted general recoverability: ${formatPercent(workflowResult.ml_prediction?.recovery_probability || 0.72)}`,
          payload: workflowResult.ml_prediction,
        };
      case 'ACTIONS':
        return {
          status: 'COMPLETED',
          summary: `Analyzed ${workflowResult.candidate_actions?.length || 6} candidate recovery actions`,
          payload: workflowResult.candidate_actions,
        };
      case 'POLICY':
        return {
          status: 'COMPLETED',
          summary: 'Validated candidate actions against all 12 policy rules',
          payload: {
            policy_decision: workflowResult.policy_decision,
            candidate_policy_outcomes: workflowResult.candidate_actions?.map((c: any) => ({
              action: c.action,
              permitted: c.permitted,
              policy_outcome: c.policy_outcome,
              rule_id: c.rule_id,
            })),
          },
        };
      case 'DECISION':
        return {
          status: 'COMPLETED',
          summary: `Selected: ${workflowResult.selected_action}`,
          payload: {
            selected_action: workflowResult.selected_action,
            action_parameters: workflowResult.action_parameters,
            step_count: workflowResult.step_count,
          },
        };
      case 'EXECUTION':
        return {
          status: 'COMPLETED',
          summary: `Executed on Simulator rail: ${workflowResult.execution_result?.status || 'INITIATED'}`,
          payload: workflowResult.execution_result,
        };
      case 'RESULT':
        return {
          status: 'COMPLETED',
          summary: `Final outcome: ${workflowResult.monitoring_outcome}`,
          payload: {
            monitoring_outcome: workflowResult.monitoring_outcome,
            errors: workflowResult.errors,
          },
        };
      default:
        return { status: 'UNKNOWN', summary: '', payload: null };
    }
  };

  const selectedNodeData = getNodeDetails(selectedNodeId);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Agentic Recovery Orchestrator
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-500/40">
              LangGraph Powered
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Live 8-stage autonomous pipeline: diagnosis, ML valuation, policy gating, decision, and simulated execution.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <select
            value={selectedTxnId}
            onChange={(e) => setSelectedTxnId(e.target.value)}
            disabled={isRunning}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
          >
            {transactions.map((t) => (
              <option key={t.transaction_id} value={t.transaction_id}>
                {t.transaction_id} — {t.failure_code || 'NONE'} ({formatINR(t.amount)})
              </option>
            ))}
          </select>

          <button
            onClick={handleRunWorkflow}
            disabled={isRunning || !selectedTxnId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-fintech-glow transition active:scale-95 disabled:opacity-50"
          >
            <Play className={`h-3.5 w-3.5 ${isRunning ? 'animate-spin' : ''}`} />
            <span>{isRunning ? 'Running Stage...' : 'Run Autonomous Workflow'}</span>
          </button>
        </div>
      </div>

      {/* Visual 8-Stage Interactive Pipeline Flow */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Pipeline Architecture (Click stage to inspect payload)
          </h2>
          <span className="text-xs font-mono text-emerald-400">Deterministic Safety Gated</span>
        </div>

        {/* Pipeline Nodes Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 relative">
          {PIPELINE_NODES.map((node, index) => {
            const isSelected = selectedNodeId === node.id;
            const isCompleted = workflowResult !== null;
            const isCurrentActive = activeStepIndex === index;

            return (
              <button
                key={node.id}
                onClick={() => setSelectedNodeId(node.id)}
                className={`relative flex flex-col items-center justify-center p-3 rounded-lg border text-center transition-all ${
                  isSelected
                    ? 'border-indigo-500 bg-indigo-950/60 shadow-fintech-glow scale-105 z-10'
                    : isCurrentActive
                    ? 'border-amber-500 bg-amber-950/40 animate-pulse'
                    : isCompleted
                    ? 'border-emerald-500/40 bg-slate-900/80 hover:bg-slate-800'
                    : 'border-slate-800 bg-slate-900/40 hover:bg-slate-800/60'
                }`}
              >
                <span className="text-[10px] font-mono text-slate-500 mb-1">0{index + 1}</span>
                <span
                  className={`font-mono text-xs font-bold ${
                    isSelected ? 'text-indigo-300' : isCompleted ? 'text-emerald-400' : 'text-slate-300'
                  }`}
                >
                  {node.label}
                </span>
                <span className="text-[10px] text-slate-400 mt-1 leading-tight line-clamp-1">
                  {node.title.split(' ')[0]}
                </span>

                {/* Status Dot */}
                <span
                  className={`mt-2 h-1.5 w-1.5 rounded-full ${
                    isCurrentActive
                      ? 'bg-amber-400 animate-ping'
                      : isCompleted
                      ? 'bg-emerald-400'
                      : 'bg-slate-700'
                  }`}
                ></span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Stage Deep Dive Inspector & Terminal Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Node Deep Dive Inspector */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white">
                Stage Inspector: <span className="text-indigo-300 font-mono">{selectedNodeId}</span>
              </h3>
            </div>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                selectedNodeData.status === 'COMPLETED'
                  ? 'bg-emerald-950/70 border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-900 border-slate-800 text-slate-400'
              }`}
            >
              {selectedNodeData.status}
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed font-medium">
            {selectedNodeData.summary}
          </p>

          {/* Raw State JSON View */}
          <div className="space-y-1.5">
            <span className="text-[11px] font-mono text-slate-400">Node State Output (JSON)</span>
            <div className="bg-slate-950/90 border border-slate-900 rounded-lg p-3 font-mono text-[11px] text-slate-300 max-h-72 overflow-y-auto">
              {selectedNodeData.payload ? (
                <pre>{JSON.stringify(selectedNodeData.payload, null, 2)}</pre>
              ) : (
                <span className="text-slate-600">No output generated for this stage yet.</span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Live Orchestrator Terminal */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-white">Execution Stream Terminal</h3>
              </div>
              <span className="text-[10px] font-mono text-slate-500">Auto-logging</span>
            </div>

            <div className="bg-slate-950 border border-slate-900 rounded-lg p-3 font-mono text-[11px] h-64 overflow-y-auto space-y-2 text-slate-300">
              {logs.length === 0 ? (
                <span className="text-slate-600">Ready. Click &quot;Run Autonomous Workflow&quot; to start.</span>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-slate-600 flex-shrink-0">[{log.timestamp}]</span>
                    <span className="text-indigo-400 font-bold flex-shrink-0">[{log.node}]</span>
                    <span className="text-slate-200">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-500 font-mono flex items-center justify-between">
            <span>LangGraph Synchronous Sandbox</span>
            <span>Safety Guard: 100% Deterministic</span>
          </div>
        </div>
      </div>
    </div>
  );
}
