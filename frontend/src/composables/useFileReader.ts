import type { UploadedFile } from "@/types";

export function readAsDataUrl(file: File, errorMessage = "无法读取本地文件"): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error(errorMessage));
    reader.readAsDataURL(file);
  });
}

export function readAsText(file: File, errorMessage = "无法读取聊天文本文件"): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error(errorMessage));
    reader.readAsText(file, "utf-8");
  });
}

export async function filesToUploadPayloads(
  files: Iterable<File>,
  errorMessage = "无法读取本地文件"
): Promise<UploadedFile[]> {
  const list = Array.from(files);
  return Promise.all(
    list.map(async (file) => ({
      name: file.name,
      data: await readAsDataUrl(file, errorMessage),
    }))
  );
}
