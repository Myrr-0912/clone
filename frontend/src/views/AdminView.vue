<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { fetchAdminSummary } from "@/api/admin";
import type { AdminSummary } from "@/types";

const summary = ref<AdminSummary | null>(null);
const refreshState = ref("正在刷新");
const refreshError = ref(false);

const resources = computed(() => summary.value?.resources ?? []);
const vectorCount = computed(() => summary.value?.vectorDbCount ?? resources.value.length);
const totalVectorSize = computed(() =>
  formatBytes(summary.value?.totalVectorDbSizeBytes ?? sumBy(resources.value, "vectorDbSizeBytes"))
);
const totalVoiceSize = computed(() =>
  formatBytes(summary.value?.totalVoiceModelSizeBytes ?? sumBy(resources.value, "voiceModelSizeBytes"))
);

onMounted(load);

async function load(): Promise<void> {
  refreshState.value = "正在刷新";
  refreshError.value = false;
  try {
    summary.value = await fetchAdminSummary();
    refreshState.value = "已刷新";
  } catch (error) {
    refreshState.value = (error as Error).message || "管理员数据加载失败";
    refreshError.value = true;
  }
}

function sumBy<T extends Record<string, unknown>>(items: T[], key: keyof T): number {
  return items.reduce((total, item) => total + Number(item[key] ?? 0), 0);
}

function formatBytes(value: number): string {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let amount = bytes / 1024;
  let unitIndex = 0;
  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }
  return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}
</script>

<template>
  <section class="admin-layout" aria-labelledby="admin-title">
    <section class="panel admin-summary">
      <div>
        <p class="eyebrow">Admin</p>
        <h1 id="admin-title">向量数据库与语音模型概览</h1>
        <p class="lede">这里只展示资源元数据和大小，不读取聊天正文或音频内容。</p>
      </div>
      <dl class="admin-metrics">
        <div class="metric">
          <dt>向量数据库</dt>
          <dd data-testid="admin-vector-count">{{ vectorCount }}</dd>
        </div>
        <div class="metric">
          <dt>向量库大小</dt>
          <dd data-testid="admin-total-vector-size">{{ totalVectorSize }}</dd>
        </div>
        <div class="metric">
          <dt>语音模型大小</dt>
          <dd data-testid="admin-total-voice-size">{{ totalVoiceSize }}</dd>
        </div>
      </dl>
    </section>

    <section class="panel" aria-labelledby="admin-table-title">
      <div class="section-head">
        <h2 id="admin-table-title">克隆人资源</h2>
        <span
          class="badge"
          :class="{ error: refreshError }"
          data-testid="admin-refresh-state"
        >
          {{ refreshState }}
        </span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>克隆人</th>
              <th>向量库</th>
              <th>分块</th>
              <th>向量大小</th>
              <th>语音模型</th>
              <th>语音大小</th>
            </tr>
          </thead>
          <tbody data-testid="admin-resource-table">
            <tr v-if="!resources.length">
              <td colspan="7">暂无向量数据库</td>
            </tr>
            <tr v-for="item in resources" :key="`${item.userId}-${item.cloneId}`">
              <td>{{ item.username || item.userId || "-" }}</td>
              <td>{{ item.cloneName || item.cloneId || "-" }}</td>
              <td>{{ item.vectorDbName || "-" }}</td>
              <td>{{ item.chunkCount ?? 0 }}</td>
              <td>{{ formatBytes(item.vectorDbSizeBytes || 0) }}</td>
              <td>{{ item.voiceModelStatus || "-" }}</td>
              <td>{{ formatBytes(item.voiceModelSizeBytes || 0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
