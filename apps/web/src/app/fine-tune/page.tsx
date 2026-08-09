'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import {
  DatasetSearchResult,
  DatasetRowPreview,
  DatasetNormalizeResponse,
  ModelDefinition,
  TrainingConfig,
} from '@/lib/types';
import {
  Sparkles,
  Database,
  Boxes,
  Sliders,
  CheckCircle2,
  Search,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  FileCheck,
  Zap,
  DollarSign,
  Clock,
  Cpu,
  Shield,
} from 'lucide-react';

const STEPS = [
  { id: 1, name: 'Dataset', icon: Database },
  { id: 2, name: 'Model', icon: Boxes },
  { id: 3, name: 'Training Config', icon: Sliders },
  { id: 4, name: 'Review & Cost', icon: CheckCircle2 },
];

function FineTuneWizardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialModelKey = searchParams.get('model') || '';

  const [currentStep, setCurrentStep] = useState(1);

  // --- Step 1: Dataset State ---
  const [searchQuery, setSearchQuery] = useState('alpaca');
  const [searchResults, setSearchResults] = useState<DatasetSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [previews, setPreviews] = useState<DatasetRowPreview[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [promptField, setPromptField] = useState('instruction');
  const [responseField, setResponseField] = useState('output');
  const [normalizing, setNormalizing] = useState(false);
  const [normalizedResult, setNormalizedResult] =
    useState<DatasetNormalizeResponse | null>(null);
  const [datasetError, setDatasetError] = useState('');

  // --- Step 2: Model State ---
  const [models, setModels] = useState<ModelDefinition[]>([]);
  const [selectedModelKey, setSelectedModelKey] = useState(initialModelKey);

  // --- Step 3: Config State ---
  const [epochs, setEpochs] = useState(3);
  const [learningRate, setLearningRate] = useState(0.0002);
  const [batchSize, setBatchSize] = useState(2);
  const [gradientAccSteps, setGradientAccSteps] = useState(4);
  const [sequenceLength, setSequenceLength] = useState(4096);
  const [loraRank, setLoraRank] = useState(16);
  const [loraAlpha, setLoraAlpha] = useState(32);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // --- Step 4: Submission State ---
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  // Search datasets
  const handleSearchDatasets = async (q: string) => {
    if (!q.trim()) return;
    try {
      setSearching(true);
      setDatasetError('');
      const results = await api.searchDatasets(q);
      setSearchResults(results);
    } catch (err: any) {
      setDatasetError(err.message || 'Failed to search datasets');
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    api.searchDatasets('alpaca').then((res) => {
      if (mounted) setSearchResults(res || []);
    }).catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  // Fetch models
  useEffect(() => {
    let ignore = false;
    api.getModels().then((res) => {
      if (ignore) return;
      setModels(res.models || []);
      if (!initialModelKey && res.models?.length > 0) {
        setSelectedModelKey(res.models[0].model_key);
      }
    }).catch(() => {});
    return () => {
      ignore = true;
    };
  }, [initialModelKey]);

  // Select dataset & fetch preview
  const handleSelectDataset = async (datasetId: string) => {
    setSelectedDatasetId(datasetId);
    setNormalizedResult(null);
    setDatasetError('');
    try {
      setLoadingPreview(true);
      const rows = await api.previewDataset(datasetId, 'train', 3);
      setPreviews(rows || []);
      if (rows && rows.length > 0) {
        const keys = Object.keys(rows[0]);
        if (keys.includes('instruction')) setPromptField('instruction');
        else if (keys.includes('prompt')) setPromptField('prompt');
        else if (keys[0]) setPromptField(keys[0]);

        if (keys.includes('output')) setResponseField('output');
        else if (keys.includes('response')) setResponseField('response');
        else if (keys[1]) setResponseField(keys[1]);
      }
    } catch (err: any) {
      setDatasetError(err.message || 'Failed to preview dataset rows');
    } finally {
      setLoadingPreview(false);
    }
  };

  // Normalize dataset
  const handleNormalize = async () => {
    if (!selectedDatasetId) return;
    try {
      setNormalizing(true);
      setDatasetError('');
      const res = await api.normalizeDataset({
        dataset_id: selectedDatasetId,
        field_mapping: {
          prompt_field: promptField,
          response_field: responseField,
        },
      });
      setNormalizedResult(res);
    } catch (err: any) {
      setDatasetError(err.message || 'Normalization failed');
    } finally {
      setNormalizing(false);
    }
  };

  // Start Training
  const handleStartTraining = async () => {
    try {
      setSubmitting(true);
      setSubmitError('');

      const config: TrainingConfig = {
        model_key: selectedModelKey,
        dataset_id: selectedDatasetId || 'yahma/alpaca-cleaned',
        normalized_dataset_path:
          normalizedResult?.artifact_path ||
          normalizedResult?.normalized_artifact_path ||
          `storage/normalized/${(selectedDatasetId || 'yahma/alpaca-cleaned').replace('/', '_')}.jsonl`,
        epochs,
        learning_rate: learningRate,
        batch_size: batchSize,
        gradient_accumulation_steps: gradientAccSteps,
        max_sequence_length: sequenceLength,
        lora_rank: loraRank,
        lora_alpha: loraAlpha,
      };

      const createRes = await api.createJob({ config });
      const jobId = createRes.job.id;

      // Queue the job
      await api.queueJob(jobId);

      // Navigate to Training Monitor
      router.push(`/jobs/${jobId}`);
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to submit training job');
      setSubmitting(false);
    }
  };

  const selectedModel = models.find((m) => m.model_key === selectedModelKey);

  // Compute Cost Calculations
  const hourlyGpuRate = selectedModelKey.includes('8b') || selectedModelKey.includes('7b') ? 1.89 : 2.49;
  const estimatedRuntimeMinutes = Math.max(15, epochs * 15);
  const estimatedRuntimeHours = estimatedRuntimeMinutes / 60;
  const estimatedCost = (estimatedRuntimeHours * hourlyGpuRate).toFixed(2);

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-200">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-50 text-teal-700 text-xs font-semibold border border-teal-200 mb-2">
          <Sparkles className="w-3.5 h-3.5" />
          <span>One-Click Fine-Tuning Wizard</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Create New Fine-Tune
        </h1>
        <p className="text-xs text-slate-500">
          Configure your dataset, base model, and hyperparameters with transparent cost estimation.
        </p>
      </div>

      {/* Stepper Progress Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="grid grid-cols-4 gap-2">
          {STEPS.map((step) => {
            const isCompleted = currentStep > step.id;
            const isCurrent = currentStep === step.id;

            return (
              <button
                key={step.id}
                onClick={() => {
                  if (step.id < currentStep) setCurrentStep(step.id);
                }}
                disabled={step.id > currentStep}
                className={`flex items-center gap-3 p-3 rounded-xl transition-all text-left ${
                  isCurrent
                    ? 'bg-teal-600 text-white font-semibold shadow-xs'
                    : isCompleted
                    ? 'bg-teal-50 text-teal-800 font-medium hover:bg-teal-100 cursor-pointer'
                    : 'bg-slate-50 text-slate-400 cursor-not-allowed'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs ${
                    isCurrent
                      ? 'bg-white/20 text-white'
                      : isCompleted
                      ? 'bg-teal-600 text-white'
                      : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : step.id}
                </div>
                <div className="hidden sm:block">
                  <p className="text-xs leading-none">{step.name}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* STEP 1: DATASET */}
      {currentStep === 1 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-6">
          <div>
            <h2 className="text-base font-bold text-slate-900 mb-1">
              Step 1: Select & Prepare Dataset
            </h2>
            <p className="text-xs text-slate-500">
              Search Hugging Face datasets and map your prompt/response fields.
            </p>
          </div>

          {datasetError && (
            <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-xl font-medium flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{datasetError}</span>
            </div>
          )}

          {/* Dataset Search */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold text-slate-700">
              Search Hugging Face Datasets
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  placeholder="e.g. alpaca, gsm8k, code_instructions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === 'Enter' && handleSearchDatasets(searchQuery)
                  }
                  className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:border-teal-600 focus:ring-1 focus:ring-teal-600"
                />
              </div>
              <button
                onClick={() => handleSearchDatasets(searchQuery)}
                disabled={searching}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {searching ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Search className="w-3.5 h-3.5" />
                )}
                <span>Search</span>
              </button>
            </div>

            {/* Search Results List */}
            {searchResults.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                {searchResults.slice(0, 4).map((ds) => (
                  <div
                    key={ds.id}
                    onClick={() => handleSelectDataset(ds.id)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                      selectedDatasetId === ds.id
                        ? 'border-teal-600 bg-teal-50/50 shadow-xs'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-xs text-slate-900 truncate">
                        {ds.name || ds.id}
                      </span>
                      {selectedDatasetId === ds.id && (
                        <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0" />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 line-clamp-2">
                      {ds.description || 'Hugging Face Dataset'}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dataset Selected Preview & Normalization */}
          {selectedDatasetId && (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 flex items-center gap-2">
                  <Database className="w-4 h-4 text-teal-600" />
                  <span>Selected: {selectedDatasetId}</span>
                </span>
                {loadingPreview && (
                  <span className="text-[11px] text-slate-500 flex items-center gap-1">
                    <RefreshCw className="w-3 h-3 animate-spin" /> Loading preview...
                  </span>
                )}
              </div>

              {/* Sample Rows Preview */}
              {previews.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
                    Sample Rows Preview
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-slate-100 font-semibold text-slate-700">
                        <tr>
                          {Object.keys(previews[0]).map((key) => (
                            <th key={key} className="px-3 py-2 border-b">
                              {key}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {previews.map((row, idx) => (
                          <tr key={idx}>
                            {Object.values(row).map((val: any, vIdx) => (
                              <td
                                key={vIdx}
                                className="px-3 py-2 max-w-[200px] truncate text-slate-600"
                              >
                                {typeof val === 'object'
                                  ? JSON.stringify(val)
                                  : String(val)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Field Mapping */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Prompt / Instruction Field
                  </label>
                  <input
                    type="text"
                    value={promptField}
                    onChange={(e) => setPromptField(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Response / Output Field
                  </label>
                  <input
                    type="text"
                    value={responseField}
                    onChange={(e) => setResponseField(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  />
                </div>
              </div>

              {/* Normalization Button */}
              <div className="pt-2 flex items-center justify-between">
                <button
                  onClick={handleNormalize}
                  disabled={normalizing}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-lg transition-all shadow-xs flex items-center gap-2 disabled:opacity-50"
                >
                  {normalizing ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <FileCheck className="w-3.5 h-3.5" />
                  )}
                  <span>Normalize Dataset</span>
                </button>

                {normalizedResult && (
                  <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Dataset ready for training!</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Step 1 Navigation */}
          <div className="flex justify-end pt-4 border-t border-slate-100">
            <button
              onClick={() => setCurrentStep(2)}
              disabled={!selectedDatasetId}
              className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl transition-all flex items-center gap-2 shadow-xs disabled:opacity-50"
            >
              <span>Next: Select Model</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: MODEL */}
      {currentStep === 2 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-6">
          <div>
            <h2 className="text-base font-bold text-slate-900 mb-1">
              Step 2: Choose Foundation Model
            </h2>
            <p className="text-xs text-slate-500">
              Select an open-source base model for 4-bit QLoRA fine-tuning.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {models.map((m) => {
              const isSelected = selectedModelKey === m.model_key;
              return (
                <div
                  key={m.model_key}
                  onClick={() => setSelectedModelKey(m.model_key)}
                  className={`p-5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? 'border-teal-600 bg-teal-50/40 shadow-xs ring-1 ring-teal-600'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                        {m.template}
                      </span>
                      {isSelected && (
                        <CheckCircle2 className="w-4 h-4 text-teal-600" />
                      )}
                    </div>
                    <h3 className="font-bold text-sm text-slate-900 mb-1">
                      {m.display_name}
                    </h3>
                    <p className="text-xs font-mono text-slate-400 mb-3 truncate">
                      {m.huggingface_repo}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                    <div>
                      <span className="text-slate-400 block">GPU Rec:</span>
                      <span className="font-semibold">
                        {m.gpu_requirements.recommended || 'A100'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Min VRAM:</span>
                      <span className="font-semibold">
                        {m.gpu_requirements.minimum_vram_gb || 24} GB
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Step 2 Navigation */}
          <div className="flex justify-between pt-4 border-t border-slate-100">
            <button
              onClick={() => setCurrentStep(1)}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-all flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <button
              onClick={() => setCurrentStep(3)}
              disabled={!selectedModelKey}
              className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl transition-all flex items-center gap-2 shadow-xs disabled:opacity-50"
            >
              <span>Next: Training Config</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: TRAINING CONFIGURATION */}
      {currentStep === 3 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-6">
          <div>
            <h2 className="text-base font-bold text-slate-900 mb-1">
              Step 3: Training Configuration
            </h2>
            <p className="text-xs text-slate-500">
              Configure hyperparameters for QLoRA fine-tuning.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Epochs ({epochs})
              </label>
              <input
                type="range"
                min="1"
                max="10"
                value={epochs}
                onChange={(e) => setEpochs(Number(e.target.value))}
                className="w-full accent-teal-600"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Learning Rate ({learningRate})
              </label>
              <select
                value={learningRate}
                onChange={(e) => setLearningRate(Number(e.target.value))}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl bg-white focus:outline-none"
              >
                <option value={0.0001}>0.0001 (Conservative)</option>
                <option value={0.0002}>0.0002 (Recommended)</option>
                <option value={0.0005}>0.0005 (Aggressive)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Micro Batch Size
              </label>
              <select
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl bg-white"
              >
                <option value={1}>1</option>
                <option value={2}>2 (Default)</option>
                <option value={4}>4</option>
                <option value={8}>8</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Max Sequence Length
              </label>
              <select
                value={sequenceLength}
                onChange={(e) => setSequenceLength(Number(e.target.value))}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl bg-white"
              >
                <option value={2048}>2048 tokens</option>
                <option value={4096}>4096 tokens (Default)</option>
                <option value={8192}>8192 tokens</option>
              </select>
            </div>
          </div>

          {/* Advanced Settings Toggle */}
          <div className="pt-2">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs font-semibold text-teal-600 hover:text-teal-700 flex items-center gap-1"
            >
              <span>{showAdvanced ? 'Hide Advanced Settings' : 'Show Advanced Settings'}</span>
            </button>

            {showAdvanced && (
              <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200 grid grid-cols-2 gap-4 animate-in fade-in duration-150">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    LoRA Rank (r)
                  </label>
                  <input
                    type="number"
                    value={loraRank}
                    onChange={(e) => setLoraRank(Number(e.target.value))}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    LoRA Alpha
                  </label>
                  <input
                    type="number"
                    value={loraAlpha}
                    onChange={(e) => setLoraAlpha(Number(e.target.value))}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Gradient Accumulation Steps
                  </label>
                  <input
                    type="number"
                    value={gradientAccSteps}
                    onChange={(e) => setGradientAccSteps(Number(e.target.value))}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Live Cost Preview Card */}
          <div className="p-5 bg-emerald-50/50 border border-emerald-200 rounded-2xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-800">
                <DollarSign className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-sm">Estimated Training Cost</h3>
              </div>
              <span className="text-lg font-black text-emerald-700 font-mono">
                ${estimatedCost} USD
              </span>
            </div>

            <div className="grid grid-cols-3 gap-3 text-xs pt-2 border-t border-emerald-200/60">
              <div className="flex items-center gap-2 text-slate-700">
                <Cpu className="w-4 h-4 text-emerald-600" />
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase font-semibold">
                    GPU Rate
                  </span>
                  <span className="font-semibold">${hourlyGpuRate}/hr (A100 80GB)</span>
                </div>
              </div>

              <div className="flex items-center gap-2 text-slate-700">
                <Clock className="w-4 h-4 text-emerald-600" />
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase font-semibold">
                    Est. Duration
                  </span>
                  <span className="font-semibold">~{estimatedRuntimeMinutes} minutes</span>
                </div>
              </div>

              <div className="flex items-center gap-2 text-slate-700">
                <Shield className="w-4 h-4 text-emerald-600" />
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase font-semibold">
                    Billing Guarantee
                  </span>
                  <span className="font-semibold">Pay-per-minute only</span>
                </div>
              </div>
            </div>
          </div>

          {/* Step 3 Navigation */}
          <div className="flex justify-between pt-4 border-t border-slate-100">
            <button
              onClick={() => setCurrentStep(2)}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-all flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <button
              onClick={() => setCurrentStep(4)}
              className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl transition-all flex items-center gap-2 shadow-xs"
            >
              <span>Next: Review & Start</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: REVIEW & COST */}
      {currentStep === 4 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-6">
          <div>
            <h2 className="text-base font-bold text-slate-900 mb-1">
              Step 4: Final Summary & Cost Review
            </h2>
            <p className="text-xs text-slate-500">
              Confirm your setup and estimated compute cost before dispatching hardware provisioning.
            </p>
          </div>

          {submitError && (
            <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-xl font-medium flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4">
            <div className="grid grid-cols-2 gap-4 border-b border-slate-200 pb-4">
              <div>
                <span className="text-[11px] text-slate-400 font-semibold uppercase block">
                  Dataset
                </span>
                <span className="text-xs font-bold text-slate-900">
                  {selectedDatasetId || 'yahma/alpaca-cleaned'}
                </span>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 font-semibold uppercase block">
                  Base Model
                </span>
                <span className="text-xs font-bold text-slate-900">
                  {selectedModel?.display_name || selectedModelKey}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block">Method:</span>
                <span className="font-semibold text-slate-900">4-bit QLoRA</span>
              </div>
              <div>
                <span className="text-slate-400 block">Epochs:</span>
                <span className="font-semibold text-slate-900">{epochs}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Learning Rate:</span>
                <span className="font-semibold text-slate-900">{learningRate}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Batch Size:</span>
                <span className="font-semibold text-slate-900">{batchSize}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Gradient Acc:</span>
                <span className="font-semibold text-slate-900">{gradientAccSteps}</span>
              </div>
              <div>
                <span className="text-slate-400 block">GPU Target:</span>
                <span className="font-semibold text-slate-900">
                  {selectedModel?.gpu_requirements.recommended || 'A100 (24GB VRAM)'}
                </span>
              </div>
            </div>
          </div>

          {/* Cost Summary Banner */}
          <div className="p-5 bg-gradient-to-r from-teal-900 to-slate-900 text-white rounded-2xl space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[11px] font-semibold text-teal-300 uppercase tracking-wider block">
                  Total Estimated Training Cost
                </span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black font-mono text-emerald-400">
                    ${estimatedCost} USD
                  </span>
                  <span className="text-xs text-slate-300">
                    (~{estimatedRuntimeMinutes} mins @ ${hourlyGpuRate}/hr)
                  </span>
                </div>
              </div>

              <div className="text-right">
                <span className="text-[10px] uppercase font-bold text-teal-200 bg-teal-800/80 px-2.5 py-1 rounded-full border border-teal-700">
                  Pay-as-you-go
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-300 flex justify-between">
              <span>Hardware Provisioning: <strong>$0.00</strong></span>
              <span>Model Weights Download: <strong>Free</strong></span>
              <span>Adapter Artifact Storage: <strong>Included</strong></span>
            </div>
          </div>

          <div className="p-4 bg-teal-50/60 border border-teal-200 rounded-xl flex items-center gap-3">
            <Zap className="w-5 h-5 text-teal-600 shrink-0" />
            <p className="text-xs text-teal-900 leading-relaxed">
              <strong>Automated Orchestration:</strong> The backend Celery worker and GPU agent will execute your training run asynchronously. You can monitor real-time logs and loss curves on the next screen.
            </p>
          </div>

          {/* Step 4 Navigation */}
          <div className="flex justify-between pt-4 border-t border-slate-100">
            <button
              onClick={() => setCurrentStep(3)}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-all flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <button
              onClick={handleStartTraining}
              disabled={submitting}
              className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs rounded-xl transition-all flex items-center gap-2 shadow-md disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Provisioning & Starting...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Start Fine-Tuning (${estimatedCost})</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FineTuneWizardPage() {
  return (
    <Suspense
      fallback={
        <div className="p-12 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
          <span>Loading Fine-Tuning Wizard...</span>
        </div>
      }
    >
      <FineTuneWizardContent />
    </Suspense>
  );
}
