"use client";

export interface Weights {
  match: number;
  interest: number;
}

export function WeightSliders({
  weights,
  onChange,
}: {
  weights: Weights;
  onChange: (w: Weights) => void;
}) {
  function setMatch(v: number) {
    const m = Math.max(0, Math.min(1, v));
    onChange({ match: round2(m), interest: round2(1 - m) });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">Weighting</span>
        <span className="text-slate-500">
          Match {pct(weights.match)} · Interest {pct(weights.interest)}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={weights.match}
        onChange={(e) => setMatch(Number(e.target.value))}
        className="w-full accent-blue-600"
      />
      <div className="flex justify-between text-[11px] text-slate-400">
        <span>All Interest</span>
        <span>Balanced (default 60/40)</span>
        <span>All Match</span>
      </div>
    </div>
  );
}

function round2(n: number) {
  return Math.round(n * 100) / 100;
}
function pct(n: number) {
  return `${Math.round(n * 100)}%`;
}
