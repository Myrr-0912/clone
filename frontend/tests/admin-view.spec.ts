import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import AdminView from "@/views/AdminView.vue";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("AdminView", () => {
  it("renders resource summary and rows", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        vectorDbCount: 2,
        totalVectorDbSizeBytes: 4096,
        totalVoiceModelSizeBytes: 2048,
        resources: [
          {
            userId: "u1",
            username: "alice",
            cloneId: "c1",
            cloneName: "Dad",
            vectorDbName: "alice-dad",
            chunkCount: 3,
            vectorDbSizeBytes: 1024,
            voiceModelStatus: "ready",
            voiceModelSizeBytes: 512,
          },
        ],
      })
    );

    const wrapper = mount(AdminView);
    await flushPromises();

    expect(wrapper.get("[data-testid=admin-vector-count]").text()).toBe("2");
    expect(wrapper.get("[data-testid=admin-total-vector-size]").text()).toBe("4.00 KB");
    expect(wrapper.get("[data-testid=admin-total-voice-size]").text()).toBe("2.00 KB");
    expect(wrapper.text()).toContain("alice");
    expect(wrapper.text()).toContain("Dad");
    expect(wrapper.text()).toContain("ready");
  });

  it("shows error badge if request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 403,
      text: () => Promise.resolve(JSON.stringify({ error: "Admin role required" })),
    } as unknown as Response);

    const wrapper = mount(AdminView);
    await flushPromises();

    const badge = wrapper.get("[data-testid=admin-refresh-state]");
    expect(badge.classes()).toContain("error");
    expect(badge.text()).toContain("Admin role required");
  });
});
