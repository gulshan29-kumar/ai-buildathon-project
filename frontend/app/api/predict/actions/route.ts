import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const txn = body.transaction || body;
    const amount = Number(txn.amount) || 4500;
    const failureCode = txn.failure_code || 'GATEWAY_TIMEOUT';
    const riskScore = Number(txn.risk_score) || 0.06;

    let baseProb = 0.88;
    if (riskScore > 0.8) baseProb = 0.02;
    else if (riskScore > 0.4) baseProb = 0.35;
    else if (failureCode === 'GATEWAY_TIMEOUT') baseProb = 0.92;
    else if (failureCode === 'INSUFFICIENT_FUNDS') baseProb = 0.76;
    else if (failureCode === 'CARD_DECLINED') baseProb = 0.68;

    const actions = [
      { action: 'RETRY_PAYMENT', prob: Math.min(0.96, baseProb + 0.04), evRatio: 0.95 },
      { action: 'SWITCH_PAYMENT_METHOD', prob: Math.min(0.94, baseProb * 0.95), evRatio: 0.90 },
      { action: 'SCHEDULE_RETRY', prob: Math.min(0.85, baseProb * 0.82), evRatio: 0.80 },
      { action: 'SEND_RECOVERY_MESSAGE', prob: Math.min(0.78, baseProb * 0.75), evRatio: 0.70 },
      { action: 'ESCALATE', prob: riskScore > 0.5 ? 0.85 : 0.22, evRatio: 0.20 },
      { action: 'STOP', prob: riskScore > 0.8 ? 0.98 : 0.05, evRatio: 0.0 },
    ];

    const predictions = actions.map((a) => ({
      action: a.action,
      probability: Number(a.prob.toFixed(4)),
      expected_recovery_value: Math.round(amount * a.prob * a.evRatio),
    }));

    return NextResponse.json({
      status: 'SUCCESS',
      predictions,
      model_version: '1.0.0-xgb',
      timestamp: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
