import { del, get, post, put } from "./client";
import type { CloneProfile, UploadedFile } from "@/types";

export interface CloneListResponse {
  clones: CloneProfile[];
}

export interface CloneResponse {
  clone: CloneProfile;
}

export interface CloneCreatePayload {
  targetName: string;
  chatText: string;
  voiceFiles?: UploadedFile[];
  imageFiles?: UploadedFile[];
  videoFiles?: UploadedFile[];
  stickerFiles?: UploadedFile[];
  momentsFiles?: UploadedFile[];
}

export function listClones(): Promise<CloneListResponse> {
  return get<CloneListResponse>("/api/clones");
}

export function getClone(cloneId: string): Promise<CloneResponse> {
  return get<CloneResponse>(`/api/clones/${encodeURIComponent(cloneId)}`);
}

export function createClone(payload: CloneCreatePayload): Promise<CloneResponse> {
  return post<CloneResponse>("/api/clones", payload);
}

export function updateClone(
  cloneId: string,
  payload: Partial<CloneCreatePayload>
): Promise<CloneResponse> {
  return put<CloneResponse>(`/api/clones/${encodeURIComponent(cloneId)}`, payload);
}

export function renameClone(cloneId: string, targetName: string): Promise<CloneResponse> {
  return put<CloneResponse>(`/api/clones/${encodeURIComponent(cloneId)}`, { targetName });
}

export function deleteClone(cloneId: string): Promise<{ ok: boolean; cloneId: string }> {
  return del<{ ok: boolean; cloneId: string }>(`/api/clones/${encodeURIComponent(cloneId)}`);
}
