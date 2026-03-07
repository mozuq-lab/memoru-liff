/**
 * Tutor API client — convenience wrappers for AI Tutor endpoints.
 *
 * All functions delegate to apiClient tutor methods.
 */

import type {
  TutorSession,
  StartSessionRequest,
  SendMessageRequest,
  SendMessageResponse,
  SessionListResponse,
} from "@/types";
import { apiClient } from "./api";

export async function startSession(
  data: StartSessionRequest,
): Promise<TutorSession> {
  return apiClient.startTutorSession(data);
}

export async function sendMessage(
  sessionId: string,
  data: SendMessageRequest,
): Promise<SendMessageResponse> {
  return apiClient.sendTutorMessage(sessionId, data);
}

export async function endSession(sessionId: string): Promise<TutorSession> {
  return apiClient.endTutorSession(sessionId);
}

export async function listSessions(
  status?: string,
  deckId?: string,
): Promise<SessionListResponse> {
  return apiClient.listTutorSessions(status, deckId);
}

export async function getSession(sessionId: string): Promise<TutorSession> {
  return apiClient.getTutorSession(sessionId);
}
