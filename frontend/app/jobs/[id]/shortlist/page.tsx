// Phase 6 will replace this stub with: ranked candidate cards + weight sliders + CSV export.
export default function ShortlistPage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-8">
      <h1 className="text-2xl font-semibold">Shortlist for job {params.id}</h1>
      <p className="text-slate-500">Ranked cards arrive in Phase 6.</p>
    </main>
  );
}
