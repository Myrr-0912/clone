<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import { sendChatMessage, synthesizeSpeech } from "@/api/chat";
import type { CloneProfile } from "@/types";

const props = defineProps<{
  cloneId: string | null;
  clone: CloneProfile | null;
  inferenceSteps: number;
  cfgValue: number;
}>();

const emit = defineEmits<{
  cloneUpdated: [clone: CloneProfile];
  status: [message: string, isError?: boolean];
}>();

type Role = "user" | "clone" | "system";
interface Message {
  id: number;
  role: Role;
  text: string;
}

const messages = ref<Message[]>([]);
const draft = ref("");
const mode = ref<"text" | "voice">("text");
const emotion = ref("auto");
const playbackUrl = ref<string | null>(null);
const sending = ref(false);
const messagesEl = ref<HTMLElement | null>(null);
let nextId = 0;

const canSend = computed(() => Boolean(props.cloneId) && draft.value.trim().length > 0 && !sending.value);

watch(
  () => props.cloneId,
  () => {
    messages.value = [];
    playbackUrl.value = null;
  }
);

watch(mode, (value) => {
  if (value === "text") {
    playbackUrl.value = null;
  }
});

async function handleSubmit(): Promise<void> {
  if (!props.cloneId) return;
  const text = draft.value.trim();
  if (!text) return;
  draft.value = "";
  push("user", text);
  sending.value = true;
  try {
    const reply = await sendChatMessage(props.cloneId, text);
    if (reply.clone) {
      emit("cloneUpdated", reply.clone);
    }
    push("clone", reply.reply.text);
    if (mode.value === "voice") {
      await speak(reply.reply.text, reply.reply.emotion);
    }
  } catch (error) {
    push("clone", (error as Error).message || "回复失败");
  } finally {
    sending.value = false;
  }
}

async function speak(replyText: string, replyEmotion: string): Promise<void> {
  if (!props.cloneId) return;
  const selected = emotion.value === "auto" ? replyEmotion || "natural" : emotion.value;
  try {
    const body = await synthesizeSpeech(props.cloneId, {
      text: replyText,
      emotion: selected,
      inferenceSteps: props.inferenceSteps,
      cfgValue: props.cfgValue,
    });
    const speech = body.speech;
    if (!speech.audioDataUrl) {
      push("system", speech.message || "语音生成失败");
      emit("status", speech.message || "语音生成失败", ["error", "failed"].includes(speech.status));
      return;
    }
    playbackUrl.value = speech.audioDataUrl;
    emit("status", `语音已生成: ${speech.backend}`);
  } catch (error) {
    const message = (error as Error).message;
    push("system", message);
    emit("status", message, true);
  }
}

function push(role: Role, text: string): void {
  messages.value.push({ id: nextId++, role, text });
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
    }
  });
}
</script>

<template>
  <section class="panel chat-panel" aria-labelledby="chat-title">
    <h2 id="chat-title">聊天测试</h2>
    <div class="chat-toolbar">
      <fieldset class="mode-toggle" aria-label="聊天模式">
        <label>
          <input v-model="mode" type="radio" value="text" data-testid="chat-mode-text" />
          <span>文本</span>
        </label>
        <label>
          <input v-model="mode" type="radio" value="voice" data-testid="chat-mode-voice" />
          <span>语音</span>
        </label>
      </fieldset>
      <label class="emotion-control">
        <span>情绪</span>
        <select v-model="emotion" data-testid="voice-emotion">
          <option value="auto">自动</option>
          <option value="natural">自然</option>
          <option value="warm">温柔</option>
          <option value="happy">开心</option>
          <option value="calm">平静</option>
          <option value="sad">低落</option>
          <option value="excited">兴奋</option>
        </select>
      </label>
    </div>
    <div ref="messagesEl" class="messages" aria-live="polite" data-testid="messages">
      <p v-if="!messages.length" class="empty">训练完成后可以在这里试聊。</p>
      <p
        v-for="msg in messages"
        :key="msg.id"
        class="bubble"
        :class="msg.role"
      >
        {{ msg.text }}
      </p>
    </div>
    <audio
      v-if="playbackUrl"
      :src="playbackUrl"
      class="audio-playback"
      controls
      autoplay
    ></audio>
    <form class="chat-form" @submit.prevent="handleSubmit">
      <input
        v-model="draft"
        type="text"
        placeholder="发一句试试"
        autocomplete="off"
        :disabled="!cloneId"
        data-testid="message-input"
      />
      <button type="submit" :disabled="!canSend">发送</button>
    </form>
  </section>
</template>
