'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { TrainingJob, ModelDefinition } from '@/lib/types';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  Sparkles,
  Cpu,
  Boxes,
  Database,
  ArrowRight,
  Clock,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';

export default function Dashboard() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [models, setModels] = useState<ModelDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [jobsRes, modelsRes] = await Promise.all([
          api.getJobs().catch(() => ({ jobs: [] })),
          api.getModels().catch(() => ({ models: [] })),
        ]);
        setJobs(jobsRes.jobs || []);
        setModels(modelsRes.models || []);
      } catch (err: any) {
        setError(err.message || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const activeJobs = jobs.filter(
    (j) => !['completed', 'failed', 'cancelled'].includes(j.status)
  );
  const completedJobs = jobs.filter((j) => j.status === 'completed');

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Main Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-teal-950 p-8 text-white shadow-md border border-slate-800">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/20 text-teal-300 text-xs font-semibold border border-teal-500/30 mb-4">
            <Sparkles className="w-3.5 h-3.5" />
            <span>One-Click Fine-Tuning Platform</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-3">
            Fine-tune your model
          </h1>
          <p className="text-sm text-slate-300 leading-relaxed mb-6">
            Prepare data, select a foundation model, and train custom weights
            without managing GPU infrastructure manually.
          </p>
          <div className="flex items-center gap-3">
            <Link
              href="/fine-tune"
              className="inline-flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs px-5 py-2.5 rounded-xl transition-all shadow-sm"
            >
              <Sparkles className="w-4 h-4" />
              <span>Create Fine-Tune</span>
            </Link>
            <Link
              href="/jobs"
              className="inline-flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white font-medium text-xs px-4 py-2.5 rounded-xl transition-all border border-white/10"
            >
              <span>View Training Jobs</span>
            </Link>
            <Link
              href="/models"
              className="inline-flex items-center gap-2 text-slate-300 hover:text-white font-medium text-xs px-3 py-2.5 transition-colors"
            >
              <span>View Models</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Decorative Grid SVG */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 opacity-10 pointer-events-none flex items-center justify-center">
          <Boxes className="w-64 h-64 text-teal-400" />
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-1">
              Active Training Jobs
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {activeJobs.length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-600 border border-teal-100 flex items-center justify-center">
            <Cpu className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-1">
              Completed Models
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {completedJobs.length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-1">
              Supported Base Models
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {models.length}
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center">
            <Boxes className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Recent Training Jobs Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Recent Training Jobs
            </h2>
            <p className="text-xs text-slate-500">
              Latest fine-tuning jobs across your workspace
            </p>
          </div>
          <Link
            href="/jobs"
            className="text-xs font-semibold text-teal-600 hover:text-teal-700 flex items-center gap-1"
          >
            <span>View All</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
            <span>Loading training jobs...</span>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Cpu}
              title="No training jobs yet"
              description="Start your first fine-tuning run to train custom models."
              actionText="Create Fine-Tune"
              actionHref="/fine-tune"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3">Job ID</th>
                  <th className="px-5 py-3">Base Model</th>
                  <th className="px-5 py-3">Dataset</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Created</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {jobs.slice(0, 5).map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-slate-50/80 transition-colors"
                  >
                    <td className="px-5 py-3.5 font-mono font-medium text-slate-900">
                      {job.id.substring(0, 8)}...
                    </td>
                    <td className="px-5 py-3.5 font-medium text-slate-800">
                      {job.model_key}
                    </td>
                    <td className="px-5 py-3.5 text-slate-600 max-w-[180px] truncate">
                      {job.dataset_id}
                    </td>
                    <td className="px-5 py-3.5">
                      <Badge status={job.status} />
                    </td>
                    <td className="px-5 py-3.5 text-slate-500">
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        href={`/jobs/${job.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 hover:bg-teal-100 px-3 py-1 rounded-lg transition-all"
                      >
                        <span>Monitor</span>
                        <ChevronRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Featured Base Models Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Supported Foundation Models
            </h2>
            <p className="text-xs text-slate-500">
              Ready for 4-bit QLoRA fine-tuning on single GPUs
            </p>
          </div>
          <Link
            href="/models"
            className="text-xs font-semibold text-teal-600 hover:text-teal-700 flex items-center gap-1"
          >
            <span>Explore Models</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {models.slice(0, 4).map((model) => (
            <div
              key={model.model_key}
              className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs hover:border-teal-300 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 uppercase tracking-wider">
                    {model.template}
                  </span>
                  <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
                    {model.quantization}
                  </span>
                </div>
                <h3 className="font-bold text-sm text-slate-900 mb-1">
                  {model.display_name}
                </h3>
                <p className="text-xs font-mono text-slate-400 mb-3 truncate">
                  {model.huggingface_repo}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-500">
                  GPU: {model.gpu_requirements.recommended || 'A100'}
                </span>
                <Link
                  href={`/fine-tune?model=${model.model_key}`}
                  className="font-semibold text-teal-600 hover:text-teal-700 flex items-center gap-1"
                >
                  <span>Train</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
