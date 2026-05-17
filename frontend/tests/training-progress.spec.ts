import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import TrainingProgress from "@/components/TrainingProgress.vue";

describe("TrainingProgress", () => {
  it("clamps and renders the percent width", () => {
    const wrapper = mount(TrainingProgress, {
      props: { label: "文本训练进度", caption: "完成", percent: 150, state: "ok" },
    });
    const bar = wrapper.get(".progress-bar");
    expect(bar.attributes("style")).toContain("width: 100%");
    expect(bar.classes()).toContain("ok");
    expect(wrapper.get(".progress-track").attributes("aria-valuenow")).toBe("150");
  });

  it("applies the error class when state is error", () => {
    const wrapper = mount(TrainingProgress, {
      props: { label: "语音训练进度", caption: "失败", percent: 100, state: "error" },
    });
    expect(wrapper.get(".progress-bar").classes()).toContain("error");
    expect(wrapper.get(".progress-panel").attributes("data-state")).toBe("error");
  });

  it("defaults to idle state", () => {
    const wrapper = mount(TrainingProgress, {
      props: { label: "文本训练进度", caption: "等待", percent: 0 },
    });
    expect(wrapper.get(".progress-panel").attributes("data-state")).toBe("idle");
  });
});
