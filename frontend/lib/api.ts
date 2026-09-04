// RazorRecover AI Frontend API Client & Domain Models

const API_BASE = typeof window !== 'undefined' ? '' : (process.env.BACKEND_API_URL || 'http://127.0.0.1:8000');

export interface DashboardMetrics {
  total_failed_volume: number;
  total_failed_count: number;
  total_revenue_recovered: number;
  total_recovered_count: number;
  recovery_rate: number;
  active_escalations_count: number;
  ai_uplift_percentage: number;
  by_failure_category: Record<string, number>;
  by_recovery_action: Record<string, number>;
  revenue_at_risk?: number;
  recoverable_revenue?: number;
  revenue_recovered?: number;
  failed_payments_count?: number;
  abandoned_checkouts_count?: number;
  active_recoveries_count?: number;
  escalations_count?: number;
  revenue_over_time?: Array<{
    timestamp: string;
    ai_recovered: number;
    baseline_recovered: number;
    at_risk: number;
  }>;
  baseline_vs_ai?: {
    baseline_recovery_rate: number;
    ai_recovery_rate: number;
    baseline_volume: number;
    ai_volume: number;
    uplift_pct: number;
  };
  recovery_probability_distribution?: Array<{
    range: string;
    count: number;
  }>;
  abandoned_checkout_revenue?: number;
  recoverable_abandonment_revenue?: number;
  recovered_abandonment_revenue?: number;
}

export interface Transaction {
  transaction_id: string;
  customer_id?: string;
  merchant_id?: string;
  amount: number;
  currency?: string;
  payment_method: string;
  gateway?: string;
  status: string;
  failure_code?: string;
  risk_score?: number;
  attempt_count?: number;
  attempt_number?: number;
  created_at?: string;
  updated_at?: string;
  simulated?: boolean;
  predicted_recovery_prob?: number;
  recommended_action?: string;
  revenue_recovered?: number;
}

export interface TransactionListResponse {
  transactions: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

export interface CandidateAction {
  action: string;
  probability: number;
  expected_recovery_value: number;
  permitted: boolean;
  policy_outcome: string;
  rule_id?: string;
  rejection_reason?: string;
  reason?: string;
}

export interface AgentDecisionResponse {
  transaction_id: string;
  selected_action: string;
  recovery_probability: number;
  expected_recovery_value: number;
  reasoning_summary: string;
  policy_status: string;
  candidates: CandidateAction[];
  fallback_used: boolean;
}

export interface RecoveryRunResponse {
  transaction_id: string;
  selected_action: string;
  monitoring_outcome: string;
  recovery_probability: number;
  expected_recovery_value: number;
  execution_result: Record<string, any>;
  policy_decision: Record<string, any>;
  errors: string[];
}

export interface AuditEvent {
  audit_id: string;
  transaction_id: string;
  timestamp: string;
  event_type: string;
  actor: string;
  input_summary?: Record<string, any>;
  root_cause?: any;
  recovery_probability?: number;
  candidate_actions?: any[];
  selected_action?: string;
  expected_value?: number;
  policy_result?: string;
  policy_rule?: string;
  execution_result?: Record<string, any>;
  revenue_recovered?: number;
  model_version?: string;
  agent_version?: string;
  hash: string;
  previous_hash?: string;
}

export interface AuditListResponse {
  total: number;
  limit: number;
  offset: number;
  actors: string[];
  events: AuditEvent[];
  verified_integrity: boolean;
}

export interface SimulationComparisonMetrics {
  total_transactions: number;
  failed_transactions: number;
  recoverable_opportunities: number;
  revenue_at_risk: number;
  recovered_revenue: number;
  recovered_count: number;
  recovery_rate: number;
  average_recovery_time_ms: number;
  retry_attempts: number;
  blocked_actions: number;
  escalations: number;
  unnecessary_intervention_rate: number;
}

export interface TransactionComparisonTrace {
  transaction_id: string;
  amount: number;
  currency?: string;
  payment_method: string;
  failure_code: string;
  risk_score: number;
  customer_id: string;
  customer_history?: any;
  payment_context?: any;
  recoverable: boolean;
  baseline: {
    action: string;
    status: string;
    recovered: boolean;
    recovered_amount: number;
    time_ms: number;
    unnecessary: boolean;
  };
  ai: {
    action: string;
    root_cause: string;
    recovery_probability: number;
    policy_decision: string;
    policy_rule_id: string;
    status: string;
    recovered: boolean;
    recovered_amount: number;
    time_ms: number;
    blocked: boolean;
    escalated: boolean;
    unnecessary: boolean;
    audit_hash: string;
  };
  ai_won: boolean;
}

export interface SimulationRunResponse {
  run_id: string;
  seed: number;
  transaction_count: number;
  recovered_count: number;
  recovered_revenue: number;
  recovery_rate: number;
  status: string;
  created_at?: string;
  scenario?: string;
  total_transactions?: number;
  failed_transactions?: number;
  recoverable_opportunities?: number;
  revenue_at_risk?: number;
  baseline_metrics?: SimulationComparisonMetrics;
  ai_metrics?: SimulationComparisonMetrics;
  uplift?: {
    revenue_gain: number;
    revenue_uplift_pct: number;
    recovery_rate_diff_pct: number;
    intervention_reduction_pct: number;
  };
  category_breakdown?: Record<string, any>;
  ai_actions_distribution?: Record<string, number>;
  transactions: TransactionComparisonTrace[];
}

export interface CheckoutSession {
  session_id: string;
  customer_id: string;
  cart_value: number;
  current_stage: string;
  created_at: string;
  updated_at: string;
  checkout_duration: number;
  device: string;
  payment_method: string;
  previous_purchases: number;
  previous_abandonment_count: number;
  risk_score: number;
  dnd_enabled: boolean;
  customer_tier: string;
  abandonment_detected: boolean;
  abandonment_reason?: string;
  abandonment_detected_at?: string;
  dropoff_stage?: string;
  recovery_action?: string;
  recovery_probability?: number;
  expected_recovery_value?: number;
  policy_outcome?: string;
  policy_rule_id?: string;
  recovered: boolean;
  recovered_amount: number;
  audit_hash?: string;
  events_count?: number;
}

export interface CheckoutRecoveryResponse {
  session_id: string;
  cart_value: number;
  dropoff_stage?: string;
  selected_action: string;
  recovery_probability: number;
  expected_recovery_value: number;
  policy_outcome: string;
  policy_rule_id: string;
  candidates: Array<{
    action: string;
    probability: number;
    expected_recovery_value: number;
    permitted: boolean;
    policy_outcome: string;
    rule_id: string;
    reason?: string;
  }>;
  execution: Record<string, any>;
  recovered: boolean;
  recovered_amount: number;
  audit_hash?: string;
  session: CheckoutSession;
}

// HTTP request helper
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    if (!res.ok) {
      const errorBody = await res.text();
      let parsed = errorBody;
      try {
        parsed = JSON.parse(errorBody);
      } catch {
        // ignore
      }
      throw new Error(
        typeof parsed === 'object' && (parsed as any).detail
          ? (parsed as any).detail
          : `HTTP ${res.status}: ${res.statusText}`
      );
    }

    return await res.json();
  } catch (err: any) {
    console.error(`API Error on [${url}]:`, err);
    throw err;
  }
}

// API Methods
export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  return request<DashboardMetrics>('/api/dashboard/metrics');
}

export async function getTransactions(params: {
  status?: string;
  failure_code?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<TransactionListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.append('status', params.status);
  if (params.failure_code) query.append('failure_code', params.failure_code);
  if (params.limit) query.append('limit', String(params.limit));
  if (params.offset) query.append('offset', String(params.offset));

  const qs = query.toString() ? `?${query.toString()}` : '';
  return request<TransactionListResponse>(`/api/transactions${qs}`);
}

export async function getTransaction(id: string): Promise<Transaction> {
  return request<Transaction>(`/api/transactions/${encodeURIComponent(id)}`);
}

export async function getAgentDecision(id: string): Promise<AgentDecisionResponse> {
  return request<AgentDecisionResponse>(`/api/agent/decision/${encodeURIComponent(id)}`);
}

export async function runRecovery(id: string): Promise<RecoveryRunResponse> {
  return request<RecoveryRunResponse>(`/api/recovery/run/${encodeURIComponent(id)}`, {
    method: 'POST',
  });
}

export async function getTransactionAuditTrail(id: string): Promise<{
  transaction_id: string;
  count: number;
  verified_integrity: boolean;
  events: AuditEvent[];
}> {
  return request(`/api/audit/${encodeURIComponent(id)}`);
}

export async function getAllAuditEvents(params: {
  transaction_id?: string;
  actor?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params.transaction_id) query.append('transaction_id', params.transaction_id);
  if (params.actor) query.append('actor', params.actor);
  if (params.event_type) query.append('event_type', params.event_type);
  if (params.limit) query.append('limit', String(params.limit));
  if (params.offset) query.append('offset', String(params.offset));

  const qs = query.toString() ? `?${query.toString()}` : '';
  return request<AuditListResponse>(`/api/audit${qs}`);
}

export async function runSimulation(params: {
  transaction_count?: number;
  seed?: number;
  scenario?: string;
} = {}): Promise<SimulationRunResponse> {
  return request<SimulationRunResponse>('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify({
      transaction_count: params.transaction_count || 20,
      seed: params.seed ?? 42,
      scenario: params.scenario || 'mixed_failures',
    }),
  });
}

export async function getSimulation(runId: string): Promise<SimulationRunResponse> {
  return request<SimulationRunResponse>(`/api/simulation/${encodeURIComponent(runId)}`);
}

export async function getSimulationRuns(): Promise<any[]> {
  return request<any[]>('/api/simulation/runs');
}

export async function getSimulationTransaction(runId: string, txnId: string): Promise<TransactionComparisonTrace> {
  return request<TransactionComparisonTrace>(`/api/simulation/${encodeURIComponent(runId)}/transaction/${encodeURIComponent(txnId)}`);
}

// Phase 17: Checkout Abandonment Client Methods
export async function getCheckoutSessions(params: {
  stage?: string;
  abandoned_only?: boolean;
  limit?: number;
} = {}): Promise<{ total: number; sessions: CheckoutSession[]; metrics: Record<string, number> }> {
  const query = new URLSearchParams();
  if (params.stage) query.append('stage', params.stage);
  if (params.abandoned_only) query.append('abandoned_only', 'true');
  if (params.limit) query.append('limit', String(params.limit));
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request<{ total: number; sessions: CheckoutSession[]; metrics: Record<string, number> }>(`/api/checkout/sessions${qs}`);
}

export async function getCheckoutSession(id: string): Promise<{ session: CheckoutSession; events: any[] }> {
  return request<{ session: CheckoutSession; events: any[] }>(`/api/checkout/sessions/${encodeURIComponent(id)}`);
}

export async function runCheckoutRecovery(id: string, forceAction?: string): Promise<CheckoutRecoveryResponse> {
  return request<CheckoutRecoveryResponse>(`/api/checkout/recover/${encodeURIComponent(id)}`, {
    method: 'POST',
    body: JSON.stringify(forceAction ? { force_action: forceAction } : {}),
  });
}

export async function detectCheckoutAbandonments(): Promise<{ detected_count: number; abandoned_sessions: any[]; metrics: any }> {
  return request<{ detected_count: number; abandoned_sessions: any[]; metrics: any }>('/api/checkout/detect', {
    method: 'POST',
  });
}

export async function getModelPerformance(): Promise<any> {
  return request<any>('/api/model/performance');
}

export async function orchestrateWorkflow(payload: any): Promise<any> {
  return request<any>('/api/orchestrate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function resetDemo(reseed: boolean = true): Promise<any> {
  return request<any>(`/api/demo/reset?reseed=${reseed}`, {
    method: 'POST',
  });
}

export async function seedDemo(): Promise<any> {
  return request<any>('/api/demo/seed', {
    method: 'POST',
  });
}

export async function getPolicies(): Promise<{ policies: any[] }> {
  return request<{ policies: any[] }>('/api/policies');
}

export async function ingestEvent(event: any): Promise<any> {
  return request<any>('/api/events', {
    method: 'POST',
    body: JSON.stringify(event),
  });
}

export async function analyzeRootCause(payload: any): Promise<any> {
  return request<any>('/api/analyze/root-cause', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function predictActions(transaction: any): Promise<any> {
  return request<any>('/api/predict/actions', {
    method: 'POST',
    body: JSON.stringify({ transaction }),
  });
}

// Formatting Utilities
export function formatINR(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(num: number | undefined | null): string {
  if (num === undefined || num === null || isNaN(num)) return '0';
  return new Intl.NumberFormat('en-IN').format(num);
}

export function formatPercent(rate: number | undefined | null): string {
  if (rate === undefined || rate === null || isNaN(rate)) return '0.0%';
  const val = rate <= 1 ? rate * 100 : rate;
  return `${val.toFixed(1)}%`;
}

export function getStatusBadge(status: string): { bg: string; text: string; border: string } {
  const s = (status || '').toUpperCase();
  switch (s) {
    case 'SUCCESS':
    case 'RECOVERED':
      return { bg: 'bg-emerald-950/60', text: 'text-emerald-400', border: 'border-emerald-500/30' };
    case 'FAILED':
      return { bg: 'bg-rose-950/60', text: 'text-rose-400', border: 'border-rose-500/30' };
    case 'ESCALATED':
      return { bg: 'bg-amber-950/60', text: 'text-amber-400', border: 'border-amber-500/30' };
    case 'PROCESSING':
    case 'INITIATED':
      return { bg: 'bg-indigo-950/60', text: 'text-indigo-400', border: 'border-indigo-500/30' };
    case 'PENDING':
    case 'WAIT':
      return { bg: 'bg-purple-950/60', text: 'text-purple-400', border: 'border-purple-500/30' };
    default:
      return { bg: 'bg-slate-900/80', text: 'text-slate-300', border: 'border-slate-700' };
  }
}

export function getActionBadge(action: string): { bg: string; text: string; border: string } {
  const a = (action || '').toUpperCase();
  switch (a) {
    case 'RETRY_PAYMENT':
      return { bg: 'bg-indigo-950/50', text: 'text-indigo-300', border: 'border-indigo-500/30' };
    case 'SWITCH_PAYMENT_METHOD':
      return { bg: 'bg-cyan-950/50', text: 'text-cyan-300', border: 'border-cyan-500/30' };
    case 'SEND_RECOVERY_LINK':
    case 'SEND_NOTIFICATION':
      return { bg: 'bg-emerald-950/50', text: 'text-emerald-300', border: 'border-emerald-500/30' };
    case 'OFFER_INCENTIVE':
    case 'DYNAMIC_DISCOUNT':
      return { bg: 'bg-amber-950/50', text: 'text-amber-300', border: 'border-amber-500/30' };
    case 'ESCALATE':
    case 'ESCALATE_TO_SUPPORT':
      return { bg: 'bg-rose-950/50', text: 'text-rose-300', border: 'border-rose-500/30' };
    case 'STOP':
      return { bg: 'bg-slate-900', text: 'text-slate-400', border: 'border-slate-700' };
    default:
      return { bg: 'bg-slate-900', text: 'text-slate-300', border: 'border-slate-800' };
  }
}
