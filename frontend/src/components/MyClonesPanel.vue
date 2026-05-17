<script setup lang="ts">
import { computed } from "vue";

import type { CloneProfile } from "@/types";

const props = defineProps<{
  clones: CloneProfile[];
  loading: boolean;
  errorMessage: string | null;
  activeCloneId: string | null;
}>();

const emit = defineEmits<{
  refresh: [];
  use: [cloneId: string];
  rename: [cloneId: string];
  remove: [cloneId: string];
}>();

const items = computed(() => props.clones);

function summary(clone: CloneProfile): string {
  const stats = clone.sourceStats as Record<string, unknown>;
  const voice = clone.voice?.status ?? "未提供语音样本";
  const messages = Number(stats?.target_messages ?? 0);
  return `ID ${clone.cloneId} · ${messages} 条目标消息 · ${voice}`;
}
</script>

<template>
  <section class="panel my-clones-panel" aria-labelledby="my-clones-title">
    <div class="section-head">
      <h2 id="my-clones-title">我的克隆人</h2>
      <button class="secondary compact-button" type="button" @click="emit('refresh')">刷新</button>
    </div>
    <ul class="my-clones-list" aria-live="polite" data-testid="my-clones-list">
      <li v-if="loading" class="empty">正在加载我的克隆人...</li>
      <li v-else-if="errorMessage" class="empty error">{{ errorMessage }}</li>
      <li v-else-if="!items.length" class="empty">你还没有创建克隆人</li>
      <template v-else>
        <li
          v-for="clone in items"
          :key="clone.cloneId"
          class="my-clone-item"
          :class="{ active: clone.cloneId === activeCloneId }"
        >
          <div class="my-clone-summary">
            <strong>{{ clone.name || clone.cloneId }}</strong>
            <span>{{ summary(clone) }}</span>
          </div>
          <div class="my-clone-actions">
            <button
              class="secondary compact-button"
              type="button"
              @click="emit('use', clone.cloneId)"
            >
              使用
            </button>
            <button
              class="ghost compact-button"
              type="button"
              @click="emit('rename', clone.cloneId)"
            >
              改名
            </button>
            <button
              class="ghost compact-button"
              type="button"
              @click="emit('remove', clone.cloneId)"
            >
              删除
            </button>
          </div>
        </li>
      </template>
    </ul>
  </section>
</template>
