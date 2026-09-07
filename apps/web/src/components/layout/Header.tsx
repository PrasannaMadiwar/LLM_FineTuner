'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { AuthModal } from './AuthModal';
import { LogOut, Sparkles, ShieldCheck } from 'lucide-react';

export function Header() {
  const { user, logout, openAuth } = useAuth();
  const router = useRouter();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <>
      <header className="h-14 border-b border-[var(--border)] bg-[var(--panel)] px-5 sm:px-8 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-[#252526] text-white border border-[#3e3e42] flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-[#75beff]" />
            Backend Verified & Connected
          </span>
        </div>

        <div className="flex items-center gap-4">
          <Link
            href="/fine-tune"
            className="inline-flex items-center gap-2 bg-[#007acc] hover:bg-[#005f9e] text-white text-xs font-semibold px-4 py-2 rounded-md transition-colors"
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
                      router.push('/');
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
              onClick={() => openAuth('login')}
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
