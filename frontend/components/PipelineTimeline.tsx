"use client";

export type StageState = "pending" | "running" | "done" | "failed";

export interface Stage {
  key: string;
  label: string;
  state: StageState;
  detail?: string;
}

const dot = (s: StageState) => {
  if (s === "done") return "bg-emerald-500";
  if (s === "running") return "bg-accent animate-pulse";
  if (s === "failed") return "bg-red-500";
  return "bg-slate-300";
};

export function PipelineTimeline({ stages }: { stages: Stage[] }) {
  return (
    <ol className="flex w-full items-center justify-between gap-2">
      {stages.map((s, i) => (
        <li key={s.key} className="flex flex-1 items-center gap-3">
          <div className="flex flex-col items-center">
            <span className={`h-3 w-3 rounded-full ${dot(s.state)}`} />
            <span className="mt-1 text-xs font-medium text-slate-700">{s.label}</span>
            {s.detail && <span className="text-[10px] text-slate-500">{s.detail}</span>}
          </div>
          {i < stages.length - 1 && (
            <div className={`h-px flex-1 ${s.state === "done" ? "bg-emerald-300" : "bg-slate-200"}`} />
          )}
        </li>
      ))}
    </ol>
  );
}
