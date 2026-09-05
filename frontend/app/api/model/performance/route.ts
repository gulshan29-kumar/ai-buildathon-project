import { NextResponse } from 'next/server';
import reportData from '@/lib/evaluation_report.json';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json(reportData);
}
