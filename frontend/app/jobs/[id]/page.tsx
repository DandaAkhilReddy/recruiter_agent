// Phase 6 will replace this stub with: 4-stage timeline + live SSE conversation stream.
export default function JobLivePage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-8">
      <h1 className="text-2xl font-semibold">Job {params.id}</h1>
      <p className="text-slate-500">
        Live pipeline view — Parsing → Matching → Outreach → Ranking. SSE wiring lands in Phase 6.
      </p>
    </main>
  );
}
