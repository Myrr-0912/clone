<script setup lang="ts">
import { computed, ref } from "vue";

import { synthesizeSpeech } from "@/api/chat";
import type { CloneProfile, SpeechResult } from "@/types";

const props = defineProps<{ clone: CloneProfile | null }>();

const inferenceSteps = ref(4);
const cfgValue = ref(2.0);

const previewText = ref("你好，我想听一下现在的声音效果。");
const previewEmotion = ref("natural");
const previewStatus = ref("");
const previewError = ref(false);
const previewAudioUrl = ref<string | null>(null);
const submitting = ref(false);

const cloneId = computed(() => props.clone?.cloneId ?? null);
const catchphrases = computed(() =>
  props.clone?.style?.catchphrases?.join("、") || "等待训练"
);
const topics = computed(() => {
  const memory = props.clone?.memory;
  if (!memory) return "等待训练";
  const list = memory.keyTopics?.length ? memory.keyTopics : memory.key_topics;
  return (list?.join("、") || "等待训练") as string;
});
const voiceStatus = computed(() => props.clone?.voice?.message || "未提供语音样本");
const sourceStats = computed(() => {
  const stats = (props.clone?.sourceStats as Record<string, unknown>) ?? {};
  const messages = Number(stats?.target_messages ?? 0);
  const voiceFiles = Number(stats?.voice_files ?? 0);
  return `${messages} 条目标消息，${voiceFiles} 个语音`;
});

defineExpose({ inferenceSteps, cfgValue });

async function preview(): Promise<void> {
  previewStatus.value = "";
  previewError.value = false;
  previewAudioUrl.value = null;
  if (!cloneId.value) {
    previewStatus.value = "请先创建或加载一个克隆人";
    previewError.value = true;
    return;
  }
  if (!previewText.value.trim()) {
    previewStatus.value = "请输入要试听的文本";
    previewError.value = true;
    return;
  }
  submitting.value = true;
  previewStatus.value = "正在生成试听语音...";
  try {
    const body = await synthesizeSpeech(cloneId.value, {
      text: previewText.value.trim(),
      emotion: previewEmotion.value || "natural",
      inferenceSteps: inferenceSteps.value,
      cfgValue: cfgValue.value,
    });
    const speech: SpeechResult = body.speech;
    if (!speech.audioDataUrl) {
      previewStatus.value = speech.message || "试听语音生成失败";
      previewError.value = ["error", "failed"].includes(speech.status);
      return;
    }
    previewAudioUrl.value = speech.audioDataUrl;
    previewStatus.value = `试听语音已生成：${speech.backend || "local"}`;
  } catch (error) {
    previewStatus.value = (error as Error).message || "试听语音生成失败";
    previewError.value = true;
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="panel profile-panel" aria-labelledby="profile-title">
    <h2 id="profile-title">克隆画像</h2>
    <dl class="profile-grid">
      <div>
        <dt>口头禅</dt>
        <dd data-testid="catchphrases">{{ catchphrases }}</dd>
      </div>
      <div>
        <dt>关键话题</dt>
        <dd data-testid="topics">{{ topics }}</dd>
      </div>
      <div>
        <dt>音色状态</dt>
        <dd data-testid="voice-status-message">{{ voiceStatus }}</dd>
      </div>
      <div>
        <dt>样本量</dt>
        <dd data-testid="source-stats">{{ sourceStats }}</dd>
      </div>
    </dl>

    <div class="voice-parameter-panel" aria-labelledby="voice-parameter-title">
      <div class="section-head compact">
        <h3 id="voice-parameter-title">语音生成参数</h3>
        <span class="badge">VoxCPM</span>
      </div>
      <div class="voice-parameter-grid">
        <label class="range-control">
          <span>推理步骤</span>
          <output>{{ inferenceSteps }}</output>
          <input
            v-model.number="inferenceSteps"
            type="range"
            min="1"
            max="30"
            step="1"
            data-testid="voice-inference-steps"
          />
        </label>
        <label class="range-control">
          <span>CFG 引导强度</span>
          <output>{{ cfgValue.toFixed(1) }}</output>
          <input
            v-model.number="cfgValue"
            type="range"
            min="0.5"
            max="5"
            step="0.1"
            data-testid="voice-cfg-value"
          />
        </label>
      </div>
    </div>

    <div class="voice-preview-panel" aria-labelledby="voice-preview-title">
      <div class="section-head compact">
        <h3 id="voice-preview-title">语音试听</h3>
        <span class="badge">TTS</span>
      </div>
      <label>
        <span>试听文本</span>
        <textarea v-model="previewText" rows="3" placeholder="输入一段想试听的话"></textarea>
      </label>
      <div class="voice-preview-grid">
        <label>
          <span>情绪</span>
          <select v-model="previewEmotion">
            <option value="natural">自然</option>
            <option value="warm">温柔</option>
            <option value="happy">开心</option>
            <option value="calm">平静</option>
            <option value="sad">低落</option>
            <option value="excited">兴奋</option>
          </select>
        </label>
        <button
          class="secondary compact-button"
          type="button"
          :disabled="!cloneId || submitting"
          data-testid="voice-preview-button"
          @click="preview"
        >
          生成试听
        </button>
      </div>
      <audio
        v-if="previewAudioUrl"
        :src="previewAudioUrl"
        class="audio-playback"
        controls
      ></audio>
      <p class="status" :class="{ error: previewError }" role="status">
        {{ previewStatus }}
      </p>
    </div>
  </section>
</template>
