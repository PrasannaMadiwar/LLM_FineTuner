'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { HealthResponse, ReadinessResponse } from '@/lib/types';
import {
  Server,
  Database,
  Activity,
  User as UserIcon,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const checkStatus = async () => {
    try {
      setLoading(true);
      const [hRes, rRes] = await Promise.all([
        api.getHealth().catch(() => ({ status: 'unavailable' })),
        api.getReady().catch(() => ({ database: 'unavailable', redis: 'unavailable' })),
      ]);
      setHealth(hRes);
      setReadiness(rRes);
    } catch (err) {
      console.warn('Status check failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.getHealth().catch(() => ({ status: 'unavailable' })),
      api.getReady().catch(() => ({ database: 'unavailable', redis: 'unavailable' })),
    ]).then(([hRes, rRes]) => {
      if (mounted) {
        setHealth(hRes);
        setReadiness(rRes);
        setLoading(false);
      }
    }).catch(() => {
      if (mounted) setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:18000/api/v1';

  return (
    <div className="max-w-4xl space-y-6 animate-in fade-in duration-200">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Platform Settings
        </h1>
        <p className="text-xs text-slate-500">
          Inspect API endpoints, environment connection status, and active user session.
        </p>
      </div>

      {/* API & Service Health Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-teal-600" />
            <h2 className="text-sm font-bold text-slate-900">
              Backend Service Readiness
            </h2>
          </div>
          <button
            onClick={checkStatus}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 flex items-center justify-between">
            <div>
              <span className="text-slate-400 block font-semibold text-[10px] uppercase">
                FastAPI Health
              </span>
              <span className="font-bold text-slate-900 capitalize">
                {health?.status || 'Unknown'}
              </span>
            </div>
            <CheckCircle2
              className={`w-4 h-4 ${
                health?.status === 'ok' ? 'text-emerald-500' : 'text-slate-300'
              }`}
            />
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 flex items-center justify-between">
            <div>
              <span className="text-slate-400 block font-semibold text-[10px] uppercase">
                PostgreSQL DB
              </span>
              <span className="font-bold text-slate-900 capitalize">
                {readiness?.database || 'Unknown'}
              </span>
            </div>
            <Database
              className={`w-4 h-4 ${
                readiness?.database === 'ok' ? 'text-emerald-500' : 'text-slate-300'
              }`}
            />
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 flex items-center justify-between">
            <div>
              <span className="text-slate-400 block font-semibold text-[10px] uppercase">
                Redis Task Broker
              </span>
              <span className="font-bold text-slate-900 capitalize">
                {readiness?.redis || 'Unknown'}
              </span>
            </div>
            <Activity
              className={`w-4 h-4 ${
                readiness?.redis === 'ok' ? 'text-emerald-500' : 'text-slate-300'
              }`}
            />
          </div>
        </div>

        <div className="pt-2 text-xs text-slate-500 flex items-center gap-2">
          <span className="font-semibold text-slate-700">API Endpoint:</span>
          <code className="bg-slate-100 px-2 py-0.5 rounded text-teal-700 font-mono">
            {apiBaseUrl}
          </code>
        </div>
      </div>

      {/* User Session Profile */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <UserIcon className="w-4 h-4 text-teal-600" />
          <h2 className="text-sm font-bold text-slate-900">
            User Session Details
          </h2>
        </div>

        {user ? (
          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">User ID:</span>
              <span className="font-mono font-semibold text-slate-900">
                {user.id}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Email:</span>
              <span className="font-semibold text-slate-900">{user.email}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Role:</span>
              <span className="font-semibold text-slate-900 capitalize">
                {user.role}
              </span>
            </div>
            <div className="pt-2">
              <button
                onClick={logout}
                className="px-4 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 font-semibold text-xs rounded-xl border border-rose-200 transition-all"
              >
                Sign Out
              </button>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">
            No active user session found. Please sign in via the header button.
          </p>
        )}
      </div>
    </div>
  );
}
