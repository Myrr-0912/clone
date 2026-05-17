import { describe, expect, it } from "vitest";

import { filesToUploadPayloads, readAsDataUrl, readAsText } from "@/composables/useFileReader";

function makeFile(content: string, name: string, type = "text/plain"): File {
  return new File([content], name, { type });
}

describe("useFileReader", () => {
  it("reads text content from a File", async () => {
    const file = makeFile("hello", "chat.txt");
    const text = await readAsText(file);
    expect(text).toBe("hello");
  });

  it("returns a data URL for binary files", async () => {
    const file = makeFile("RIFF", "voice.wav", "audio/wav");
    const url = await readAsDataUrl(file);
    expect(url.startsWith("data:audio/wav")).toBe(true);
  });

  it("converts multiple files into upload payloads", async () => {
    const files = [makeFile("a", "a.wav", "audio/wav"), makeFile("b", "b.wav", "audio/wav")];
    const payloads = await filesToUploadPayloads(files);
    expect(payloads.map((file) => file.name)).toEqual(["a.wav", "b.wav"]);
    payloads.forEach((file) => {
      expect(file.data.startsWith("data:audio/wav")).toBe(true);
    });
  });
});
