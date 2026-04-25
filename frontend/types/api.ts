// Mirrors backend Pydantic schemas. Keep in sync when backend types change.

export type Seniority = "junior" | "mid" | "senior" | "staff" | "principal";
export type DimKey = "skill" | "experience" | "domain" | "location";

export interface JobOut {
  id: string;
  title: string | null;
  seniority: string | null;
  min_yoe: number | null;
  must_have_skills: string[];
  nice_to_have: string[];
  domain: string | null;
  location_pref: string | null;
  remote_ok: boolean;
  status: string;
  created_at: string;
}

export interface CandidateBrief {
  id: string;
  name: string;
  title: string;
  yoe: number;
  seniority: string;
  skills: string[];
  location: string | null;
  remote_ok: boolean;
}

export interface ScoreOut {
  rank: number;
  candidate: CandidateBrief;
  match_score: number;
  breakdown: Record<DimKey, number>;
  justifications: Record<DimKey, string>;
}

export interface MatchOut {
  job_id: string;
  matched_count: number;
  rerank_count: number;
  top: ScoreOut[];
}

export interface ShortlistItem {
  rank: number;
  candidate: CandidateBrief;
  match_score: number | null;
  interest_score: number | null;
  final_score: number | null;
  breakdown: Record<DimKey, number> | null;
  match_justifications: Record<string, string> | null;
  interest_signals: string[] | null;
  interest_concerns: string[] | null;
  interest_reasoning: string | null;
}

export interface ShortlistOut {
  job_id: string;
  match_weight: number;
  interest_weight: number;
  total: number;
  items: ShortlistItem[];
}

export interface TranscriptMessage {
  role: "recruiter" | "candidate";
  content: string;
  turn_index: number;
  created_at: string;
}

export interface ConversationDetailOut {
  job_id: string;
  candidate: CandidateBrief;
  status: string;
  started_at: string;
  completed_at: string | null;
  interest_score: number | null;
  interest_signals: string[] | null;
  interest_concerns: string[] | null;
  interest_reasoning: string | null;
  messages: TranscriptMessage[];
}

// SSE event payloads
export type SseEvent =
  | { type: "outreach_started"; candidate_count: number; max_turns: number }
  | {
      type: "turn";
      candidate_id: string;
      candidate_name: string;
      role: "recruiter" | "candidate";
      content: string;
      turn_index: number;
      ts: string;
    }
  | { type: "conversation_done"; candidate_id: string; candidate_name: string }
  | { type: "conversation_failed"; candidate_id: string; error: string }
  | {
      type: "judge";
      candidate_id: string;
      candidate_name: string;
      interest_score: number;
      signals: string[];
      concerns: string[];
      reasoning: string;
    }
  | { type: "judge_failed"; candidate_id: string; error: string }
  | { type: "error"; message: string }
  | { type: "done" };
