import { get, post } from "./client";
import type { SessionUser } from "@/types";

export interface MeResponse {
  user: SessionUser | null;
}

export interface AuthResponse {
  user: SessionUser;
}

export function fetchMe(): Promise<MeResponse> {
  return get<MeResponse>("/api/v1/auth/me");
}

export function login(username: string, password: string): Promise<AuthResponse> {
  return post<AuthResponse>("/api/v1/auth/login", { username, password });
}

export function register(username: string, password: string): Promise<AuthResponse> {
  return post<AuthResponse>("/api/v1/auth/register", { username, password });
}

export function logout(): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/v1/auth/logout");
}
