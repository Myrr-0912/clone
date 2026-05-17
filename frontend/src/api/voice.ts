import { get, post } from "./client";
import type { CloneProfile, UploadedFile, VoiceStatus } from "@/types";

export interface VoiceStatusResponse {
  voice: VoiceStatus;
  clone: CloneProfile;
}

export interface VoiceSamplesResponse {
  voice: VoiceStatus | null;
  clone: CloneProfile;
}

export function getVoiceStatus(cloneId: string): Promise<VoiceStatusResponse> {
  return get<VoiceStatusResponse>(`/api/v1/clones/${encodeURIComponent(cloneId)}/voice/status`);
}

export function uploadVoiceSamples(
  cloneId: string,
  voiceFiles: UploadedFile[]
): Promise<VoiceSamplesResponse> {
  return post<VoiceSamplesResponse>(
    `/api/v1/clones/${encodeURIComponent(cloneId)}/voice/samples`,
    { voiceFiles }
  );
}

export function trainVoiceModel(cloneId: string): Promise<VoiceStatusResponse> {
  return post<VoiceStatusResponse>(`/api/v1/clones/${encodeURIComponent(cloneId)}/voice/train`);
}
