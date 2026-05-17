import { vi } from "vitest";

// 全局 fetch mock 通过 globalThis.fetch 注入；测试用 vi.spyOn 覆盖即可。
if (!("fetch" in globalThis)) {
  // happy-dom 已自带 fetch；这里仅作占位。
  (globalThis as { fetch?: typeof fetch }).fetch = vi.fn() as unknown as typeof fetch;
}

// 确保 jsdom/happy-dom 下 confirm/prompt 返回值可控（默认值，可在每个用例里覆盖）。
if (typeof window !== "undefined") {
  if (!("confirm" in window)) {
    Object.defineProperty(window, "confirm", { value: () => true, configurable: true });
  }
  if (!("prompt" in window)) {
    Object.defineProperty(window, "prompt", { value: () => "", configurable: true });
  }
}
