<script setup lang="ts">
defineProps<{
  label: string;
  caption: string;
  percent: number;
  state?: "idle" | "running" | "ok" | "error";
  ariaLabel?: string;
}>();
</script>

<template>
  <div class="progress-panel" :data-state="state ?? 'idle'">
    <div class="progress-meta">
      <span>{{ label }}</span>
      <strong>{{ caption }}</strong>
    </div>
    <div
      class="progress-track"
      role="progressbar"
      :aria-label="ariaLabel ?? label"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="percent"
    >
      <span
        class="progress-bar"
        :class="{ ok: state === 'ok', error: state === 'error' }"
        :style="{ width: `${Math.max(0, Math.min(100, percent))}%` }"
      ></span>
    </div>
  </div>
</template>
