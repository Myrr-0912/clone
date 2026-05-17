import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import ChatPanel from "@/components/ChatPanel.vue";

beforeEach(() => {
  setActivePinia(createPinia());
});

function fakeReply(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

describe("ChatPanel", () => {
  it("sends a message and renders both bubbles", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      fakeReply({ reply: { clone_id: "c1", text: "你好呀", emotion: "warm" } })
    );

    const wrapper = mount(ChatPanel, {
      props: { cloneId: "c1", clone: null, inferenceSteps: 4, cfgValue: 2.0 },
    });

    await wrapper.find("[data-testid=message-input]").setValue("hi");
    await wrapper.find("form").trigger("submit.prevent");
    await flushPromises();

    const bubbles = wrapper.findAll(".bubble");
    expect(bubbles).toHaveLength(2);
    expect(bubbles[0].text()).toBe("hi");
    expect(bubbles[0].classes()).toContain("user");
    expect(bubbles[1].text()).toBe("你好呀");
    expect(bubbles[1].classes()).toContain("clone");
  });

  it("disables the input when there is no cloneId", () => {
    const wrapper = mount(ChatPanel, {
      props: { cloneId: null, clone: null, inferenceSteps: 4, cfgValue: 2.0 },
    });
    const input = wrapper.find("[data-testid=message-input]")
      .element as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it("falls back to the error text if the backend returns an error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 502,
      text: () => Promise.resolve(JSON.stringify({ error: "LLM reply failed" })),
    } as unknown as Response);

    const wrapper = mount(ChatPanel, {
      props: { cloneId: "c1", clone: null, inferenceSteps: 4, cfgValue: 2.0 },
    });
    await wrapper.find("[data-testid=message-input]").setValue("hi");
    await wrapper.find("form").trigger("submit.prevent");
    await flushPromises();

    const bubbles = wrapper.findAll(".bubble");
    expect(bubbles[1].text()).toContain("LLM reply failed");
  });
});
