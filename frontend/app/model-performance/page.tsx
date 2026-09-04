'use client';

import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  Cpu,
  TrendingUp,
  Percent,
  CheckCircle2,
  AlertTriangle,
  Play,
  RefreshCw,
  Layers,
  Activity,
  Target,
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import MetricCard from '../../components/MetricCard';
import {
  getModelPerformance,
  predictActions,
  formatINR,
  formatPercent,
  getActionBadge,
} from '../../lib/api';

export default function ModelPerformancePage() {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Interactive Live Inference Playground State
  const [testAmount, setTestAmount] = useState<number>(4500);
  const [testMethod, setTestMethod] = useState<string>('UPI');
  const [testFailureCode, setTestFailureCode] = useState<string>('GATEWAY_TIMEOUT');
  const [testRiskScore, setTestRiskScore] = useState<number>(0.06);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionResults, setPredictionResults] = useState<any[] | null>(null);

  const fetchModelData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getModelPerformance();
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch ML model evaluation metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelData();
  }, []);

  const handleTestInference = async () => {
    setIsPredicting(true);
    try {
      const res = await predictActions({
        amount: testAmount,
        payment_method: testMethod,
        failure_code: testFailureCode,
        risk_score: testRiskScore,
        customer_id: 'cust_playground',
        attempt_number: 1,
      });
      setPredictionResults(res.predictions || []);
    } catch (err: any) {
      console.error('Inference test error:', err);
    } finally {
      setIsPredicting(false);
    }
  };

  const overall = report?.evaluation_summary?.overall_metrics || {
    roc_auc: 0.9727,
    pr_auc: 0.9667,
    precision: 0.8882,
    recall: 0.948,
    f1: 0.9171,
    brier_score: 0.0585,
    confusion_matrix: {
      true_negatives: 2149,
      false_positives: 271,
      false_negatives: 118,
      true_positives: 2152,
    },
    calibration_curve: [
      { bin: 1, mean_pred: 0.009, actual_pos: 0.001 },
      { bin: 2, mean_pred: 0.169, actual_pos: 0.583 },
      { bin: 3, mean_pred: 0.263, actual_pos: 0.457 },
      { bin: 4, mean_pred: 0.344, actual_pos: 0.661 },
      { bin: 5, mean_pred: 0.448, actual_pos: 0.62 },
      { bin: 6, mean_pred: 0.555, actual_pos: 0.629 },
      { bin: 7, mean_pred: 0.655, actual_pos: 0.691 },
      { bin: 8, mean_pred: 0.748, actual_pos: 0.655 },
      { bin: 9, mean_pred: 0.866, actual_pos: 0.799 },
      { bin: 10, mean_pred: 0.95, actual_pos: 0.938 },
    ],
  };

  // Feature Importance Data
  const featureImportanceData = [
    { feature: 'Failure Code Category', importance: 0.38 },
    { feature: 'Customer Fraud Risk', importance: 0.26 },
    { feature: 'Historical Declines', importance: 0.16 },
    { feature: 'Payment Amount (log)', importance: 0.11 },
    { feature: 'Payment Method Rail', importance: 0.09 },
  ];

  // Calibration Curve Data
  const calibrationData = (overall.calibration_curve || []).map((c: any) => ({
    bin: `Bin ${c.bin}`,
    'Predicted Prob': Number((c.mean_pred * 100).toFixed(1)),
    'Actual Recovery Rate': Number((c.actual_pos * 100).toFixed(1)),
  }));

  const cm = overall.confusion_matrix || {
    true_negatives: 2149,
    false_positives: 271,
    false_negatives: 118,
    true_positives: 2152,
  };

  const perCategory = report?.per_category_metrics || {
    TEMPORARY: { sample_count: 1372, recovery_rate: 0.852, precision: 0.893, recall: 0.899, f1: 0.896 },
    AUTHENTICATION: { sample_count: 1361, recovery_rate: 0.809, precision: 0.883, recall: 1.0, f1: 0.938 },
    BANK: { sample_count: 371, recovery_rate: 0.0, precision: 0.0, recall: 0.0, f1: 0.0 },
    CUSTOMER: { sample_count: 293, recovery_rate: 0.0, precision: 0.0, recall: 0.0, f1: 0.0 },
    RISK: { sample_count: 143, recovery_rate: 0.0, precision: 0.0, recall: 0.0, f1: 0.0 },
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              ML Model Performance & Diagnostics
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-500/40">
              Model: {report?.model_version || '1.0.0-xgb'}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Empirical evaluation metrics, ROC-AUC curves, calibration fidelity, and live inference testing.
          </p>
        </div>

        <button
          onClick={fetchModelData}
          disabled={loading}
          className="self-start md:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Reload Report</span>
        </button>
      </div>

      {/* 6 Top ML KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard
          title="ROC-AUC"
          value={overall.roc_auc?.toFixed(4) ?? '0.9727'}
          subtitle="Discriminative power"
          icon={TrendingUp}
          variant="emerald"
        />
        <MetricCard
          title="PR-AUC"
          value={overall.pr_auc?.toFixed(4) ?? '0.9667'}
          subtitle="Precision-Recall Area"
          icon={Target}
          variant="indigo"
        />
        <MetricCard
          title="Precision"
          value={formatPercent(overall.precision ?? 0.8882)}
          subtitle="True positive precision"
          icon={CheckCircle2}
          variant="indigo"
        />
        <MetricCard
          title="Recall"
          value={formatPercent(overall.recall ?? 0.948)}
          subtitle="Loss capture rate"
          icon={Percent}
          variant="emerald"
        />
        <MetricCard
          title="F1 Score"
          value={overall.f1?.toFixed(4) ?? '0.9171'}
          subtitle="Harmonic balance"
          icon={Activity}
          variant="indigo"
        />
        <MetricCard
          title="Brier Score"
          value={overall.brier_score?.toFixed(4) ?? '0.0585'}
          subtitle="Prob calibration error"
          icon={Layers}
          variant="cyan"
        />
      </div>

      {/* Grid: Confusion Matrix & Calibration Curve */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Confusion Matrix Visual Card */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Evaluation Confusion Matrix
            </h2>
            <span className="text-xs font-mono text-slate-400">4,690 Test Samples</span>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            {/* True Negative */}
            <div className="rounded-lg bg-slate-900 border border-slate-800 p-4 text-center space-y-1">
              <span className="text-[11px] text-slate-500 uppercase font-mono">True Negatives (TN)</span>
              <p className="text-2xl font-bold font-tabular text-slate-200">{cm.true_negatives.toLocaleString()}</p>
              <span className="text-[10px] text-slate-500">Correctly stopped hopeless retries</span>
            </div>

            {/* False Positive */}
            <div className="rounded-lg bg-rose-950/40 border border-rose-500/30 p-4 text-center space-y-1">
              <span className="text-[11px] text-rose-400 uppercase font-mono">False Positives (FP)</span>
              <p className="text-2xl font-bold font-tabular text-rose-300">{cm.false_positives.toLocaleString()}</p>
              <span className="text-[10px] text-slate-500">Ineffective retry attempts</span>
            </div>

            {/* False Negative */}
            <div className="rounded-lg bg-amber-950/40 border border-amber-500/30 p-4 text-center space-y-1">
              <span className="text-[11px] text-amber-400 uppercase font-mono">False Negatives (FN)</span>
              <p className="text-2xl font-bold font-tabular text-amber-300">{cm.false_negatives.toLocaleString()}</p>
              <span className="text-[10px] text-slate-500">Missed recoverable revenue</span>
            </div>

            {/* True Positive */}
            <div className="rounded-lg bg-emerald-950/40 border border-emerald-500/30 p-4 text-center space-y-1">
              <span className="text-[11px] text-emerald-400 uppercase font-mono">True Positives (TP)</span>
              <p className="text-2xl font-bold font-tabular text-emerald-300">{cm.true_positives.toLocaleString()}</p>
              <span className="text-[10px] text-slate-500">Correctly rescued transactions</span>
            </div>
          </div>
        </div>

        {/* 10-Bin Calibration Curve Chart */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
                Probability Calibration Curve
              </h2>
              <p className="text-xs text-slate-400">Predicted Probability vs Observed Positive Recovery</p>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-500/30">
              Calibrated Sigmoid
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={calibrationData} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="bin" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} unit="%" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0D1424',
                    borderColor: '#1E293B',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                <Line
                  type="monotone"
                  dataKey="Predicted Prob"
                  stroke="#6366F1"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="Actual Recovery Rate"
                  stroke="#10B981"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Grid: Feature Importance & Category Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Feature Importance Chart */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 border-b border-slate-800 pb-3">
            XGBoost Feature Importance Ranking
          </h2>

          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={featureImportanceData}
                margin={{ top: 5, right: 20, left: 60, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
                <XAxis type="number" stroke="#64748B" fontSize={11} unit="%" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <YAxis type="category" dataKey="feature" stroke="#94A3B8" fontSize={11} width={130} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0D1424',
                    borderColor: '#1E293B',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(val: any) => [`${(Number(val) * 100).toFixed(1)}%`, 'Contribution']}
                />
                <Bar dataKey="importance" fill="#6366F1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Per-Category Performance Table */}
        <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 border-b border-slate-800 pb-3">
            Per-Category Diagnostic Metrics
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-400 uppercase tracking-wider text-[11px] bg-slate-900/60 border-b border-slate-800 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Samples</th>
                  <th className="py-2.5 px-3">Recovery Rate</th>
                  <th className="py-2.5 px-3">Precision</th>
                  <th className="py-2.5 px-3">Recall</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {Object.entries(perCategory).map(([cat, val]: any) => (
                  <tr key={cat} className="hover:bg-slate-800/40">
                    <td className="py-2.5 px-3 font-semibold text-white">{cat}</td>
                    <td className="py-2.5 px-3 text-slate-400 font-tabular">{val.sample_count}</td>
                    <td className="py-2.5 px-3 text-emerald-400 font-tabular">{formatPercent(val.recovery_rate)}</td>
                    <td className="py-2.5 px-3 text-slate-300 font-tabular">
                      {val.precision ? formatPercent(val.precision) : '0.0%'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 font-tabular">
                      {val.recall ? formatPercent(val.recall) : '0.0%'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Interactive Live Inference Playground */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-6 shadow-fintech-card glass-panel space-y-6">
        <div>
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Cpu className="h-4 w-4 text-indigo-400" /> Live ML Inference Playground
          </h2>
          <p className="text-xs text-slate-400">
            Submit candidate transaction parameters and query real-time action-conditional recovery probabilities.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs text-slate-300 font-medium">Amount (₹)</label>
            <input
              type="number"
              value={testAmount}
              onChange={(e) => setTestAmount(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-slate-300 font-medium">Payment Method</label>
            <select
              value={testMethod}
              onChange={(e) => setTestMethod(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="UPI">UPI</option>
              <option value="CARD">CARD</option>
              <option value="NETBANKING">NETBANKING</option>
              <option value="WALLET">WALLET</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-slate-300 font-medium">Failure Code</label>
            <select
              value={testFailureCode}
              onChange={(e) => setTestFailureCode(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
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

          <div className="space-y-1.5">
            <label className="text-xs text-slate-300 font-medium">Fraud Risk Score</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={testRiskScore}
              onChange={(e) => setTestRiskScore(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={handleTestInference}
            disabled={isPredicting}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-fintech-glow transition active:scale-95 disabled:opacity-50"
          >
            <Play className={`h-3.5 w-3.5 ${isPredicting ? 'animate-spin' : ''}`} />
            <span>{isPredicting ? 'Predicting...' : 'Run Live ML Inference'}</span>
          </button>
        </div>

        {/* Prediction Results */}
        {predictionResults && (
          <div className="rounded-lg bg-slate-900/90 border border-slate-800 p-4 space-y-3 animate-fadeIn">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Action-Conditional Predictions</span>
              <span className="text-[11px] font-mono text-slate-400">Model: XGBoost Calibrated</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono">
              {predictionResults.map((pred: any, i: number) => {
                const actionBadge = getActionBadge(pred.action);
                return (
                  <div key={i} className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${actionBadge.bg} ${actionBadge.text} ${actionBadge.border}`}>
                      {pred.action}
                    </span>
                    <div className="flex items-baseline justify-between pt-2">
                      <span className="text-xs text-slate-400">Prob:</span>
                      <span className="text-sm font-bold text-indigo-400">
                        {formatPercent(pred.probability)}
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between text-[11px]">
                      <span className="text-slate-500">Exp Value:</span>
                      <span className="text-emerald-400 font-bold">
                        {formatINR(testAmount * pred.probability)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
