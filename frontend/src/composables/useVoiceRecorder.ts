import { onBeforeUnmount, ref } from "vue";

export interface RecorderHandle {
  isRecording: ReturnType<typeof ref<boolean>>;
  message: ReturnType<typeof ref<string>>;
  recordedFiles: ReturnType<typeof ref<File[]>>;
  start: () => Promise<void>;
  stop: () => void;
  pop: () => File | undefined;
  clear: () => void;
}

export function useVoiceRecorder(): RecorderHandle {
  const isRecording = ref(false);
  const message = ref("麦克风未开始");
  const recordedFiles = ref<File[]>([]);

  let mediaRecorder: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let chunks: BlobPart[] = [];

  function stopStream(): void {
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    mediaRecorder = null;
    chunks = [];
    isRecording.value = false;
  }

  async function start(): Promise<void> {
    if (isRecording.value) return;
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      message.value = "当前浏览器不支持录音，请改为上传音频文件。";
      throw new Error(message.value);
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      stopStream();
      message.value = "无法打开麦克风，请检查浏览器授权。";
      throw new Error(message.value);
    }
    chunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) chunks.push(event.data);
    });
    mediaRecorder.addEventListener("stop", () => save(), { once: true });
    mediaRecorder.start();
    isRecording.value = true;
    message.value = "正在录制...";
  }

  function stop(): void {
    if (mediaRecorder?.state === "recording") {
      mediaRecorder.stop();
    }
  }

  function save(): void {
    try {
      if (!chunks.length) {
        message.value = "录音失败，请重试或上传音频文件。";
        return;
      }
      const mimeType = (chunks[0] as Blob).type || "audio/webm";
      const extension = recordingExtension(mimeType);
      const filename = `recording-${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`;
      const blob = new Blob(chunks, { type: mimeType });
      const file =
        typeof File === "function"
          ? new File([blob], filename, { type: mimeType })
          : (Object.assign(blob, { name: filename }) as unknown as File);
      recordedFiles.value = [...recordedFiles.value, file];
      message.value = `已添加录音样本：${filename}`;
    } finally {
      stopStream();
    }
  }

  function pop(): File | undefined {
    const file = recordedFiles.value.shift();
    recordedFiles.value = [...recordedFiles.value];
    return file;
  }

  function clear(): void {
    recordedFiles.value = [];
    message.value = "麦克风未开始";
  }

  onBeforeUnmount(stopStream);

  return { isRecording, message, recordedFiles, start, stop, pop, clear };
}

function recordingExtension(mimeType: string): string {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("wav")) return "wav";
  if (mimeType.includes("mp4")) return "m4a";
  return "webm";
}
