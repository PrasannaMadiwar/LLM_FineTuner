'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Sparkles,
  Database,
  Cpu,
  Boxes,
  PlayCircle,
  FolderDown,
  Settings,
  Activity,
} from 'lucide-react';

const NAV_ITEMS = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Fine-Tune', href: '/fine-tune', icon: Sparkles },
  { name: 'Datasets', href: '/datasets', icon: Database },
  { name: 'Training Jobs', href: '/jobs', icon: Cpu },
  { name: 'Models', href: '/models', icon: Boxes },
  { name: 'Playground', href: '/playground', icon: PlayCircle },
  { name: 'Artifacts', href: '/artifacts', icon: FolderDown },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-[var(--border)] bg-[var(--panel)] flex flex-col h-screen sticky top-0">
      {/* Brand Header */}
      <div className="p-6 border-b border-[var(--border)] flex items-center gap-3">
        <div className="h-9 w-9 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-sm font-semibold">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-bold text-base tracking-tight text-slate-900 leading-none">
            FineTuner
          </h1>
          <span className="text-xs text-teal-600 font-medium tracking-wide">
            Enterprise SaaS
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-teal-50 text-teal-700 font-semibold shadow-xs'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Icon
                className={`w-4 h-4 ${
                  isActive ? 'text-teal-600' : 'text-slate-400'
                }`}
              />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Engine Status Banner */}
      <div className="p-4 border-t border-[var(--border)] bg-slate-50/50">
        <div className="flex items-center gap-2.5 text-xs text-slate-600 font-medium">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <Activity className="w-3.5 h-3.5 text-slate-400" />
          <span>GPU Orchestrator Ready</span>
        </div>
      </div>
    </aside>
  );
}
