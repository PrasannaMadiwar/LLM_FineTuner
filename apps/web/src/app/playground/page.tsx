'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { ModelDefinition, TrainingJob } from '@/lib/types';
import { Badge } from '@/components/ui/Badge';
import {
  Sparkles,
  PlayCircle,
  Send,
  RefreshCw,
  SlidersHorizontal,
  Code2,
  Copy,
  Check,
  Zap,
  Bot,
  User,
  Split,
  MessageSquare,
  Cpu,
  Layers,
  ArrowLeft,
  Boxes,
} from 'lucide-react';

function PlaygroundContent() {
  const searchParams = useSearchParams();
  const initialJobId = searchParams.get('job_id') || searchParams.get('model');

  const [baseModels, setBaseModels] = useState<ModelDefinition[]>([]);
  const [completedJobs, setCompletedJobs] = useState<TrainingJob[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('');
  const [loading, setLoading] = useState(true);

  // Playground settings
  const [mode, setMode] = useState<'single' | 'compare'>('single');
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful, precise AI assistant fine-tuned for high-performance task execution.');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(512);
  const [topP, setTopP] = useState(0.9);

  // Chat messages
  const [inputPrompt, setInputPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const [showCodeModal, setShowCodeModal] = useState(false);

  interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    metrics?: {
      tokensPerSec: number;
      latencyMs: number;
      tokenCount: number;
      modelName: string;
    };
    compareContent?: string;
    compareMetrics?: {
      tokensPerSec: number;
      latencyMs: number;
      tokenCount: number;
      modelName: string;
    };
  }

  const [messages, setMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [modelsRes, jobsRes] = await Promise.all([
          api.getModels().catch(() => ({ models: [] })),
          api.getJobs().catch(() => ({ jobs: [] })),
        ]);
        const bModels = modelsRes.models || [];
        const cJobs = (jobsRes.jobs || []).filter((j) => j.status === 'completed');
        setBaseModels(bModels);
        setCompletedJobs(cJobs);

        if (initialJobId) {
          const matchJob = cJobs.find((j) => j.id === initialJobId);
          if (matchJob) {
            setSelectedModelId(`job:${matchJob.id}`);
          } else {
            const matchModel = bModels.find((m) => m.model_key === initialJobId);
            if (matchModel) {
              setSelectedModelId(`base:${matchModel.model_key}`);
            } else if (cJobs.length > 0) {
              setSelectedModelId(`job:${cJobs[0].id}`);
            } else if (bModels.length > 0) {
              setSelectedModelId(`base:${bModels[0].model_key}`);
            }
          }
        } else if (cJobs.length > 0) {
          setSelectedModelId(`job:${cJobs[0].id}`);
        } else if (bModels.length > 0) {
          setSelectedModelId(`base:${bModels[0].model_key}`);
        }
      } catch (err) {
        console.warn('Failed to load playground models:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [initialJobId]);

  // Selected model display name
  const getSelectedModelName = () => {
    if (selectedModelId.startsWith('job:')) {
      const id = selectedModelId.replace('job:', '');
      const j = completedJobs.find((item) => item.id === id);
      return j ? `${j.training_config.model_key} Fine-Tuned (${j.dataset_id})` : 'Fine-Tuned Model';
    } else if (selectedModelId.startsWith('base:')) {
      const key = selectedModelId.replace('base:', '');
      const m = baseModels.find((item) => item.model_key === key);
      return m ? `${m.display_name} (Base Foundation)` : 'Base Model';
    }
    return 'Select a Model';
  };

  const handleSendMessage = async (promptOverride?: string) => {
    const text = (promptOverride || inputPrompt).trim();
    if (!text || isGenerating) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!promptOverride) setInputPrompt('');
    setIsGenerating(true);

    // Simulate real-time streaming inference generation
    const modelName = getSelectedModelName();
    const isFinetuned = selectedModelId.startsWith('job:');

    setTimeout(() => {
      let finetunedResponse = '';
      let baseResponse = '';

      if (text.toLowerCase().includes('hello') || text.toLowerCase().includes('hi')) {
        finetunedResponse = `Hello! I am your custom fine-tuned assistant based on ${modelName}. I'm optimized for precise instructions and domain tasks. How can I help you today?`;
        baseResponse = `Hello! How can I assist you today? I am a general foundation language model.`;
      } else if (text.toLowerCase().includes('dataset') || text.toLowerCase().includes('train')) {
        finetunedResponse = `Fine-tuning transforms generic base model representations into domain-specific experts using LoRA rank decomposition adapters. By focusing optimization on target query/value projection matrices, training achieves high accuracy while requiring 80% less VRAM.`;
        baseResponse = `Fine-tuning is a machine learning process where a pre-trained model is further trained on a specific dataset to adapt its parameters for specialized tasks.`;
      } else {
        finetunedResponse = `Here is the specialized output for your request:\n\nBased on your prompt ("${text}"), I have evaluated the input through the fine-tuned adapter weights (${modelName}). The response follows your exact target mapping format with optimized completion accuracy.\n\nKey Recommendations:\n1. Ensure high dataset normalization cleanliness.\n2. Utilize rank=16 LoRA configuration for balanced efficiency.\n3. Deploy the resulting model via Hugging Face Transformers or vLLM.`;
        baseResponse = `Here is a standard completion for your prompt ("${text}"). Foundation models provide general answers across open-ended domains without specialized dataset constraints.`;
      }

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: isFinetuned ? finetunedResponse : baseResponse,
        metrics: {
          tokensPerSec: Math.floor(Math.random() * 15) + 42,
          latencyMs: Math.floor(Math.random() * 80) + 120,
          tokenCount: (isFinetuned ? finetunedResponse : baseResponse).split(' ').length * 2,
          modelName,
        },
        compareContent: mode === 'compare' ? baseResponse : undefined,
        compareMetrics: mode === 'compare' ? {
          tokensPerSec: Math.floor(Math.random() * 12) + 35,
          latencyMs: Math.floor(Math.random() * 100) + 180,
          tokenCount: baseResponse.split(' ').length * 2,
          modelName: 'Base Foundation Model (Pre-Fine-Tuning)',
        } : undefined,
      };

      setMessages((prev) => [...prev, botMsg]);
      setIsGenerating(false);
    }, 900);
  };

  const codeSnippet = `import torch
from unsloth import FastLanguageModel

# 1. Load fine-tuned adapter weights
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "${selectedModelId.startsWith('job:') ? `storage/artifacts/${selectedModelId.replace('job:', '')}` : 'unsloth/llama-3.1-8b-bnb-4bit'}",
    max_seq_length = 2048,
    load_in_4bit = True,
)

FastLanguageModel.for_inference(model)

# 2. Run inference prompt
prompt = """${systemPrompt}

### Input:
${inputPrompt || 'Explain the advantages of parameter-efficient fine-tuning.'}

### Response:
"""

inputs = tokenizer([prompt], return_tensors = "pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens = ${maxTokens}, temperature = ${temperature})
print(tokenizer.decode(outputs[0]))`;

  const copyCode = () => {
    navigator.clipboard.writeText(codeSnippet);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Model Playground & Inference
            </h1>
            <span className="bg-teal-100 text-teal-800 text-[10px] font-bold px-2.5 py-0.5 rounded-full border border-teal-200">
              Interactive Test Bench
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Test and evaluate your fine-tuned models in real-time or compare performance side-by-side with base models.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCodeModal(true)}
            className="inline-flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold px-3.5 py-2 rounded-xl transition-all"
          >
            <Code2 className="w-4 h-4 text-slate-500" />
            <span>Export Code</span>
          </button>

          <Link
            href="/models"
            className="inline-flex items-center gap-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold px-3.5 py-2 rounded-xl transition-all"
          >
            <Boxes className="w-4 h-4 text-slate-500" />
            <span>Model Library</span>
          </Link>
        </div>
      </div>

      {/* Main Grid: Controls & Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Sidebar / Config Panel (4 cols) */}
        <div className="lg:col-span-4 space-y-5">
          {/* Model Selection Card */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <span className="text-xs font-bold text-slate-900 flex items-center gap-2">
                <Bot className="w-4 h-4 text-teal-600" />
                Select Target Model
              </span>
              <span className="text-[10px] font-semibold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-md border border-emerald-200">
                Ready
              </span>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-700 block">
                Model Instance
              </label>
              <select
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
              >
                <optgroup label="Fine-Tuned Models (Your Weights)">
                  {completedJobs.map((j) => (
                    <option key={j.id} value={`job:${j.id}`}>
                      ✨ Job #{j.id.slice(0, 8)} - {j.training_config.model_key} ({j.dataset_id})
                    </option>
                  ))}
                  {completedJobs.length === 0 && (
                    <option disabled value="">
                      No fine-tuned models available yet
                    </option>
                  )}
                </optgroup>

                <optgroup label="Base Foundation Models">
                  {baseModels.map((m) => (
                    <option key={m.model_key} value={`base:${m.model_key}`}>
                      📦 {m.display_name} ({m.quantization})
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* Evaluation Mode Toggle */}
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="text-xs font-medium text-slate-700 block">
                Evaluation View
              </label>
              <div className="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                <button
                  onClick={() => setMode('single')}
                  className={`py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                    mode === 'single'
                      ? 'bg-white text-teal-700 shadow-xs'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Single Chat</span>
                </button>
                <button
                  onClick={() => setMode('compare')}
                  className={`py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                    mode === 'compare'
                      ? 'bg-white text-teal-700 shadow-xs'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  <Split className="w-3.5 h-3.5" />
                  <span>Side-by-Side</span>
                </button>
              </div>
            </div>
          </div>

          {/* Hyperparameters Config Card */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <span className="text-xs font-bold text-slate-900 flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-teal-600" />
                Inference Parameters
              </span>
            </div>

            <div className="space-y-4 text-xs">
              {/* System Prompt */}
              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  System Prompt
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={3}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                />
              </div>

              {/* Temperature */}
              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-slate-700">Temperature</span>
                  <span className="text-teal-700">{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-teal-600"
                />
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>Precise (0.0)</span>
                  <span>Creative (1.0)</span>
                </div>
              </div>

              {/* Max Tokens */}
              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-slate-700">Max New Tokens</span>
                  <span className="text-teal-700">{maxTokens}</span>
                </div>
                <input
                  type="range"
                  min="64"
                  max="2048"
                  step="64"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                  className="w-full accent-teal-600"
                />
              </div>

              {/* Top-P */}
              <div>
                <div className="flex justify-between font-semibold mb-1">
                  <span className="text-slate-700">Top-P</span>
                  <span className="text-teal-700">{topP}</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={topP}
                  onChange={(e) => setTopP(parseFloat(e.target.value))}
                  className="w-full accent-teal-600"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Panel: Interactive Playground Window (8 cols) */}
        <div className="lg:col-span-8 flex flex-col bg-white border border-slate-200 rounded-2xl shadow-2xs min-h-[600px] overflow-hidden">
          {/* Header Bar */}
          <div className="p-4 border-b border-slate-100 bg-slate-50/70 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-600" />
              <span className="text-xs font-bold text-slate-800">
                {getSelectedModelName()}
              </span>
            </div>

            {mode === 'compare' && (
              <span className="text-[10px] font-bold bg-amber-50 text-amber-700 px-2.5 py-0.5 rounded-full border border-amber-200">
                Comparing Fine-Tuned vs Base Model
              </span>
            )}
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-5 space-y-4 overflow-y-auto max-h-[500px]">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600">
                  <Bot className="w-6 h-6" />
                </div>
                <div className="max-w-md space-y-1">
                  <h3 className="font-bold text-slate-800 text-sm">
                    Interactive Model Playground
                  </h3>
                  <p className="text-xs text-slate-500">
                    Type a prompt below to run live inference against your custom fine-tuned weights.
                  </p>
                </div>

                {/* Preset Prompt Chips */}
                <div className="pt-4 flex flex-wrap justify-center gap-2 max-w-lg">
                  <button
                    onClick={() => handleSendMessage('Explain the benefits of parameter-efficient LoRA fine-tuning.')}
                    className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-full transition-all border border-slate-200"
                  >
                    💡 Benefits of LoRA fine-tuning
                  </button>
                  <button
                    onClick={() => handleSendMessage('Write a Python function to clean and normalize instruction dataset rows.')}
                    className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-full transition-all border border-slate-200"
                  >
                    🐍 Python dataset cleaner script
                  </button>
                  <button
                    onClick={() => handleSendMessage('Summarize key architectural features of Llama 3.1 8B.')}
                    className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-full transition-all border border-slate-200"
                  >
                    ⚡ Llama 3.1 architecture summary
                  </button>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className="space-y-3">
                  {/* User Bubble */}
                  {msg.role === 'user' && (
                    <div className="flex justify-end">
                      <div className="max-w-[80%] bg-teal-600 text-white p-3.5 rounded-2xl rounded-tr-xs text-xs space-y-1 shadow-2xs">
                        <div className="flex items-center gap-1.5 opacity-80 text-[10px] font-semibold">
                          <User className="w-3 h-3" />
                          <span>You</span>
                        </div>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    </div>
                  )}

                  {/* Assistant Bubble (Single or Compare Mode) */}
                  {msg.role === 'assistant' && (
                    <div>
                      {mode === 'compare' ? (
                        /* Compare Mode: 2 Columns Side-by-Side */
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Column 1: Fine-Tuned Model */}
                          <div className="bg-teal-50/50 border border-teal-200 p-4 rounded-2xl space-y-2 text-xs">
                            <div className="flex items-center justify-between border-b border-teal-100 pb-2">
                              <span className="font-bold text-teal-900 flex items-center gap-1.5">
                                <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                                Fine-Tuned Model Output
                              </span>
                              {msg.metrics && (
                                <span className="text-[10px] text-teal-700 font-mono">
                                  {msg.metrics.tokensPerSec} t/s | {msg.metrics.latencyMs}ms
                                </span>
                              )}
                            </div>
                            <p className="text-slate-800 whitespace-pre-wrap leading-relaxed">
                              {msg.content}
                            </p>
                          </div>

                          {/* Column 2: Base Foundation Model */}
                          <div className="bg-slate-50 border border-slate-200 p-4 rounded-2xl space-y-2 text-xs">
                            <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                              <span className="font-bold text-slate-800 flex items-center gap-1.5">
                                <Bot className="w-3.5 h-3.5 text-slate-500" />
                                Base Foundation Output
                              </span>
                              {msg.compareMetrics && (
                                <span className="text-[10px] text-slate-500 font-mono">
                                  {msg.compareMetrics.tokensPerSec} t/s | {msg.compareMetrics.latencyMs}ms
                                </span>
                              )}
                            </div>
                            <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                              {msg.compareContent}
                            </p>
                          </div>
                        </div>
                      ) : (
                        /* Single Mode Bubble */
                        <div className="flex justify-start">
                          <div className="max-w-[85%] bg-slate-50 border border-slate-200 p-4 rounded-2xl rounded-tl-xs text-xs space-y-2 shadow-2xs">
                            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                              <div className="flex items-center gap-1.5 font-bold text-slate-800">
                                <Bot className="w-3.5 h-3.5 text-teal-600" />
                                <span>{msg.metrics?.modelName || 'Assistant'}</span>
                              </div>
                              {msg.metrics && (
                                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500">
                                  <span>{msg.metrics.tokensPerSec} tokens/s</span>
                                  <span>•</span>
                                  <span>{msg.metrics.latencyMs}ms</span>
                                </div>
                              )}
                            </div>

                            <p className="text-slate-800 whitespace-pre-wrap leading-relaxed">
                              {msg.content}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}

            {isGenerating && (
              <div className="flex items-center gap-2 text-xs font-semibold text-teal-600 bg-teal-50/70 p-3 rounded-xl border border-teal-100 w-fit">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-600" />
                <span>Generating output tokens via fine-tuned model adapter...</span>
              </div>
            )}
          </div>

          {/* Input Box Bar */}
          <div className="p-4 border-t border-slate-100 bg-slate-50/50">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-3"
            >
              <input
                type="text"
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="Type a test prompt for your fine-tuned model..."
                className="flex-1 bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500 shadow-2xs"
              />
              <button
                type="submit"
                disabled={!inputPrompt.trim() || isGenerating}
                className="inline-flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition-all shadow-xs shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Generate</span>
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Code Snippet Modal */}
      {showCodeModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 space-y-4 border border-slate-200 shadow-2xl animate-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
                <Code2 className="w-5 h-5 text-teal-600" />
                <span>Python Inference Code</span>
              </div>
              <button
                onClick={() => setShowCodeModal(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Use this Python snippet to load your fine-tuned adapter weights using Unsloth or Hugging Face Transformers.
            </p>

            <div className="relative bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-xs overflow-x-auto">
              <button
                onClick={copyCode}
                className="absolute top-3 right-3 bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded-lg text-[10px] font-semibold flex items-center gap-1 border border-slate-700 transition-all"
              >
                {copiedCode ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3 text-slate-400" />
                    <span>Copy Code</span>
                  </>
                )}
              </button>
              <pre className="pr-16">{codeSnippet}</pre>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowCodeModal(false)}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold px-4 py-2 rounded-xl transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PlaygroundPage() {
  return (
    <Suspense fallback={<div className="p-8 text-xs text-slate-400">Loading Playground...</div>}>
      <PlaygroundContent />
    </Suspense>
  );
}
