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
  Activity,
} from 'lucide-react';

const NAV_ITEMS = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Fine-Tune', href: '/fine-tune', icon: Sparkles },
  { name: 'Datasets', href: '/datasets', icon: Database },
  { name: 'Training Jobs', href: '/jobs', icon: Cpu },
  { name: 'Models', href: '/models', icon: Boxes },
  { name: 'Playground', href: '/playground', icon: PlayCircle },
  { name: 'Artifacts', href: '/artifacts', icon: FolderDown },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 border-r border-[#2d2d30] bg-[#181818] flex flex-col h-screen sticky top-0">
      {/* Brand Header */}
      <div className="p-5 border-b border-[#2d2d30] flex items-center gap-3">
        <div className="h-9 w-9 rounded-md bg-[#007acc] flex items-center justify-center text-white font-semibold">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-bold text-base text-white leading-none">
            FineTuner
          </h1>
          <span className="text-xs text-[#75beff] font-medium tracking-wide">
            MODEL WORKSPACE
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 border-l-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-[#37373d] text-white border-[#007acc] font-semibold'
                  : 'text-white border-transparent hover:bg-[#2d2d30] hover:text-white'
              }`}
            >
              <Icon
                className={`w-4 h-4 ${
                  isActive ? 'text-[#75beff]' : 'text-white'
                }`}
              />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Engine Status Banner */}
      <div className="p-4 border-t border-[#2d2d30] bg-[#181818]">
        <div className="flex items-center gap-2.5 text-xs text-white font-medium">
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
