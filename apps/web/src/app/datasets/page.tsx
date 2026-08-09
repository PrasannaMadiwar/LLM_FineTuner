'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { DatasetSearchResult, DatasetRowPreview } from '@/lib/types';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  Database,
  Search,
  RefreshCw,
  Sparkles,
  ArrowRight,
  Eye,
} from 'lucide-react';

export default function DatasetsPage() {
  const [query, setQuery] = useState('alpaca');
  const [datasets, setDatasets] = useState<DatasetSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDs, setSelectedDs] = useState<string | null>(null);
  const [previews, setPreviews] = useState<DatasetRowPreview[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const handleSearch = async (q: string) => {
    if (!q.trim()) return;
    try {
      setLoading(true);
      const res = await api.searchDatasets(q);
      setDatasets(res || []);
    } catch (err) {
      console.warn('Dataset search error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    api.searchDatasets('alpaca').then((res) => {
      if (mounted) setDatasets(res || []);
    }).catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const handlePreview = async (dsId: string) => {
    setSelectedDs(dsId);
    try {
      setLoadingPreview(true);
      const rows = await api.previewDataset(dsId, 'train', 3);
      setPreviews(rows || []);
    } catch (err) {
      console.warn('Preview error:', err);
    } finally {
      setLoadingPreview(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Dataset Library
          </h1>
          <p className="text-xs text-slate-500">
            Discover, preview, and normalize training datasets from Hugging Face.
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

      {/* Search Input */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs flex gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search Hugging Face datasets (e.g. alpaca, gsm8k, code_instructions)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch(query)}
            className="w-full pl-10 pr-4 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:border-teal-600 focus:ring-1 focus:ring-teal-600"
          />
        </div>
        <button
          onClick={() => handleSearch(query)}
          disabled={loading}
          className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl transition-all flex items-center gap-2 disabled:opacity-50"
        >
          {loading ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Search className="w-3.5 h-3.5" />
          )}
          <span>Search</span>
        </button>
      </div>

      {/* Results Grid */}
      {datasets.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No datasets found"
          description="Try searching for popular open datasets like alpaca, dolly, or squad."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {datasets.map((ds) => (
            <div
              key={ds.id}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs hover:border-teal-300 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                    Hugging Face
                  </span>
                  <button
                    onClick={() => handlePreview(ds.id)}
                    className="text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Preview</span>
                  </button>
                </div>
                <h3 className="font-bold text-sm text-slate-900 mb-1">
                  {ds.name || ds.id}
                </h3>
                <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed mb-4">
                  {ds.description || 'Hugging Face public training dataset.'}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] font-mono text-slate-400">
                  {ds.id}
                </span>
                <Link
                  href={`/fine-tune?dataset=${encodeURIComponent(ds.id)}`}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 hover:bg-teal-100 px-3 py-1.5 rounded-lg transition-all"
                >
                  <span>Use in Wizard</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Row Preview Modal */}
      {selectedDs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-2xl bg-white rounded-2xl border border-slate-200 shadow-xl p-6 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-sm text-slate-900">
                Sample Preview: {selectedDs}
              </h3>
              <button
                onClick={() => setSelectedDs(null)}
                className="text-xs font-semibold text-slate-500 hover:text-slate-900 px-2 py-1 bg-slate-100 rounded-lg"
              >
                Close
              </button>
            </div>

            {loadingPreview ? (
              <div className="py-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
                <span>Loading preview rows...</span>
              </div>
            ) : previews.length === 0 ? (
              <p className="text-xs text-slate-500 py-4">No preview rows available.</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 font-semibold text-slate-700">
                    <tr>
                      {Object.keys(previews[0]).map((k) => (
                        <th key={k} className="px-3 py-2 border-b">
                          {k}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {previews.map((row, idx) => (
                      <tr key={idx}>
                        {Object.values(row).map((v: any, vIdx) => (
                          <td key={vIdx} className="px-3 py-2 text-slate-600 max-w-[200px] truncate">
                            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
