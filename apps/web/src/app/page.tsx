const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  return (
    <main className="min-h-screen">
      <header className="border-b border-[var(--border)] bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-medium text-[var(--accent)]">LLM Fine-Tuner</p>
            <h1 className="text-2xl font-semibold tracking-normal">Workspace</h1>
          </div>
          <a
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--accent-dark)]"
            href={`${apiBaseUrl}/docs`}
          >
            API Docs
          </a>
        </div>
      </header>
      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 md:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-6">
          <h2 className="text-lg font-semibold">Phase 1 Foundation</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Authentication, API configuration, database connectivity, cache wiring, and deployment
            scaffolding are ready for the next product workflows.
          </p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-6">
          <h2 className="text-lg font-semibold">Service Status</h2>
          <dl className="mt-4 grid gap-3 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-[var(--muted)]">Frontend</dt>
              <dd className="font-medium">Ready</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-[var(--muted)]">FastAPI</dt>
              <dd className="font-medium">Configured</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-[var(--muted)]">Training</dt>
              <dd className="font-medium">Not implemented</dd>
            </div>
          </dl>
        </div>
      </section>
    </main>
  );
}
