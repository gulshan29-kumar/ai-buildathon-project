'use client';

import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  className?: string;
}

export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  onAction,
  secondaryLabel,
  onSecondary,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`rounded-xl border border-slate-800/80 bg-slate-900/40 p-8 text-center flex flex-col items-center justify-center max-w-md mx-auto my-6 ${className}`}
    >
      <div className="h-12 w-12 rounded-xl bg-slate-800/60 border border-slate-700/60 text-slate-400 flex items-center justify-center mb-3">
        <Icon className="h-6 w-6 text-slate-400" />
      </div>
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      <p className="text-xs text-slate-400 mt-1 max-w-xs leading-relaxed">
        {description}
      </p>

      {(actionLabel || secondaryLabel) && (
        <div className="flex items-center gap-2 mt-4">
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-sm transition active:scale-95"
            >
              {actionLabel}
            </button>
          )}
          {secondaryLabel && onSecondary && (
            <button
              onClick={onSecondary}
              className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-300 transition active:scale-95"
            >
              {secondaryLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
