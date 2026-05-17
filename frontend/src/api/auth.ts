import { get, post } from "./client";
import type { SessionUser } from "@/types";

export interface MeResponse {
  user: SessionUser | null;
}

export interface AuthResponse {
  user: SessionUser;
}

export function fetchMe(): Promise<MeResponse> {
  return get<MeResponse>("/api/auth/me");
}

export function login(username: string, password: string): Promise<AuthResponse> {
  return post<AuthResponse>("/api/auth/login", { username, password });
}

export function register(username: string, password: string): Promise<AuthResponse> {
  return post<AuthResponse>("/api/auth/register", { username, password });
}

export function logout(): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/auth/logout");
}
