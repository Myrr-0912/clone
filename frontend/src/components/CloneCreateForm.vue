<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { useClonesStore } from "@/stores/clones";
import { filesToUploadPayloads, readAsText } from "@/composables/useFileReader";
import { useVoiceRecorder } from "@/composables/useVoiceRecorder";
import TrainingProgress from "./TrainingProgress.vue";
import type { CloneProfile } from "@/types";

const props = defineProps<{ current: CloneProfile | null }>();
const emit = defineEmits<{
  status: [message: string, isError?: boolean];
  loadById: [cloneId: string];
}>();

const clones = useClonesStore();

const targetName = ref("Target");
const chatText = ref("");
const consent = ref(false);
const cloneIdInput = ref("");
const submitting = ref(false);
const pickedVoiceFiles = ref<File[]>([]);

const recorder = useVoiceRecorder();

type ProgressState = "idle" | "running" | "ok" | "error";
interface ProgressSnapshot {
  percent: number;
  label: string;
  state: ProgressState;
}
const textProgress = ref<ProgressSnapshot>({ percent: 0, label: "等待上传聊天记录", state: "idle" });
const voiceProgress = ref<ProgressSnapshot>({ percent: 0, label: "等待上传语音样本", state: "idle" });

const allPickedFiles = computed<File[]>(() => [
  ...pickedVoiceFiles.value,
  ...recorder.recordedFiles.value!,
]);

watch(
  () => props.current,
  (next) => {
    if (!next) return;
    targetName.value = next.name || "Target";
    cloneIdInput.value = next.cloneId;
    textProgress.value = { percent: 100, label: "文本向量数据库已生成", state: "ok" };
    voiceProgress.value = progressFromVoiceStatus(next.voice?.status);
  },
  { immediate: true }
);

function onChatFiles(event: Event): void {
  const files = (event.target as HTMLInputElement).files;
  if (!files || !files.length) return;
  Promise.all(
    Array.from(files).map(async (file) => `# 来自文件: ${file.name}\n${await readAsText(file)}`)
  )
    .then((parts) => {
      chatText.value = parts.join("\n\n");
    })
    .catch((error: Error) => emit("status", error.message, true));
}

function onVoiceFiles(event: Event): void {
  const files = (event.target as HTMLInputElement).files;
  pickedVoiceFiles.value = files ? Array.from(files) : [];
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

async function handleSubmit(): Promise<void> {
  if (!targetName.value.trim() || !chatText.value.trim()) {
    emit("status", "请补全名称和聊天文本。", true);
    return;
  }
  if (!consent.value) {
    emit("status", "请先勾选授权确认。", true);
    return;
  }

  submitting.value = true;
  textProgress.value = { percent: 10, label: "正在读取本地文件", state: "running" };
  emit("status", "正在训练画像并保存本地文件...");
  try {
    const voiceFiles = await filesToUploadPayloads(allPickedFiles.value, "无法读取声音文件");
    if (voiceFiles.length) {
      voiceProgress.value = { percent: 20, label: "正在保存语音样本", state: "running" };
    }
    textProgress.value = { percent: 65, label: "正在生成文本向量数据库", state: "running" };

    const payload = {
      targetName: targetName.value.trim(),
      chatText: chatText.value.trim(),
      voiceFiles,
    };
    const isUpdating = Boolean(props.current?.cloneId);
    const profile = isUpdating
      ? await clones.updateClone(props.current!.cloneId, payload)
      : await clones.createClone(payload);
    pickedVoiceFiles.value = [];
    recorder.clear();
    textProgress.value = { percent: 100, label: "文本向量数据库已生成", state: "ok" };
    voiceProgress.value = progressFromVoiceStatus(profile.voice?.status);
    cloneIdInput.value = profile.cloneId;
    emit("status", `${isUpdating ? "更新完成，克隆 ID：" : "训练完成，克隆 ID："}${profile.cloneId}`);
  } catch (error) {
    textProgress.value = { percent: 100, label: "文本向量数据库生成失败", state: "error" };
    emit("status", (error as Error).message, true);
  } finally {
    submitting.value = false;
  }
}

function loadById(): void {
  const trimmed = cloneIdInput.value.trim();
  if (!trimmed) {
    emit("status", "请输入已有克隆 ID。", true);
    return;
  }
  emit("loadById", trimmed);
}

function progressFromVoiceStatus(status?: string | null): ProgressSnapshot {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "ready") return { percent: 100, label: "语音模型已就绪", state: "ok" };
  if (normalized === "samples_ready") return { percent: 35, label: "样本已保存，等待训练", state: "idle" };
  if (normalized === "queued") return { percent: 55, label: "语音训练排队中", state: "running" };
  if (normalized === "running") return { percent: 78, label: "语音训练进行中", state: "running" };
  if (["error", "failed", "missing_samples", "pending_adapter", "pending_backend", "unavailable"].includes(normalized)) {
    return { percent: 100, label: "语音训练失败或后端未就绪", state: "error" };
  }
  return { percent: 0, label: "等待上传语音样本", state: "idle" };
}
</script>

<template>
  <section class="panel upload-panel" aria-labelledby="upload-title">
    <h2 id="upload-title">训练输入</h2>
    <form class="clone-form" @submit.prevent="handleSubmit">
      <label>
        <span>克隆对象名称</span>
        <input
          v-model="targetName"
          type="text"
          autocomplete="off"
          required
          data-testid="target-name"
        />
      </label>

      <div class="resume-section" aria-label="恢复已有克隆">
        <label>
          <span>已有克隆 ID</span>
          <input
            v-model="cloneIdInput"
            type="text"
            autocomplete="off"
            placeholder="clone id"
            data-testid="clone-id-input"
          />
        </label>
        <button
          class="secondary compact-button"
          type="button"
          data-testid="load-clone-button"
          @click="loadById"
        >
          加载克隆
        </button>
      </div>

      <div class="import-section">
        <div class="section-head">
          <h3>本地文件导入</h3>
          <span class="badge">全部本地</span>
        </div>
        <div class="local-file-grid">
          <label>
            <span>聊天文本文件（可多选）</span>
            <input
              type="file"
              accept=".txt,.json,.csv,.md"
              multiple
              @change="onChatFiles"
            />
          </label>
          <label>
            <span>语音文件（可多选）</span>
            <input
              type="file"
              accept="audio/*,.wav,.mp3,.m4a,.ogg"
              multiple
              data-testid="voice-file"
              @change="onVoiceFiles"
            />
          </label>
        </div>

        <div class="record-panel">
          <button
            class="secondary compact-button"
            type="button"
            data-testid="record-voice-button"
            @click="toggleRecording"
          >
            {{ recorder.isRecording.value ? "停止录制" : "录制语音样本" }}
          </button>
          <span class="recording-state">{{ recorder.message.value }}</span>
        </div>

        <div class="sample-panel" aria-live="polite">
          <div class="section-head compact">
            <h3>语音样本</h3>
            <span class="badge">{{ allPickedFiles.length ? `已选择 ${allPickedFiles.length}` : "等待上传" }}</span>
          </div>
          <ul class="sample-list">
            <li v-if="!allPickedFiles.length">尚未选择语音样本</li>
            <li v-for="file in allPickedFiles" :key="file.name">{{ file.name }}</li>
          </ul>
          <TrainingProgress
            label="语音训练进度"
            :caption="voiceProgress.label"
            :percent="voiceProgress.percent"
            :state="voiceProgress.state"
            aria-label="语音训练进度"
          />
        </div>

        <label>
          <span>聊天文本内容</span>
          <textarea
            v-model="chatText"
            rows="10"
            placeholder="Target: hahaha"
            data-testid="chat-text"
          ></textarea>
        </label>
      </div>

      <label class="consent">
        <input v-model="consent" type="checkbox" required />
        <span>
          我确认拥有上传声音和聊天记录的使用授权，并同意生成内容标记为 AI 合成。
        </span>
      </label>

      <button class="primary" type="submit" :disabled="submitting">开始训练</button>
      <TrainingProgress
        label="文本训练进度"
        :caption="textProgress.label"
        :percent="textProgress.percent"
        :state="textProgress.state"
        aria-label="文本训练进度"
      />
    </form>
  </section>
</template>
