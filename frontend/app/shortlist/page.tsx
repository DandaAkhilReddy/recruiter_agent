"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { CandidateCard } from "@/components/CandidateCard";
import { WeightSliders, type Weights } from "@/components/WeightSliders";
import { api } from "@/lib/api";
import type { ShortlistOut } from "@/types/api";

function ShortlistInner() {
  const router = useRouter();
  const params = useSearchParams();
  const id = params.get("id") ?? "";

  const [weights, setWeights] = useState<Weights>({ match: 0.6, interest: 0.4 });
  const [data, setData] = useState<ShortlistOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) {
      router.push("/");
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .getShortlist(id, { limit: 20, match_w: weights.match, interest_w: weights.interest })
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setErr(null);
        }
      })
      .catch((e) => !cancelled && setErr(e instanceof Error ? e.message : "failed"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id, weights, router]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-8">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Shortlist</h1>
          <p className="text-sm text-slate-500">
            Job {id.slice(0, 8)}… · {data?.total ?? "—"} candidates scored
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href={`/job?id=${id}`}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            ← Live view
          </Link>
          <a
            href={api.shortlistCsvUrl(id, { match_w: weights.match, interest_w: weights.interest })}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90"
            download
          >
            Export CSV
          </a>
        </div>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <WeightSliders weights={weights} onChange={setWeights} />
      </section>

      {err && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>
      )}

      <section className="flex flex-col gap-2">
        {loading && !data && <div className="text-sm text-slate-500">Loading shortlist...</div>}
        {data?.items.map((item) => (
          <CandidateCard key={item.candidate.id} jobId={id} item={item} />
        ))}
        {data && data.items.length === 0 && (
          <div className="rounded-md border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
            No scored candidates yet — go run the pipeline first.
          </div>
        )}
      </section>
    </main>
  );
}

export default function ShortlistPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-500">Loading...</div>}>
      <ShortlistInner />
    </Suspense>
  );
}
