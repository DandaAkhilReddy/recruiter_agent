"use client";

import { useMemo, useState } from "react";

export interface StreamTurn {
  candidate_id: string;
  candidate_name: string;
  role: "recruiter" | "candidate";
  content: string;
  turn_index: number;
  ts: string;
}

export function ConversationStream({ turns }: { turns: StreamTurn[] }) {
  const candidates = useMemo(() => {
    const seen = new Map<string, string>();
    turns.forEach((t) => {
      if (!seen.has(t.candidate_id)) seen.set(t.candidate_id, t.candidate_name);
    });
    return Array.from(seen.entries());
  }, [turns]);

  const [filter, setFilter] = useState<string>("all");
  const visible = filter === "all" ? turns : turns.filter((t) => t.candidate_id === filter);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3 text-sm">
        <label className="text-slate-600">Filter:</label>
        <select
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All candidates ({candidates.length})</option>
          {candidates.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-slate-500">{visible.length} messages</span>
      </div>

      <div className="flex max-h-[60vh] flex-col gap-2 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3">
        {visible.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-400">Waiting for first turn...</div>
        )}
        {visible.map((t, i) => (
          <div
            key={`${t.candidate_id}-${t.turn_index}-${i}`}
            className={`flex ${t.role === "recruiter" ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm shadow-sm ${
                t.role === "recruiter"
                  ? "bg-slate-100 text-slate-800"
                  : "bg-accent text-white"
              }`}
            >
              <div className="mb-0.5 text-[10px] uppercase opacity-70">
                {t.role === "recruiter" ? "Recruiter" : t.candidate_name}
              </div>
              <div className="whitespace-pre-wrap">{t.content}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
