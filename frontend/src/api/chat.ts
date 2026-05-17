import { post } from "./client";
import type { ChatReply, CloneProfile, SpeechResult } from "@/types";

export interface ChatResponse {
  reply: ChatReply;
  clone?: CloneProfile;
}

export interface SpeakResponse {
  speech: SpeechResult;
}

export function sendChatMessage(cloneId: string, message: string): Promise<ChatResponse> {
  return post<ChatResponse>(`/api/clones/${encodeURIComponent(cloneId)}/chat`, { message });
}

export interface SpeakOptions {
  text: string;
  emotion: string;
  inferenceSteps?: number;
  cfgValue?: number;
}

export function synthesizeSpeech(cloneId: string, options: SpeakOptions): Promise<SpeakResponse> {
  return post<SpeakResponse>(`/api/clones/${encodeURIComponent(cloneId)}/speak`, options);
}
