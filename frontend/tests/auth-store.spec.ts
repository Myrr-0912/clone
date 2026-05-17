import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

import { useAuthStore } from "@/stores/auth";

beforeEach(() => {
  setActivePinia(createPinia());
});

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

describe("useAuthStore", () => {
  it("populates user from /api/auth/me", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, { user: { id: "1", username: "alice", role: "user" } })
    );
    const store = useAuthStore();

    const user = await store.refresh();
    expect(user).toEqual({ id: "1", username: "alice", role: "user" });
    expect(store.isAuthenticated).toBe(true);
    expect(store.isAdmin).toBe(false);
  });

  it("marks loaded even when /api/auth/me fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(500, { error: "boom" }));
    const store = useAuthStore();

    const user = await store.refresh();
    expect(user).toBeNull();
    expect(store.loaded).toBe(true);
  });

  it("sets admin role after successful login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, { user: { id: "2", username: "root", role: "admin" } })
    );
    const store = useAuthStore();

    const user = await store.login("root", "pw");
    expect(user.role).toBe("admin");
    expect(store.isAdmin).toBe(true);
  });

  it("clears user after logout, even if the request throws", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, { user: { id: "3", username: "bob", role: "user" } }))
      .mockRejectedValueOnce(new Error("network down"));
    const store = useAuthStore();
    await store.login("bob", "pw");

    await expect(store.logout()).rejects.toBeInstanceOf(Error);
    expect(store.user).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
