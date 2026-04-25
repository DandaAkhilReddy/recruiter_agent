"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ConversationStream, type StreamTurn } from "@/components/ConversationStream";
import { PipelineTimeline, type Stage } from "@/components/PipelineTimeline";
import { api } from "@/lib/api";
import { useJobStream } from "@/lib/sse";
import type { JobOut, SseEvent } from "@/types/api";

export default function JobLivePage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<JobOut | null>(null);
  const [turns, setTurns] = useState<StreamTurn[]>([]);
  const [judged, setJudged] = useState<Record<string, number>>({});
  const [matchProgress, setMatchProgress] = useState<{ matched: number; rerank: number } | null>(null);
  const [phase, setPhase] = useState<"parsing" | "matching" | "outreach" | "ranking" | "done" | "error">("parsing");
  const [error, setError] = useState<string | null>(null);

  // Stream subscription — opens immediately, replays buffered events.
  useJobStream(api.streamUrl(params.id), (e: SseEvent) => {
    if (e.type === "outreach_started") setPhase("outreach");
    if (e.type === "turn") setTurns((prev) => [...prev, e]);
    if (e.type === "judge") setJudged((j) => ({ ...j, [e.candidate_id]: e.interest_score }));
    if (e.type === "error") {
      setError(e.message);
      setPhase("error");
    }
    if (e.type === "done") setPhase("done");
  });

  // Phase 1: load job, run match, kick off outreach. Idempotency: only run once per id.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const j = await api.getJob(params.id);
        if (cancelled) return;
        setJob(j);
        if (j.status === "parsed" || j.status === "matched") {
          setPhase("matching");
          const m = await api.runMatch(params.id);
          if (cancelled) return;
          setMatchProgress({ matched: m.matched_count, rerank: m.rerank_count });
          setPhase("outreach");
          await api.startOutreach(params.id);
        } else if (j.status === "outreached") {
          setPhase("done");
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "failed to bootstrap pipeline");
          setPhase("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const stages = useMemo<Stage[]>(() => {
    const order = ["parsing", "matching", "outreach", "ranking"];
    const idx = ["parsing", "matching", "outreach", "ranking", "done"].indexOf(phase);
    return [
      { key: "parse", label: "Parsing JD" },
      { key: "match", label: "Matching", detail: matchProgress ? `${matchProgress.rerank}/${matchProgress.matched}` : undefined },
      { key: "outreach", label: "Outreach", detail: turns.length ? `${turns.length} turns` : undefined },
      { key: "ranking", label: "Ranking", detail: Object.keys(judged).length ? `${Object.keys(judged).length} judged` : undefined },
    ].map((s, i): Stage => {
      const state =
        phase === "error"
          ? i <= order.indexOf(phase as any)
            ? "failed"
            : "pending"
          : i < idx
          ? "done"
          : i === idx
          ? "running"
          : "pending";
      return { ...s, state };
    });
  }, [phase, matchProgress, turns.length, judged]);

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-8">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{job?.title ?? "Loading job..."}</h1>
          <p className="text-sm text-slate-500">
            {job?.seniority ? `${job.seniority} · ` : ""}
            {job?.min_yoe ? `${job.min_yoe}+ yoe · ` : ""}
            {job?.must_have_skills?.slice(0, 4).join(", ")}
          </p>
        </div>
        {phase === "done" && (
          <Link
            href={`/jobs/${params.id}/shortlist`}
            className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-accent/90"
          >
            View shortlist →
          </Link>
        )}
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <PipelineTimeline stages={stages} />
      </section>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <section>
        <h2 className="mb-2 text-lg font-semibold">Live conversations</h2>
        <ConversationStream turns={turns} />
      </section>
    </main>
  );
}
