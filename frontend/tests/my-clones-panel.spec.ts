import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import MyClonesPanel from "@/components/MyClonesPanel.vue";
import type { CloneProfile } from "@/types";

function makeClone(overrides: Partial<CloneProfile> = {}): CloneProfile {
  return {
    cloneId: overrides.cloneId ?? "clone-1",
    name: overrides.name ?? "Target",
    style: {
      catchphrases: [],
      particles: [],
      punctuation: [],
      emoji_style: [],
      message_format: [],
      typing_habits: [],
      address_terms: [],
      example_dialogues: [],
      average_length: 0,
    },
    memory: {
      keyTopics: [],
      key_topics: [],
      summary: "",
      relationship_overview: [],
      timeline: [],
      daily_patterns: [],
      shared_experiences: [],
      inside_jokes: [],
      food_preferences: [],
      interests: [],
      conflict_patterns: [],
      sweet_moments: [],
      breakup_notes: [],
    },
    rules: {},
    corrections: [],
    sourceStats: overrides.sourceStats ?? { target_messages: 12 },
    voice: overrides.voice ?? null,
  };
}

describe("MyClonesPanel", () => {
  it("renders loading state", () => {
    const wrapper = mount(MyClonesPanel, {
      props: { clones: [], loading: true, errorMessage: null, activeCloneId: null },
    });
    expect(wrapper.text()).toContain("正在加载");
  });

  it("renders empty state", () => {
    const wrapper = mount(MyClonesPanel, {
      props: { clones: [], loading: false, errorMessage: null, activeCloneId: null },
    });
    expect(wrapper.text()).toContain("还没有创建克隆人");
  });

  it("emits use/rename/remove for each clone", async () => {
    const clones = [makeClone({ cloneId: "abc", name: "Alpha" })];
    const wrapper = mount(MyClonesPanel, {
      props: { clones, loading: false, errorMessage: null, activeCloneId: "abc" },
    });

    const buttons = wrapper.findAll(".my-clone-actions button");
    expect(buttons).toHaveLength(3);
    await buttons[0].trigger("click");
    await buttons[1].trigger("click");
    await buttons[2].trigger("click");

    expect(wrapper.emitted("use")?.[0]).toEqual(["abc"]);
    expect(wrapper.emitted("rename")?.[0]).toEqual(["abc"]);
    expect(wrapper.emitted("remove")?.[0]).toEqual(["abc"]);
    expect(wrapper.find(".my-clone-item.active").exists()).toBe(true);
  });

  it("emits refresh when the header button is clicked", async () => {
    const wrapper = mount(MyClonesPanel, {
      props: { clones: [], loading: false, errorMessage: null, activeCloneId: null },
    });
    await wrapper.get(".section-head button").trigger("click");
    expect(wrapper.emitted("refresh")).toHaveLength(1);
  });
});
