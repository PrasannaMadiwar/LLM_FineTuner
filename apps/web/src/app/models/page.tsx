'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { ModelDefinition, TrainingJob } from '@/lib/types';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  Boxes,
  Sparkles,
  ArrowRight,
  RefreshCw,
  FolderDown,
  Cpu,
  CheckCircle2,
  Info,
  PlayCircle,
} from 'lucide-react';

export default function ModelsPage() {
  const [baseModels, setBaseModels] = useState<ModelDefinition[]>([]);
  const [completedJobs, setCompletedJobs] = useState<TrainingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'base' | 'finetuned'>('base');

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [modelsRes, jobsRes] = await Promise.all([
          api.getModels().catch(() => ({ models: [] })),
          api.getJobs().catch(() => ({ jobs: [] })),
        ]);
        setBaseModels(modelsRes.models || []);
        setCompletedJobs(
          (jobsRes.jobs || []).filter((j) => j.status === 'completed')
        );
      } catch (err) {
        console.warn('Failed to load models:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Model Library
          </h1>
          <p className="text-xs text-slate-500">
            Explore supported base foundation models and your custom fine-tuned weights.
          </p>
        </div>

        <Link
          href="/fine-tune"
          className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all shadow-xs"
        >
          <Sparkles className="w-4 h-4" />
          <span>New Fine-Tune</span>
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('base')}
          className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'base'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Boxes className="w-4 h-4" />
          <span>Base Foundation Models ({baseModels.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('finetuned')}
          className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'finetuned'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Fine-Tuned Models ({completedJobs.length})</span>
        </button>
      </div>

      {/* BASE MODELS GRID */}
      {activeTab === 'base' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {baseModels.map((m) => (
            <div
              key={m.model_key}
              className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4 hover:border-teal-300 transition-all"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                  {m.template}
                </span>
                <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-100">
                  {m.quantization}
                </span>
              </div>

              <div>
                <h3 className="font-bold text-base text-slate-900 mb-1">
                  {m.display_name}
                </h3>
                <p className="text-xs font-mono text-slate-400">
                  {m.huggingface_repo}
                </p>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Recommended GPU:</span>
                  <span className="font-bold text-slate-800">{m.gpu_requirements.recommended || 'A100'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Max Sequence Length:</span>
                  <span className="font-bold text-slate-800">{m.sequence_length} tokens</span>
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <Link
                  href={`/fine-tune?model=${m.model_key}`}
                  className="inline-flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-xs"
                >
                  <span>Fine-Tune This Model</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* FINE-TUNED MODELS GRID */}
      {activeTab === 'finetuned' && (
        <div className="space-y-6">
          <div className="p-4 bg-teal-50/70 border border-teal-200 rounded-xl flex items-center gap-3 text-xs text-teal-900">
            <Info className="w-5 h-5 text-teal-600 shrink-0" />
            <p>
              <strong>Model Weights & Checkpoints:</strong> Fine-tuned model adapters are generated during training runs. You can view logs, checkpoints, and export artifacts directly from your job details.
            </p>
          </div>

          {completedJobs.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No fine-tuned models yet"
              description="Complete your first fine-tuning training job to export custom model weights."
              actionText="Create Fine-Tune"
              actionHref="/fine-tune"
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {completedJobs.map((job) => (
                <div
                  key={job.id}
                  className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">
                      {job.training_config.model_key} Custom Adapter
                    </span>
                    <Badge status="completed" />
                  </div>

                  <div className="space-y-1 text-xs">
                    <p className="text-slate-500 font-mono">
                      Job ID: {job.id}
                    </p>
                    <p className="text-slate-600 font-medium">
                      Dataset: {job.dataset_id}
                    </p>
                    <p className="text-slate-400 text-[11px]">
                      Completed: {new Date(job.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1"
                    >
                      <span>Details</span>
                      <ArrowRight className="w-3 h-3" />
                    </Link>

                    <div className="flex items-center gap-2">
                      <Link
                        href={`/playground?job_id=${job.id}`}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-teal-600 hover:bg-teal-700 px-3 py-1.5 rounded-lg transition-all shadow-xs"
                      >
                        <PlayCircle className="w-3.5 h-3.5" />
                        <span>Test in Playground</span>
                      </Link>

                      <Link
                        href="/artifacts"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1.5 rounded-lg transition-all"
                      >
                        <FolderDown className="w-3.5 h-3.5" />
                        <span>Artifacts</span>
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
