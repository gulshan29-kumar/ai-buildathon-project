import { NextRequest, NextResponse } from 'next/server';
import {
  MOCK_DASHBOARD_METRICS,
  MOCK_CURATED_SCENARIOS,
  getMockCuratedScenarioTrace,
  MOCK_TRANSACTIONS,
  MOCK_BASELINE_COMPARISON,
  MOCK_MODEL_PERFORMANCE_REPORT,
  MOCK_LATEST_BENCHMARK,
  MOCK_SUBSCRIPTIONS,
  MOCK_SUBSCRIPTION_METRICS,
  MOCK_SIMULATION_RUN,
  MOCK_CHECKOUT_SESSIONS,
  MOCK_POLICIES,
} from '@/lib/mockFallback';

export const dynamic = 'force-dynamic';

async function handleApi(req: NextRequest, { params }: { params: { slug: string[] } }) {
  const slugPath = (params.slug || []).join('/');
  const endpoint = `/api/${slugPath}`;
  const search = req.nextUrl.search || '';

  // If external backend configured, attempt proxying first
  const serverBackend = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;
  if (serverBackend) {
    try {
      const cleanUrl = serverBackend.replace(/\/+$/, '');
      const targetUrl = `${cleanUrl}${endpoint}${search}`;
      const headers = new Headers(req.headers);
      headers.delete('host');

      let body: any = undefined;
      if (req.method !== 'GET' && req.method !== 'HEAD') {
        body = await req.arrayBuffer();
      }

      const res = await fetch(targetUrl, {
        method: req.method,
        headers,
        body,
        cache: 'no-store',
      });

      if (res.ok) {
        const data = await res.arrayBuffer();
        return new NextResponse(data, {
          status: res.status,
          headers: {
            'content-type': res.headers.get('content-type') || 'application/json',
          },
        });
      }
    } catch {
      // Backend unreachable; gracefully fallback to simulation mode below
    }
  }

  // Dashboard Metrics
  if (endpoint.startsWith('/api/dashboard/metrics')) {
    return NextResponse.json(MOCK_DASHBOARD_METRICS);
  }

  // Curated Scenarios
  if (endpoint === '/api/scenarios') {
    return NextResponse.json({
      scenarios: MOCK_CURATED_SCENARIOS,
      total: MOCK_CURATED_SCENARIOS.length,
    });
  }

  if (endpoint.startsWith('/api/scenarios/run-all')) {
    const traces = MOCK_CURATED_SCENARIOS.map((s) => getMockCuratedScenarioTrace(s.scenario_id));
    return NextResponse.json({
      total_scenarios: 8,
      executed_count: 8,
      recovered_count: 5,
      recovery_rate: 62.5,
      total_revenue_at_risk: 138847.0,
      total_revenue_recovered: 23697.0,
      prevented_fraud_losses: 85000.0,
      timestamp: new Date().toISOString(),
      traces,
    });
  }

  if (endpoint.startsWith('/api/scenarios/reset')) {
    const traces = MOCK_CURATED_SCENARIOS.map((s) => getMockCuratedScenarioTrace(s.scenario_id));
    return NextResponse.json({
      status: 'reset_successful',
      summary: {
        total_scenarios: 8,
        executed_count: 8,
        recovered_count: 5,
        recovery_rate: 62.5,
        total_revenue_at_risk: 138847.0,
        total_revenue_recovered: 23697.0,
        prevented_fraud_losses: 85000.0,
        timestamp: new Date().toISOString(),
        traces,
      },
    });
  }

  if (endpoint.startsWith('/api/scenarios/')) {
    const scenarioId = params.slug[1];
    return NextResponse.json(getMockCuratedScenarioTrace(scenarioId));
  }

  // Transactions
  if (endpoint.startsWith('/api/transactions')) {
    if (endpoint === '/api/transactions') {
      return NextResponse.json({
        transactions: MOCK_TRANSACTIONS,
        total: MOCK_TRANSACTIONS.length,
        limit: 10,
        offset: 0,
      });
    }
    const txnId = params.slug[1];
    const txn = MOCK_TRANSACTIONS.find((t) => t.transaction_id === txnId) || MOCK_TRANSACTIONS[0];
    return NextResponse.json(txn);
  }

  // Agent Decision
  if (endpoint.startsWith('/api/agent/decision/')) {
    const firstScenario = MOCK_CURATED_SCENARIOS[0];
    return NextResponse.json({
      transaction_id: params.slug[2] || 'txn_gateway_timeout_001',
      selected_action: firstScenario.expected_action,
      recovery_probability: 0.88,
      expected_recovery_value: Math.round(firstScenario.amount * 0.88),
      reasoning_summary: firstScenario.description,
      reasoning: firstScenario.description,
      policy_status: 'PERMITTED',
      policy_rule_id: (firstScenario as any).expected_rule_id || 'POL-004',
      evaluation_latency_ms: 4.2,
      candidates: [
        {
          action: firstScenario.expected_action,
          probability: 0.88,
          expected_recovery_value: Math.round(firstScenario.amount * 0.88),
          permitted: true,
          policy_outcome: 'PERMITTED',
          rule_id: (firstScenario as any).expected_rule_id || 'POL-004',
        },
      ],
      fallback_used: false,
    });
  }

  // Recovery Execution
  if (endpoint.startsWith('/api/recovery/run/')) {
    return NextResponse.json({
      transaction_id: params.slug[2] || 'txn_gateway_timeout_001',
      selected_action: 'RETRY_PAYMENT',
      monitoring_outcome: 'SUCCESS',
      recovery_probability: 0.88,
      expected_recovery_value: 3499.0,
      execution_result: { status: 'SUCCESS', rrn: 'RRN-SIM-829104819' },
      policy_decision: { outcome: 'PERMITTED', rule_id: 'POL-004' },
      errors: [],
    });
  }

  // Audit
  if (endpoint.startsWith('/api/audit')) {
    const trace = getMockCuratedScenarioTrace('scenario_gateway_timeout');
    return NextResponse.json({
      transaction_id: 'txn_gateway_timeout_001',
      count: trace.audit_trail.total_events,
      verified_integrity: true,
      events: trace.audit_trail.events,
    });
  }

  // Baseline Benchmark
  if (endpoint.startsWith('/api/benchmark/latest') || endpoint.startsWith('/api/benchmark/run')) {
    return NextResponse.json(MOCK_LATEST_BENCHMARK);
  }

  if (endpoint.startsWith('/api/benchmark/history')) {
    return NextResponse.json([
      {
        benchmark_id: 'bench_20260905_142925',
        timestamp: new Date().toISOString(),
        seed: 42,
        total_transactions: 100,
        revenue_at_risk: 425000,
        ai_recovery_rate: 0.74,
        ai_revenue_recovered: 314500,
        fixed_retry_rate: 0.24,
      },
    ]);
  }

  if (endpoint.startsWith('/api/baseline-comparison')) {
    return NextResponse.json(MOCK_BASELINE_COMPARISON);
  }

  // Subscriptions
  if (endpoint.startsWith('/api/subscriptions')) {
    if (params.slug.length >= 2 && !params.slug[1].startsWith('recover')) {
      const sub = MOCK_SUBSCRIPTIONS.find((s) => s.subscription_id === params.slug[1]) || MOCK_SUBSCRIPTIONS[0];
      return NextResponse.json(sub);
    }
    return NextResponse.json({
      subscriptions: MOCK_SUBSCRIPTIONS,
      total: MOCK_SUBSCRIPTIONS.length,
      count: MOCK_SUBSCRIPTIONS.length,
      metrics: MOCK_SUBSCRIPTION_METRICS,
    });
  }

  // Simulation
  if (endpoint.startsWith('/api/simulation/runs')) {
    return NextResponse.json([MOCK_SIMULATION_RUN]);
  }

  if (endpoint.startsWith('/api/simulation')) {
    return NextResponse.json(MOCK_SIMULATION_RUN);
  }

  // Checkout Abandonment
  if (endpoint.startsWith('/api/checkout/detect')) {
    return NextResponse.json({
      detected_count: 2,
      abandoned_sessions: MOCK_CHECKOUT_SESSIONS,
      metrics: { total_abandoned: 2, recoverable_value: 12489 },
    });
  }

  if (endpoint.startsWith('/api/checkout/recover')) {
    return NextResponse.json({
      session_id: 'chk_sess_001',
      action_executed: 'SEND_WHATSAPP_LINK',
      channel: 'WHATSAPP_INTENT',
      status: 'SUCCESS',
      recovered: true,
      recovered_value: 3499.0,
      policy_decision: { outcome: 'PERMITTED', rule_id: 'POL-007' },
      audit_hash: 'h_chk_001',
    });
  }

  if (endpoint.startsWith('/api/checkout/sessions')) {
    return NextResponse.json({
      total: MOCK_CHECKOUT_SESSIONS.length,
      sessions: MOCK_CHECKOUT_SESSIONS,
      metrics: { total_abandoned: 28, recoverable_revenue: 84500, recovered_revenue: 62100 },
    });
  }

  // Policies
  if (endpoint.startsWith('/api/policies')) {
    return NextResponse.json({ policies: MOCK_POLICIES });
  }

  // Agent Orchestrate
  if (endpoint.startsWith('/api/orchestrate')) {
    return NextResponse.json({
      status: 'COMPLETED',
      selected_action: 'RETRY_PAYMENT',
      monitoring_outcome: 'SUCCESS',
      recovery_probability: 0.92,
      expected_recovery_value: 4140.0,
      policy_decision: { outcome: 'PERMITTED', rule_id: 'POL-004' },
      execution_result: { status: 'SUCCESS', rrn: 'RRN-SIM-829104819' },
      nodes_executed: ['EVENT', 'ROOT_CAUSE', 'ML', 'ACTIONS', 'POLICY', 'DECISION', 'EXECUTION', 'RESULT'],
      latency_ms: 38,
    });
  }

  // Demo
  if (endpoint.startsWith('/api/demo')) {
    return NextResponse.json({ status: 'success', message: 'Demo sandbox initialized.' });
  }

  return NextResponse.json({ status: 'OK', simulated: true });
}

export async function GET(req: NextRequest, ctx: { params: { slug: string[] } }) {
  return handleApi(req, ctx);
}

export async function POST(req: NextRequest, ctx: { params: { slug: string[] } }) {
  return handleApi(req, ctx);
}

export async function PUT(req: NextRequest, ctx: { params: { slug: string[] } }) {
  return handleApi(req, ctx);
}

export async function DELETE(req: NextRequest, ctx: { params: { slug: string[] } }) {
  return handleApi(req, ctx);
}
