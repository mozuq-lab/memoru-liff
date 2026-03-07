/**
 * TypeScript type definitions for AI Tutor feature.
 */

export type LearningMode = "free_talk" | "quiz" | "weak_point";

export type SessionStatus = "active" | "ended" | "timed_out";

export interface TutorMessage {
  role: "user" | "assistant";
  content: string;
  related_cards: string[];
  timestamp: string;
}

export interface TutorSession {
  session_id: string;
  deck_id: string;
  mode: LearningMode;
  status: SessionStatus;
  messages: TutorMessage[];
  message_count: number;
  created_at: string;
  updated_at: string;
  ended_at: string | null;
}

export interface StartSessionRequest {
  deck_id: string;
  mode: LearningMode;
}

export interface SendMessageRequest {
  content: string;
}

export interface SendMessageResponse {
  message: TutorMessage;
  session_id: string;
  message_count: number;
  is_limit_reached: boolean;
}

export interface SessionListResponse {
  sessions: TutorSession[];
}
