'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { AuthModal } from './AuthModal';
import { User, LogOut, Sparkles, ExternalLink, ShieldCheck } from 'lucide-react';

export function Header() {
  const { user, logout, setIsAuthModalOpen } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const apiDocsUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace('/api/v1', '/docs') ||
    'http://localhost:18000/docs';

  return (
    <>
      <header className="h-16 border-b border-[var(--border)] bg-[var(--panel)] px-8 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
            Backend Verified & Connected
          </span>
        </div>

        <div className="flex items-center gap-4">
          <a
            href={apiDocsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-slate-500 hover:text-slate-900 flex items-center gap-1 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100"
          >
            <span>API Specs</span>
            <ExternalLink className="w-3 h-3" />
          </a>

          <Link
            href="/fine-tune"
            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-all shadow-xs"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Create Fine-Tune</span>
          </Link>

          {user ? (
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg border border-slate-200 transition-all"
              >
                <div className="w-5 h-5 rounded-full bg-teal-600 text-white flex items-center justify-center font-bold text-[10px]">
                  {user.email[0].toUpperCase()}
                </div>
                <span className="max-w-[120px] truncate">{user.email}</span>
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white border border-slate-200 rounded-xl shadow-lg py-1.5 z-50 text-xs">
                  <div className="px-3.5 py-2 border-b border-slate-100">
                    <p className="font-semibold text-slate-900 truncate">
                      {user.full_name || 'Authenticated User'}
                    </p>
                    <p className="text-slate-500 truncate">{user.email}</p>
                  </div>
                  <button
                    onClick={() => {
                      logout();
                      setDropdownOpen(false);
                    }}
                    className="w-full text-left px-3.5 py-2 text-rose-600 hover:bg-rose-50 flex items-center gap-2 font-medium"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => setIsAuthModalOpen(true)}
              className="text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-3.5 py-2 rounded-lg transition-all"
            >
              Sign In
            </button>
          )}
        </div>
      </header>

      <AuthModal />
    </>
  );
}
