import type {
  ConversationDetailOut,
  JobOut,
  MatchOut,
  ShortlistOut,
} from "@/types/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = `${res.status}: ${body.detail}`;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  createJob: (raw_text: string) =>
    request<JobOut>("/jobs", { method: "POST", body: JSON.stringify({ raw_text }) }),

  getJob: (id: string) => request<JobOut>(`/jobs/${id}`),

  runMatch: (id: string) =>
    request<MatchOut>(`/jobs/${id}/match`, { method: "POST", body: JSON.stringify({}) }),

  startOutreach: (id: string) =>
    request<{ job_id: string; started: boolean; top_k: number; max_turns: number }>(
      `/jobs/${id}/outreach`,
      { method: "POST", body: JSON.stringify({}) },
    ),

  getShortlist: (id: string, opts?: { limit?: number; match_w?: number; interest_w?: number }) => {
    const q = new URLSearchParams();
    if (opts?.limit) q.set("limit", String(opts.limit));
    if (opts?.match_w !== undefined) q.set("match_w", opts.match_w.toFixed(2));
    if (opts?.interest_w !== undefined) q.set("interest_w", opts.interest_w.toFixed(2));
    const qs = q.toString();
    return request<ShortlistOut>(`/jobs/${id}/shortlist${qs ? `?${qs}` : ""}`);
  },

  shortlistCsvUrl: (id: string, opts?: { match_w?: number; interest_w?: number }) => {
    const q = new URLSearchParams();
    if (opts?.match_w !== undefined) q.set("match_w", opts.match_w.toFixed(2));
    if (opts?.interest_w !== undefined) q.set("interest_w", opts.interest_w.toFixed(2));
    const qs = q.toString();
    return `${API}/jobs/${id}/shortlist.csv${qs ? `?${qs}` : ""}`;
  },

  getConversation: (job_id: string, candidate_id: string) =>
    request<ConversationDetailOut>(`/jobs/${job_id}/conversations/${candidate_id}`),

  streamUrl: (id: string) => `${API}/jobs/${id}/stream`,
};
