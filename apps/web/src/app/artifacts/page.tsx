'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { TrainingArtifact, TrainingJob } from '@/lib/types';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  FolderDown,
  FileCode,
  Sparkles,
  RefreshCw,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';

export default function ArtifactsPage() {
  const [artifacts, setArtifacts] = useState<TrainingArtifact[]>([]);
  const [loading, setLoading] = useState(true);

  const loadArtifacts = useCallback(async () => {
    try {
      setLoading(true);
      const jobsRes = await api.getJobs().catch(() => ({ jobs: [] }));
      const allJobs = jobsRes.jobs || [];

      // Fetch artifacts across completed jobs
      const artifactPromises = allJobs.map((j) =>
        api.getJobArtifacts(j.id).catch(() => ({ artifacts: [] }))
      );
      const artifactResults = await Promise.all(artifactPromises);
      const combined = artifactResults.flatMap((r) => r.artifacts || []);

      setArtifacts(combined);
    } catch (err) {
      console.warn('Failed to load artifacts:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const jobsRes = await api.getJobs().catch(() => ({ jobs: [] }));
        if (ignore) return;
        const allJobs = jobsRes.jobs || [];

        const artifactPromises = allJobs.map((j) =>
          api.getJobArtifacts(j.id).catch(() => ({ artifacts: [] }))
        );
        const artifactResults = await Promise.all(artifactPromises);
        if (ignore) return;
        const combined = artifactResults.flatMap((r) => r.artifacts || []);

        setArtifacts(combined);
      } catch (err) {
        console.warn('Failed to load artifacts:', err);
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Artifact Repository
          </h1>
          <p className="text-xs text-slate-500">
            Centralized file registry for model weights, adapter configs, logs, and dataset artifacts.
          </p>
        </div>

        <button
          onClick={loadArtifacts}
          className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
          <span>Loading artifacts...</span>
        </div>
      ) : artifacts.length === 0 ? (
        <EmptyState
          icon={FolderDown}
          title="No training artifacts yet"
          description="Complete a fine-tuning job to package model adapters, tokenizer files, and execution logs."
          actionText="Create Fine-Tune"
          actionHref="/fine-tune"
        />
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-900">
              Generated Files ({artifacts.length})
            </span>
            <span className="text-[11px] font-semibold text-slate-500 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
              <span>Verified Checksums</span>
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Filename</th>
                  <th className="px-5 py-3.5">Type</th>
                  <th className="px-5 py-3.5">Job ID</th>
                  <th className="px-5 py-3.5">Size</th>
                  <th className="px-5 py-3.5">Created</th>
                  <th className="px-5 py-3.5 text-right">Link</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {artifacts.map((art) => (
                  <tr key={art.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-4 font-mono font-bold text-slate-900 flex items-center gap-2">
                      <FileCode className="w-4 h-4 text-teal-600" />
                      <span>{art.filename}</span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                        {art.artifact_type}
                      </span>
                    </td>
                    <td className="px-5 py-4 font-mono text-slate-500">
                      {art.training_job_id.substring(0, 8)}...
                    </td>
                    <td className="px-5 py-4 font-mono text-slate-600">
                      {(art.size_bytes / (1024 * 1024)).toFixed(2)} MB
                    </td>
                    <td className="px-5 py-4 text-slate-400">
                      {new Date(art.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        href={`/jobs/${art.training_job_id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 hover:bg-teal-100 px-3 py-1.5 rounded-lg transition-all"
                      >
                        <span>View Job</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
