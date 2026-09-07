'use client';

import Image from 'next/image';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { ArrowRight, Boxes, CheckCircle2, Database, Gauge, Layers3, LineChart, LockKeyhole, Sparkles, TerminalSquare } from 'lucide-react';

const capabilities = [
  { icon: Database, title: 'Dataset workspace', text: 'Discover, inspect, normalize, and prepare training data in one place.' },
  { icon: Layers3, title: 'QLoRA fine-tuning', text: 'Configure efficient adapters for supported foundation models.' },
  { icon: LineChart, title: 'Live training signals', text: 'Follow loss, progress, events, checkpoints, and GPU activity as work runs.' },
  { icon: Boxes, title: 'Model lifecycle', text: 'Keep base models, custom adapters, artifacts, and testing workflows connected.' },
];

const workflow = [
  ['01', 'Choose a foundation model'], ['02', 'Prepare a dataset'], ['03', 'Configure and launch training'], ['04', 'Review checkpoints and artifacts'],
];

export default function LandingPage() {
  const { user, loading, openAuth } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading && user) router.replace('/dashboard'); }, [loading, router, user]);

  return <div className="min-h-screen bg-[#1e1e1e] text-slate-950">
    <header className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8">
      <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 text-white shadow-sm"><Sparkles className="h-4 w-4" /></div><span className="text-base font-bold">FineTuner</span></div>
      <div className="flex items-center gap-2"><button onClick={() => openAuth('login')} className="px-3 py-2 text-sm font-semibold text-slate-700 hover:text-slate-950">Sign in</button><button onClick={() => openAuth('register')} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">Create account</button></div>
    </header>
    <main>
      <section className="mx-auto grid max-w-7xl gap-12 px-5 pb-20 pt-12 sm:px-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-center lg:pt-20">
        <div className="max-w-xl"><div className="mb-6 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-bold text-teal-800"><Gauge className="h-3.5 w-3.5" /> Managed fine-tuning workspace</div><h1 className="text-4xl font-bold leading-tight sm:text-5xl">Turn your training data into models your team can use.</h1><p className="mt-6 max-w-lg text-base leading-7 text-slate-600">FineTuner brings datasets, model selection, training operations, and output artifacts into one practical workspace for custom LLMs.</p><div className="mt-8 flex flex-wrap gap-3"><button onClick={() => openAuth('register')} className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-teal-700">Start fine-tuning <ArrowRight className="h-4 w-4" /></button><button onClick={() => openAuth('login')} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-bold text-slate-800 hover:bg-slate-50"><LockKeyhole className="h-4 w-4" /> Access workspace</button></div><div className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-600"><span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-teal-600" /> Model-ready datasets</span><span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-teal-600" /> Checkpoints and metrics</span></div></div>
        <div className="relative"><div className="absolute -inset-4 -z-10 bg-[#007acc]/15 blur-3xl" /><Image src="/images/training-console.png" alt="Fine-tuning workspace showing training progress and model metrics" width={1536} height={1024} priority className="w-full rounded-lg border border-[#3e3e42] shadow-2xl" /></div>
      </section>
      <section className="border-y border-slate-200 bg-white"><div className="mx-auto grid max-w-7xl gap-8 px-5 py-14 sm:px-8 md:grid-cols-2 lg:grid-cols-4">{capabilities.map(({ icon: Icon, title, text }) => <div key={title}><div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-teal-700"><Icon className="h-5 w-5" /></div><h2 className="text-sm font-bold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></div>)}</div></section>
      <section className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[0.8fr_1.2fr]"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">A connected workflow</p><h2 className="mt-3 text-3xl font-bold leading-tight">From a raw dataset to a tested model adapter.</h2><p className="mt-4 text-sm leading-6 text-slate-600">The workspace keeps the important parts of each run visible, so training decisions have their data and outputs close at hand.</p></div><div className="border-l border-slate-200">{workflow.map(([number, label]) => <div key={number} className="flex items-center gap-5 border-b border-slate-200 py-5 pl-5 first:pt-0 last:border-b-0"><span className="font-mono text-sm font-bold text-teal-700">{number}</span><span className="text-sm font-semibold text-slate-800">{label}</span></div>)}</div></section>
      <section className="border-t border-slate-200 bg-slate-950"><div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-5 py-14 sm:px-8 md:flex-row md:items-center"><div><TerminalSquare className="mb-3 h-5 w-5 text-teal-300" /><h2 className="text-2xl font-bold text-white">Your model operations, in one place.</h2></div><button onClick={() => openAuth('register')} className="inline-flex items-center gap-2 rounded-lg bg-teal-400 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-teal-300">Create your account <ArrowRight className="h-4 w-4" /></button></div></section>
    </main>
  </div>;
}
