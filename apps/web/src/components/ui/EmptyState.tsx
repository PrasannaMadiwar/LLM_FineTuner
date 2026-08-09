import React from 'react';
import { LucideIcon } from 'lucide-react';
import Link from 'next/link';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionText?: string;
  actionHref?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionText,
  actionHref,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
      <div className="w-12 h-12 rounded-2xl bg-slate-100 border border-slate-200 text-slate-500 flex items-center justify-center mb-4">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-slate-900 mb-1">{title}</h3>
      <p className="text-xs text-slate-500 max-w-sm mb-6 leading-relaxed">
        {description}
      </p>
      {actionText && actionHref && (
        <Link
          href={actionHref}
          className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-all shadow-xs"
        >
          {actionText}
        </Link>
      )}
      {actionText && onAction && !actionHref && (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-all shadow-xs"
        >
          {actionText}
        </button>
      )}
    </div>
  );
}
