"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ConversationDetailOut, ShortlistItem } from "@/types/api";

const DIM_LABELS = {
  skill: "Skill fit",
  experience: "Experience",
  domain: "Domain",
  location: "Location",
} as const;

export function CandidateCard({ jobId, item }: { jobId: string; item: ShortlistItem }) {
  const [open, setOpen] = useState(false);
  const [convo, setConvo] = useState<ConversationDetailOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || convo) return;
    let cancelled = false;
    api
      .getConversation(jobId, item.candidate.id)
      .then((c) => !cancelled && setConvo(c))
      .catch((e) => !cancelled && setErr(e instanceof Error ? e.message : "failed"));
    return () => {
      cancelled = true;
    };
  }, [open, jobId, item.candidate.id, convo]);

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-slate-50"
      >
        <span className="w-6 text-right text-sm font-semibold text-slate-400">{item.rank}</span>
        <div className="flex-1">
          <div className="font-medium text-slate-900">{item.candidate.name}</div>
          <div className="text-xs text-slate-500">
            {item.candidate.title} · {item.candidate.yoe} yoe · {item.candidate.location ?? "—"}
          </div>
        </div>
        <div className="flex gap-2 text-xs">
          <Pill label="Match" value={item.match_score} color="bg-blue-50 text-blue-700" />
          <Pill label="Interest" value={item.interest_score} color="bg-emerald-50 text-emerald-700" />
          <Pill label="Final" value={item.final_score} color="bg-slate-900 text-white" strong />
        </div>
        <span className="text-slate-400">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="border-t border-slate-100 p-4">
          {item.breakdown && (
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              {(Object.keys(DIM_LABELS) as Array<keyof typeof DIM_LABELS>).map((k) => (
                <div key={k}>
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-slate-700">{DIM_LABELS[k]}</span>
                    <span className="text-slate-500">{Math.round(item.breakdown![k])}</span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-slate-100">
                    <div
                      className="h-full bg-accent"
                      style={{ width: `${Math.min(100, Math.max(0, item.breakdown![k]))}%` }}
                    />
                  </div>
                  {item.match_justifications?.[k] && (
                    <div className="mt-1 text-[11px] text-slate-500">{item.match_justifications[k]}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {(item.interest_signals?.length || item.interest_concerns?.length || item.interest_reasoning) && (
            <div className="mb-4 grid gap-3 md:grid-cols-2">
              <div>
                <div className="text-xs font-semibold uppercase text-emerald-700">Signals</div>
                <ul className="mt-1 list-disc pl-4 text-sm text-slate-700">
                  {(item.interest_signals ?? []).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                  {!item.interest_signals?.length && <li className="text-slate-400">none</li>}
                </ul>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase text-amber-700">Concerns</div>
                <ul className="mt-1 list-disc pl-4 text-sm text-slate-700">
                  {(item.interest_concerns ?? []).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                  {!item.interest_concerns?.length && <li className="text-slate-400">none</li>}
                </ul>
              </div>
              {item.interest_reasoning && (
                <div className="md:col-span-2">
                  <div className="text-xs font-semibold uppercase text-slate-500">Judge reasoning</div>
                  <p className="mt-1 text-sm text-slate-700">{item.interest_reasoning}</p>
                </div>
              )}
            </div>
          )}

          <div>
            <div className="text-xs font-semibold uppercase text-slate-500">Transcript</div>
            {err && <p className="mt-1 text-sm text-red-700">{err}</p>}
            {!convo && !err && <p className="mt-1 text-sm text-slate-400">Loading...</p>}
            {convo && (
              <div className="mt-2 flex flex-col gap-2">
                {convo.messages.map((m) => (
                  <div
                    key={`${m.turn_index}`}
                    className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                      m.role === "recruiter"
                        ? "self-start bg-slate-100 text-slate-800"
                        : "self-end bg-accent text-white"
                    }`}
                  >
                    <div className="mb-0.5 text-[10px] uppercase opacity-70">
                      {m.role === "recruiter" ? "Recruiter" : item.candidate.name}
                    </div>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Pill({
  label,
  value,
  color,
  strong = false,
}: {
  label: string;
  value: number | null;
  color: string;
  strong?: boolean;
}) {
  return (
    <div className={`rounded-md px-2 py-1 ${color} ${strong ? "font-semibold" : ""}`}>
      <span className="opacity-70">{label}</span>{" "}
      <span>{value === null ? "—" : Math.round(value)}</span>
    </div>
  );
}
