<script setup lang="ts">
import { computed, ref } from "vue";

import { useClonesStore } from "@/stores/clones";
import { filesToUploadPayloads } from "@/composables/useFileReader";
import { useVoiceRecorder } from "@/composables/useVoiceRecorder";

const props = defineProps<{ cloneId: string | null }>();
const emit = defineEmits<{
  status: [message: string, isError?: boolean];
}>();

const clones = useClonesStore();
const recorder = useVoiceRecorder();

const pickedFiles = ref<File[]>([]);
const busy = ref(false);

const hasPicked = computed(() => pickedFiles.value.length + recorder.recordedFiles.value!.length > 0);

function onFiles(event: Event): void {
  const list = (event.target as HTMLInputElement).files;
  pickedFiles.value = list ? Array.from(list) : [];
}

async function toggleRecording(): Promise<void> {
  if (recorder.isRecording.value) {
    recorder.stop();
    return;
  }
  try {
    await recorder.start();
  } catch (error) {
    emit("status", (error as Error).message, true);
  }
}

async function upload(): Promise<void> {
  if (!props.cloneId) return;
  if (!hasPicked.value) {
    emit("status", "请先选择或录制语音样本", true);
    return;
  }
  busy.value = true;
  try {
    const payloads = await filesToUploadPayloads(
      [...pickedFiles.value, ...recorder.recordedFiles.value!],
      "无法读取声音文件"
    );
    const voice = await clones.uploadVoiceSamples(props.cloneId, payloads);
    pickedFiles.value = [];
    recorder.clear();
    emit("status", voice?.message || "语音样本已保存");
  } catch (error) {
    emit("status", (error as Error).message, true);
  } finally {
    busy.value = false;
  }
}

async function train(): Promise<void> {
  if (!props.cloneId) return;
  busy.value = true;
  try {
    const voice = await clones.trainVoice(props.cloneId);
    emit("status", voice.message || "训练完成", isErrorStatus(voice.status));
  } catch (error) {
    emit("status", (error as Error).message, true);
  } finally {
    busy.value = false;
  }
}

async function refresh(): Promise<void> {
  if (!props.cloneId) return;
  busy.value = true;
  try {
    const voice = await clones.refreshVoiceStatus(props.cloneId);
    emit("status", voice.message || "已刷新", isErrorStatus(voice.status));
  } catch (error) {
    emit("status", (error as Error).message, true);
  } finally {
    busy.value = false;
  }
}

function isErrorStatus(status?: string): boolean {
  return ["error", "failed", "missing_samples", "pending_adapter", "pending_backend", "unavailable"].includes(
    String(status || "")
  );
}
</script>

<template>
  <section class="panel" aria-labelledby="voice-actions-title">
    <div class="section-head">
      <h2 id="voice-actions-title">追加语音样本与训练</h2>
      <span class="badge">VoxCPM</span>
    </div>
    <p v-if="!cloneId" class="empty">先创建或加载一个克隆人。</p>
    <template v-else>
      <label>
        <span>追加语音文件</span>
        <input
          type="file"
          accept="audio/*,.wav,.mp3,.m4a,.ogg"
          multiple
          @change="onFiles"
        />
      </label>
      <div class="record-panel">
        <button
          class="secondary compact-button"
          type="button"
          @click="toggleRecording"
        >
          {{ recorder.isRecording.value ? "停止录制" : "录制语音样本" }}
        </button>
        <span class="recording-state">{{ recorder.message.value }}</span>
      </div>
      <ul class="sample-list">
        <li v-if="!hasPicked">尚未选择新的样本</li>
        <li v-for="file in pickedFiles" :key="`p-${file.name}`">{{ file.name }}</li>
        <li v-for="file in recorder.recordedFiles.value" :key="`r-${file.name}`">{{ file.name }}</li>
      </ul>
      <div class="sample-actions">
        <button
          class="secondary compact-button"
          type="button"
          :disabled="!hasPicked || busy"
          @click="upload"
        >
          保存样本
        </button>
        <button
          class="secondary compact-button"
          type="button"
          :disabled="busy"
          @click="train"
        >
          训练音色
        </button>
        <button
          class="secondary compact-button"
          type="button"
          :disabled="busy"
          @click="refresh"
        >
          刷新状态
        </button>
      </div>
    </template>
  </section>
</template>
