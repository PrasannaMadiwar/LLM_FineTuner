'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Boxes, CheckCircle2, Cpu, Database, RefreshCw, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';
import { ModelDefinition, TrainingJob } from '@/lib/types';
import { Badge } from '@/components/ui/Badge';

export default function DashboardPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [models, setModels] = useState<ModelDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { Promise.all([api.getJobs().catch(() => ({ jobs: [] })), api.getModels().catch(() => ({ models: [] }))]).then(([jobData, modelData]) => { setJobs(jobData.jobs || []); setModels(modelData.models || []); }).finally(() => setLoading(false)); }, []);
  const activeJobs = jobs.filter((job) => !['completed', 'failed', 'cancelled'].includes(job.status));
  const completedJobs = jobs.filter((job) => job.status === 'completed');
  const stats = [{ label: 'Active training jobs', value: activeJobs.length, icon: Cpu, color: 'text-teal-700 bg-teal-50 border-teal-100' }, { label: 'Completed models', value: completedJobs.length, icon: CheckCircle2, color: 'text-emerald-700 bg-emerald-50 border-emerald-100' }, { label: 'Foundation models', value: models.length, icon: Boxes, color: 'text-sky-700 bg-sky-50 border-sky-100' }];

  return <div className="space-y-8">
    <div className="flex flex-col justify-between gap-5 border-b border-slate-200 pb-7 sm:flex-row sm:items-end"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">Workspace overview</p><h1 className="mt-2 text-3xl font-bold">Training dashboard</h1><p className="mt-2 text-sm text-slate-600">Track runs, models, and everything needed to ship a custom adapter.</p></div><Link href="/fine-tune" className="inline-flex w-fit items-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-teal-700"><Sparkles className="h-4 w-4" /> New fine-tune</Link></div>
    <div className="grid gap-4 md:grid-cols-3">{stats.map(({ label, value, icon: Icon, color }) => <div key={label} className="flex items-center justify-between border border-slate-200 bg-white p-5 shadow-sm"><div><p className="text-sm font-medium text-slate-600">{label}</p><p className="mt-2 text-3xl font-bold">{loading ? '...' : value}</p></div><div className={`flex h-10 w-10 items-center justify-center rounded-lg border ${color}`}><Icon className="h-5 w-5" /></div></div>)}</div>
    <div className="grid gap-6 lg:grid-cols-[1.45fr_0.8fr]"><section className="border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-200 p-5"><div><h2 className="font-bold">Recent training jobs</h2><p className="mt-1 text-sm text-slate-500">Latest activity in your workspace</p></div><Link href="/jobs" className="inline-flex items-center gap-1 text-sm font-bold text-teal-700 hover:text-teal-800">View all <ArrowRight className="h-4 w-4" /></Link></div>{loading ? <div className="flex items-center justify-center gap-2 p-12 text-sm text-slate-500"><RefreshCw className="h-4 w-4 animate-spin" /> Loading jobs</div> : jobs.length === 0 ? <div className="p-10 text-center"><Cpu className="mx-auto h-7 w-7 text-slate-300" /><p className="mt-3 font-semibold">No training jobs yet</p><Link href="/fine-tune" className="mt-4 inline-flex text-sm font-bold text-teal-700">Create your first run</Link></div> : <div className="divide-y divide-slate-100">{jobs.slice(0, 5).map((job) => <Link key={job.id} href={`/jobs/${job.id}`} className="flex items-center justify-between gap-4 p-4 hover:bg-slate-50"><div className="min-w-0"><p className="truncate font-mono text-sm font-semibold">{job.id.slice(0, 8)}</p><p className="mt-1 truncate text-xs text-slate-500">{job.model_key} · {job.dataset_id}</p></div><Badge status={job.status} /></Link>)}</div>}</section><section className="border border-slate-200 bg-white p-5"><Database className="h-5 w-5 text-teal-700" /><h2 className="mt-5 font-bold">Ready to train?</h2><p className="mt-2 text-sm leading-6 text-slate-600">Start with a dataset, select a model, and set the training configuration for your next adapter.</p><div className="mt-6 space-y-3"><Link href="/datasets" className="flex items-center justify-between border border-slate-200 p-3 text-sm font-semibold hover:border-teal-300">Explore datasets <ArrowRight className="h-4 w-4" /></Link><Link href="/models" className="flex items-center justify-between border border-slate-200 p-3 text-sm font-semibold hover:border-teal-300">Browse models <ArrowRight className="h-4 w-4" /></Link></div></section></div>
  </div>;
}
