import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, get, post } from "@/api/client";

afterEach(() => {
  vi.restoreAllMocks();
});

interface MockResponse {
  body: unknown;
  ok: boolean;
  status?: number;
}

function mockFetch(response: MockResponse) {
  const fakeResponse = {
    ok: response.ok,
    status: response.status ?? (response.ok ? 200 : 400),
    text: () =>
      Promise.resolve(typeof response.body === "string" ? response.body : JSON.stringify(response.body)),
  } as unknown as Response;
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(fakeResponse);
}

describe("api client", () => {
  it("attaches Content-Type for JSON requests", async () => {
    const spy = mockFetch({ body: { user: { id: "1", username: "alice", role: "user" } }, ok: true });

    await post("/api/auth/login", { username: "alice", password: "pw" });

    const [, init] = spy.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect((init as RequestInit).credentials).toBe("same-origin");
  });

  it("returns parsed body on success", async () => {
    mockFetch({ body: { clones: [] }, ok: true });

    const body = await get<{ clones: unknown[] }>("/api/clones");
    expect(body).toEqual({ clones: [] });
  });

  it("throws ApiError with the server detail", async () => {
    mockFetch({ body: { error: "Authentication required" }, ok: false, status: 401 });

    await expect(get("/api/clones")).rejects.toMatchObject({
      message: "Authentication required",
      status: 401,
      name: "ApiError",
    });
  });

  it("falls back to FastAPI detail field", async () => {
    mockFetch({ body: { detail: "Clone not found" }, ok: false, status: 404 });

    const error = await get("/api/clones/missing").catch((err: ApiError) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Clone not found");
  });
});
