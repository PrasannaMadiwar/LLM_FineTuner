'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { TrainingJob } from '@/lib/types';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  Cpu,
  Sparkles,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';

export default function TrainingJobsPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'completed' | 'failed'>('all');

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const res = await api.getJobs();
      setJobs(res.jobs || []);
    } catch (err) {
      console.warn('Failed to load training jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    api.getJobs().then((res) => {
      if (mounted) {
        setJobs(res.jobs || []);
        setLoading(false);
      }
    }).catch(() => {
      if (mounted) setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const filteredJobs = jobs.filter((job) => {
    if (filter === 'active')
      return !['completed', 'failed', 'cancelled'].includes(job.status);
    if (filter === 'completed') return job.status === 'completed';
    if (filter === 'failed') return job.status === 'failed';
    return true;
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Training Jobs
          </h1>
          <p className="text-xs text-slate-500">
            Monitor, inspect, and manage asynchronous fine-tuning runs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchJobs}
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          <Link
            href="/fine-tune"
            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all shadow-xs"
          >
            <Sparkles className="w-4 h-4" />
            <span>Create Fine-Tune</span>
          </Link>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2">
        {[
          { id: 'all', label: 'All Jobs' },
          { id: 'active', label: 'Active Runs' },
          { id: 'completed', label: 'Completed' },
          { id: 'failed', label: 'Failed / Cancelled' },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id as any)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              filter === f.id
                ? 'bg-teal-600 text-white border-teal-600 shadow-xs'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Jobs Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
            <span>Loading jobs...</span>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Cpu}
              title="No training jobs found"
              description="Start a new fine-tuning job to train custom LLM models."
              actionText="Create Fine-Tune"
              actionHref="/fine-tune"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Job ID</th>
                  <th className="px-5 py-3.5">Base Model</th>
                  <th className="px-5 py-3.5">Dataset</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Epochs</th>
                  <th className="px-5 py-3.5">Created</th>
                  <th className="px-5 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredJobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-4 font-mono font-medium text-slate-900">
                      {job.id.substring(0, 8)}...
                    </td>
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      {job.model_key}
                    </td>
                    <td className="px-5 py-4 text-slate-600 max-w-[180px] truncate">
                      {job.dataset_id}
                    </td>
                    <td className="px-5 py-4">
                      <Badge status={job.status} />
                    </td>
                    <td className="px-5 py-4 text-slate-600">
                      {job.training_config?.epochs || 3}
                    </td>
                    <td className="px-5 py-4 text-slate-400">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        href={`/jobs/${job.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 hover:bg-teal-100 px-3 py-1.5 rounded-lg transition-all"
                      >
                        <span>Monitor</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
