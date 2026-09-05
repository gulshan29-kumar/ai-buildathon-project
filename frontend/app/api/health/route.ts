import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'razorrecover-ai-backend',
    version: '1.0.0',
    environment: 'simulation',
    database: 'connected',
    ml_model: '1.0.0-xgb',
    policy_engine: 'active',
    simulator: 'ready',
    timestamp: new Date().toISOString(),
  });
}
