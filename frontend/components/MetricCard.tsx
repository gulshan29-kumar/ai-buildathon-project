'use client';

import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  delta?: string;
  deltaType?: 'positive' | 'negative' | 'neutral' | 'alert';
  icon: LucideIcon;
  variant?: 'default' | 'emerald' | 'amber' | 'rose' | 'indigo' | 'cyan';
  loading?: boolean;
}

export default function MetricCard({
  title,
  value,
  subtitle,
  delta,
  deltaType = 'positive',
  icon: Icon,
  variant = 'default',
  loading = false,
}: MetricCardProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card animate-pulse space-y-3">
        <div className="flex justify-between items-center">
          <div className="h-3 w-24 bg-slate-800 rounded"></div>
          <div className="h-8 w-8 bg-slate-800 rounded-lg"></div>
        </div>
        <div className="h-7 w-32 bg-slate-800 rounded"></div>
        <div className="h-3 w-20 bg-slate-800 rounded"></div>
      </div>
    );
  }

  const getVariantStyles = () => {
    switch (variant) {
      case 'emerald':
        return {
          iconBg: 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30',
          borderHover: 'hover:border-emerald-500/40',
          accentGlow: 'hover:shadow-fintech-glow-emerald',
        };
      case 'rose':
        return {
          iconBg: 'bg-rose-950/60 text-rose-400 border border-rose-500/30',
          borderHover: 'hover:border-rose-500/40',
          accentGlow: 'hover:shadow-fintech-glow-rose',
        };
      case 'amber':
        return {
          iconBg: 'bg-amber-950/60 text-amber-400 border border-amber-500/30',
          borderHover: 'hover:border-amber-500/40',
          accentGlow: '',
        };
      case 'indigo':
        return {
          iconBg: 'bg-indigo-950/60 text-indigo-400 border border-indigo-500/30',
          borderHover: 'hover:border-indigo-500/40',
          accentGlow: 'hover:shadow-fintech-glow',
        };
      case 'cyan':
        return {
          iconBg: 'bg-cyan-950/60 text-cyan-400 border border-cyan-500/30',
          borderHover: 'hover:border-cyan-500/40',
          accentGlow: '',
        };
      default:
        return {
          iconBg: 'bg-slate-800/80 text-slate-300 border border-slate-700',
          borderHover: 'hover:border-slate-700',
          accentGlow: '',
        };
    }
  };

  const styles = getVariantStyles();

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-fintech-border bg-fintech-card/80 p-5 shadow-fintech-card transition-all duration-200 ${styles.borderHover} ${styles.accentGlow} glass-panel`}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</p>
          <p className="text-2xl font-bold tracking-tight text-white font-tabular">{value}</p>
        </div>
        <div className={`p-2.5 rounded-lg ${styles.iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>

      {(subtitle || delta) && (
        <div className="mt-3 flex items-center gap-2 pt-2 border-t border-slate-800/60 text-xs">
          {delta && (
            <span
              className={`inline-flex items-center gap-1 font-semibold text-[11px] px-1.5 py-0.5 rounded ${
                deltaType === 'positive'
                  ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/30'
                  : deltaType === 'negative'
                  ? 'bg-rose-950/80 text-rose-400 border border-rose-500/30'
                  : deltaType === 'alert'
                  ? 'bg-amber-950/80 text-amber-400 border border-amber-500/30'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {deltaType === 'positive' ? (
                <TrendingUp className="h-3 w-3" />
              ) : deltaType === 'negative' ? (
                <TrendingDown className="h-3 w-3" />
              ) : null}
              {delta}
            </span>
          )}
          {subtitle && <span className="text-slate-400 text-[11px] truncate">{subtitle}</span>}
        </div>
      )}
    </div>
  );
}
