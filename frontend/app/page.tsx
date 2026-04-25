"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";

const SAMPLE_JD = `Senior Backend Engineer — Payments Platform

We're a Series B fintech building cross-border payments infrastructure. We
process $400M+ annualized across 18 countries.

You'll design services that move money — latency-sensitive, idempotent,
exactly-once. You'll own the ledger and reconciliation pipeline. Mentor
2-3 mid engineers. On-call 1 week in 6, weekday-only.

Requirements: 6+ years backend (3+ in payments / fintech / trading). Deep
Python (FastAPI) AND/OR Go. PostgreSQL fluency including query plans and
multi-million-row migrations. Comfortable with Kafka. Strong testing
opinions. Production AWS (ECS/EKS, RDS, MSK, IAM) + Terraform.

Bonus: Rust, gRPC, OpenTelemetry, double-entry bookkeeping.

Remote across US (PT-ET), quarterly NYC onsites. $210k-$260k base + equity.`;

export default function HomePage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (text.trim().length < 20) {
      setError("JD must be at least 20 characters");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const job = await api.createJob(text);
      router.push(`/jobs/${job.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "submit failed");
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 p-8">
      <header className="mt-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight">Recruiter Agent</h1>
        <p className="mt-3 text-lg text-slate-600">
          Paste a Job Description. Get a ranked shortlist scored on{" "}
          <span className="font-semibold text-accent">Match</span> and{" "}
          <span className="font-semibold text-accent">Interest</span>, with a live
          conversational pipeline you can watch as it runs.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <label className="text-sm font-medium text-slate-700">Job Description</label>
        <textarea
          className="h-72 w-full rounded-lg border border-slate-300 bg-white p-4 font-mono text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
          placeholder="Paste a JD here..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={20_000}
        />
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>{text.length} / 20,000 chars</span>
          <button
            type="button"
            className="underline hover:text-accent"
            onClick={() => setText(SAMPLE_JD)}
          >
            Use sample JD
          </button>
        </div>
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="mt-2 self-start rounded-md bg-accent px-6 py-2.5 font-medium text-white shadow hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Parsing..." : "Find candidates"}
        </button>
      </section>

      <footer className="mt-auto pt-8 text-center text-xs text-slate-400">
        All candidates are AI-generated for demonstration purposes.
      </footer>
    </main>
  );
}
