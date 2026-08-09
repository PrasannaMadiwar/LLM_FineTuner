import React from 'react';
import { TrainingJobStatus } from '@/lib/types';

interface BadgeProps {
  status: TrainingJobStatus | string;
  className?: string;
}

export function Badge({ status, className = '' }: BadgeProps) {
  let style = 'bg-slate-100 text-slate-700 border-slate-200';

  switch (status.toLowerCase()) {
    case 'completed':
      style = 'bg-emerald-50 text-emerald-700 border-emerald-200';
      break;
    case 'training':
    case 'starting':
    case 'uploading':
    case 'gpu_ready':
      style = 'bg-teal-50 text-teal-700 border-teal-200 animate-pulse';
      break;
    case 'queued':
    case 'preparing':
    case 'waiting_gpu':
      style = 'bg-amber-50 text-amber-700 border-amber-200';
      break;
    case 'failed':
      style = 'bg-rose-50 text-rose-700 border-rose-200';
      break;
    case 'cancelled':
      style = 'bg-slate-100 text-slate-600 border-slate-200';
      break;
    default:
      break;
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border tracking-tight ${style} ${className}`}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
}
