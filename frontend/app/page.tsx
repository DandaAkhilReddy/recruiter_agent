export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-4xl font-bold tracking-tight">Recruiter Agent</h1>
      <p className="text-center text-lg text-slate-600">
        Paste a Job Description. Get a ranked shortlist scored on{" "}
        <span className="font-semibold text-accent">Match</span> and{" "}
        <span className="font-semibold text-accent">Interest</span> — with conversational outreach
        simulated live.
      </p>
      <div className="rounded-md border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        JD input form coming in Phase 6. Backend health: <code>{`{API}/health`}</code>.
      </div>
    </main>
  );
}
