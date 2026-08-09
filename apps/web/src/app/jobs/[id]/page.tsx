'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import {
  TrainingJob,
  TrainingJobEvent,
  TrainingMetric,
  TrainingCheckpoint,
  TrainingArtifact,
} from '@/lib/types';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  Cpu,
  Activity,
  Terminal,
  BarChart3,
  Bookmark,
  FolderDown,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  PlayCircle,
  XCircle,
  Play,
  RotateCcw,
  Sparkles,
  ArrowLeft,
  Clock,
  HardDrive,
  FileCode,
} from 'lucide-react';

export default function TrainingMonitorPage() {
  const params = useParams();
  const jobId = params?.id as string;
  const router = useRouter();

  const [job, setJob] = useState<TrainingJob | null>(null);
  const [events, setEvents] = useState<TrainingJobEvent[]>([]);
  const [metrics, setMetrics] = useState<TrainingMetric[]>([]);
  const [latestCheckpoint, setLatestCheckpoint] =
    useState<TrainingCheckpoint | null>(null);
  const [artifacts, setArtifacts] = useState<TrainingArtifact[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'logs' | 'metrics' | 'checkpoints' | 'artifacts'>('overview');
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Poll job data
  useEffect(() => {
    if (!jobId) return;

    let timer: NodeJS.Timeout;

    async function fetchJobDetails() {
      try {
        const [jobRes, eventsRes, metricsRes, ckptRes, artRes] =
          await Promise.all([
            api.getJob(jobId),
            api.getJobEvents(jobId).catch(() => ({ events: [] })),
            api.getJobMetrics(jobId).catch(() => ({ metrics: [] })),
            api.getLatestCheckpoint(jobId).catch(() => ({ checkpoint: null })),
            api.getJobArtifacts(jobId).catch(() => ({ artifacts: [] })),
          ]);

        setJob(jobRes.job);
        setEvents(eventsRes.events || []);
        setMetrics(metricsRes.metrics || []);
        setLatestCheckpoint(ckptRes.checkpoint || null);
        setArtifacts(artRes.artifacts || []);
        setLoading(false);

        // Continue polling if not terminal
        const isTerminal = [
          'completed',
          'failed',
          'cancelled',
        ].includes(jobRes.job.status);
        if (!isTerminal) {
          timer = setTimeout(fetchJobDetails, 3000);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to fetch job details');
        setLoading(false);
      }
    }

    fetchJobDetails();

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [jobId]);

  // Auto-scroll logs
  useEffect(() => {
    if (autoScrollLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScrollLogs]);

  // Handle Cancel
  const handleCancelJob = async () => {
    if (!job) return;
    try {
      const res = await api.cancelJob(job.id);
      setJob(res.job);
    } catch (err: any) {
      alert(`Failed to cancel job: ${err.message}`);
    }
  };

  // Handle Resume
  const handleResumeJob = async (ckptPath?: string) => {
    if (!job) return;
    try {
      const res = await api.resumeJob(job.id, ckptPath);
      router.push(`/jobs/${res.job.id}`);
    } catch (err: any) {
      alert(`Failed to resume job: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-teal-600" />
        <span className="font-semibold text-slate-700">
          Loading Training Monitor...
        </span>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="p-8">
        <EmptyState
          icon={AlertCircle}
          title="Training Job Not Found"
          description={error || 'Unable to retrieve training job details.'}
          actionText="Back to Training Jobs"
          actionHref="/jobs"
        />
      </div>
    );
  }

  const latestMetric = metrics[metrics.length - 1];
  const isCompleted = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isCancelled = job.status === 'cancelled';
  const isActive = !isCompleted && !isFailed && !isCancelled;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/jobs"
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                {job.training_config.model_key}
              </h1>
              <Badge status={job.status} />
            </div>
            <p className="text-xs font-mono text-slate-400">
              ID: {job.id} • Dataset: {job.dataset_id}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {isActive && (
            <button
              onClick={handleCancelJob}
              className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-semibold text-xs rounded-xl transition-all flex items-center gap-1.5"
            >
              <XCircle className="w-4 h-4" />
              <span>Cancel Job</span>
            </button>
          )}

          {(isCompleted || isFailed || isCancelled) && (
            <button
              onClick={() => handleResumeJob(latestCheckpoint?.path)}
              className="px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl transition-all shadow-xs flex items-center gap-1.5"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Resume Training</span>
            </button>
          )}
        </div>
      </div>

      {/* Success State Banner */}
      {isCompleted && (
        <div className="bg-emerald-50 border border-emerald-200 p-6 rounded-2xl flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-sm">
              <CheckCircle2 className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-base font-bold text-emerald-950">
                Fine-tuning Completed Successfully!
              </h2>
              <p className="text-xs text-emerald-700">
                Your custom LLM weights have been checkpointed and packaged into production artifacts.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/playground?job_id=${job.id}`}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl transition-all shadow-xs flex items-center gap-1.5"
            >
              <PlayCircle className="w-4 h-4" />
              <span>Test Model in Playground</span>
            </Link>
            <Link
              href="/artifacts"
              className="px-3.5 py-2 bg-white hover:bg-emerald-100 text-emerald-800 border border-emerald-300 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5"
            >
              <FolderDown className="w-4 h-4" />
              <span>Artifacts</span>
            </Link>
          </div>
        </div>
      )}

      {/* Failed Banner */}
      {isFailed && (
        <div className="bg-rose-50 border border-rose-200 p-5 rounded-2xl flex items-center gap-4 text-rose-900">
          <AlertCircle className="w-6 h-6 text-rose-600 shrink-0" />
          <div>
            <h2 className="text-sm font-bold">Training Failed</h2>
            <p className="text-xs text-rose-700">
              {job.error_message || 'Training run encountered an infrastructure or runtime issue.'}
            </p>
          </div>
        </div>
      )}

      {/* Main Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">
            Status
          </span>
          <span className="text-sm font-bold text-slate-900 capitalize">
            {job.status.replace(/_/g, ' ')}
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">
            Epoch / Step
          </span>
          <span className="text-sm font-bold text-slate-900">
            {latestMetric?.epoch ?? '0'} / {latestMetric?.global_step ?? '0'}
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">
            Training Loss
          </span>
          <span className="text-sm font-bold text-teal-600">
            {latestMetric?.loss ? latestMetric.loss.toFixed(4) : 'N/A'}
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">
            GPU Utilization
          </span>
          <span className="text-sm font-bold text-slate-900">
            {latestMetric?.gpu_utilization
              ? `${latestMetric.gpu_utilization.toFixed(1)}%`
              : 'N/A'}
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">
            Artifacts
          </span>
          <span className="text-sm font-bold text-slate-900">
            {artifacts.length} files
          </span>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-slate-200 flex gap-6">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'logs', label: 'Console Logs', icon: Terminal, count: events.length },
          { id: 'metrics', label: 'Metrics', icon: BarChart3, count: metrics.length },
          { id: 'checkpoints', label: 'Checkpoints', icon: Bookmark, badge: latestCheckpoint ? '1' : '0' },
          { id: 'artifacts', label: 'Artifacts', icon: FolderDown, count: artifacts.length },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
                isActive
                  ? 'border-teal-600 text-teal-700'
                  : 'border-transparent text-slate-500 hover:text-slate-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              {(tab.count !== undefined || tab.badge) && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] ${
                    isActive
                      ? 'bg-teal-100 text-teal-800'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {tab.count ?? tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 space-y-6">
            <h2 className="text-sm font-bold text-slate-900">
              Training Configuration Details
            </h2>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">
                  Model Key
                </span>
                <span className="font-bold text-slate-900">{job.model_key}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">
                  Template
                </span>
                <span className="font-bold text-slate-900">{job.template_name}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">
                  Epochs
                </span>
                <span className="font-bold text-slate-900">
                  {job.training_config.epochs}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">
                  Learning Rate
                </span>
                <span className="font-bold text-slate-900">
                  {job.training_config.learning_rate}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">
                  Batch Size
                </span>
                <span className="font-bold text-slate-900">
                  {job.training_config.batch_size}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">
                  Gradient Accumulation
                </span>
                <span className="font-bold text-slate-900">
                  {job.training_config.gradient_accumulation_steps}
                </span>
              </div>
            </div>

            {/* Event Timeline */}
            <div>
              <h3 className="text-xs font-bold text-slate-900 mb-3">
                Lifecycle Events
              </h3>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
                {events.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <Badge status={ev.to_status} />
                      <span className="text-slate-700 font-medium">
                        {ev.message}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {new Date(ev.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200">
              <h3 className="text-xs font-bold text-slate-900 mb-3 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-teal-600" />
                <span>Runtime Environment</span>
              </h3>
              <dl className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <dt className="text-slate-500">Orchestrator:</dt>
                  <dd className="font-semibold text-slate-900">Celery Async</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <dt className="text-slate-500">GPU Agent Protocol:</dt>
                  <dd className="font-semibold text-slate-900">HTTP Forward</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <dt className="text-slate-500">Unsloth Precision:</dt>
                  <dd className="font-semibold text-slate-900">4-Bit QLoRA</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt className="text-slate-500">Created At:</dt>
                  <dd className="font-semibold text-slate-900">
                    {new Date(job.created_at).toLocaleString()}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CONSOLE LOGS */}
      {activeTab === 'logs' && (
        <div className="bg-slate-950 rounded-2xl border border-slate-800 p-4 font-mono text-xs text-slate-300 shadow-inner">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800 text-xs">
            <span className="text-slate-400 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-teal-400" />
              <span>Runtime Event Stream</span>
            </span>
            <label className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-slate-200">
              <input
                type="checkbox"
                checked={autoScrollLogs}
                onChange={(e) => setAutoScrollLogs(e.target.checked)}
                className="accent-teal-500"
              />
              <span>Auto-scroll</span>
            </label>
          </div>

          <div className="space-y-1.5 max-h-96 overflow-y-auto leading-relaxed">
            {events.map((ev) => (
              <div key={ev.id} className="flex gap-3 font-mono">
                <span className="text-slate-500 shrink-0">
                  [{new Date(ev.created_at).toLocaleTimeString()}]
                </span>
                <span className="text-teal-400 font-bold uppercase shrink-0">
                  {ev.to_status}:
                </span>
                <span className="text-slate-200">{ev.message}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}

      {/* TAB 3: METRICS */}
      {activeTab === 'metrics' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 space-y-6">
          <h2 className="text-sm font-bold text-slate-900">
            Training Telemetry Metrics
          </h2>

          {metrics.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="No telemetry metrics yet"
              description="Metrics will appear once training steps begin executing."
            />
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 font-semibold text-slate-700 border-b">
                    <tr>
                      <th className="px-4 py-2.5">Step</th>
                      <th className="px-4 py-2.5">Epoch</th>
                      <th className="px-4 py-2.5">Loss</th>
                      <th className="px-4 py-2.5">Learning Rate</th>
                      <th className="px-4 py-2.5">GPU Util</th>
                      <th className="px-4 py-2.5">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {metrics.map((m) => (
                      <tr key={m.id} className="hover:bg-slate-50">
                        <td className="px-4 py-2 text-slate-900 font-bold">
                          {m.global_step ?? '—'}
                        </td>
                        <td className="px-4 py-2 text-slate-600">
                          {m.epoch ? m.epoch.toFixed(2) : '—'}
                        </td>
                        <td className="px-4 py-2 text-teal-600 font-bold">
                          {m.loss ? m.loss.toFixed(4) : '—'}
                        </td>
                        <td className="px-4 py-2 text-slate-600">
                          {m.learning_rate ? m.learning_rate.toExponential(2) : '—'}
                        </td>
                        <td className="px-4 py-2 text-slate-600">
                          {m.gpu_utilization ? `${m.gpu_utilization.toFixed(1)}%` : '—'}
                        </td>
                        <td className="px-4 py-2 text-slate-400 text-[11px]">
                          {new Date(m.timestamp).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: CHECKPOINTS */}
      {activeTab === 'checkpoints' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 space-y-6">
          <h2 className="text-sm font-bold text-slate-900">
            Model Checkpoints
          </h2>

          {!latestCheckpoint ? (
            <EmptyState
              icon={Bookmark}
              title="No checkpoints saved yet"
              description="Model checkpoints are generated automatically during training iterations."
            />
          ) : (
            <div className="p-5 rounded-2xl border border-teal-200 bg-teal-50/50 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-sm text-slate-900">
                    Latest Checkpoint (Step {latestCheckpoint.global_step ?? 'N/A'})
                  </span>
                  <span className="text-[10px] font-bold bg-teal-600 text-white px-2 py-0.5 rounded-full">
                    LATEST
                  </span>
                </div>
                <p className="text-xs font-mono text-slate-600">
                  Path: {latestCheckpoint.path}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Saved: {new Date(latestCheckpoint.created_at).toLocaleString()}
                </p>
              </div>

              <button
                onClick={() => handleResumeJob(latestCheckpoint.path)}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-xl transition-all shadow-xs flex items-center gap-1.5"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Resume From Here</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: ARTIFACTS */}
      {activeTab === 'artifacts' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 space-y-6">
          <h2 className="text-sm font-bold text-slate-900">
            Training Job Output Artifacts
          </h2>

          {artifacts.length === 0 ? (
            <EmptyState
              icon={FolderDown}
              title="No artifacts collected yet"
              description="Artifacts will be packaged upon successful training run completion."
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {artifacts.map((art) => (
                <div
                  key={art.id}
                  className="p-4 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-teal-100 text-teal-700 flex items-center justify-center">
                      <FileCode className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="font-bold text-xs text-slate-900">
                        {art.filename}
                      </p>
                      <p className="text-[11px] text-slate-500 font-mono">
                        {(art.size_bytes / (1024 * 1024)).toFixed(2)} MB • {art.artifact_type}
                      </p>
                    </div>
                  </div>
                  <span className="text-[10px] font-semibold bg-white border border-slate-200 text-slate-600 px-2 py-1 rounded-md">
                    Verified
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
