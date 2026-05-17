import { get } from "./client";
import type { AdminSummary } from "@/types";

export function fetchAdminSummary(): Promise<AdminSummary> {
  return get<AdminSummary>("/api/admin/vector-dbs");
}
