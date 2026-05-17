<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useClonesStore } from "@/stores/clones";
import CloneCreateForm from "@/components/CloneCreateForm.vue";
import MyClonesPanel from "@/components/MyClonesPanel.vue";
import ProfilePanel from "@/components/ProfilePanel.vue";
import ChatPanel from "@/components/ChatPanel.vue";
import VoiceActionsPanel from "@/components/VoiceActionsPanel.vue";

const route = useRoute();
const router = useRouter();
const clones = useClonesStore();

const status = ref("");
const statusError = ref(false);
const profilePanel = ref<InstanceType<typeof ProfilePanel> | null>(null);

const cloneIdFromRoute = computed(() => {
  const raw = route.params.cloneId;
  return typeof raw === "string" && raw ? raw : null;
});
const currentClone = computed(() => clones.current);
const inferenceSteps = computed(() => profilePanel.value?.inferenceSteps ?? 4);
const cfgValue = computed(() => profilePanel.value?.cfgValue ?? 2.0);

onMounted(async () => {
  await clones.refreshList();
  if (cloneIdFromRoute.value) {
    await loadClone(cloneIdFromRoute.value);
  }
});

watch(cloneIdFromRoute, async (next) => {
  if (next && next !== clones.current?.cloneId) {
    await loadClone(next);
  } else if (!next) {
    clones.reset();
  }
});

async function loadClone(cloneId: string): Promise<void> {
  setStatus("正在加载已有克隆...");
  try {
    const profile = await clones.loadById(cloneId);
    setStatus(`已加载克隆 ID：${profile.cloneId}`);
  } catch (error) {
    setStatus((error as Error).message || "加载克隆失败", true);
  }
}

async function handleUse(cloneId: string): Promise<void> {
  await router.push(`/app/clones/${encodeURIComponent(cloneId)}`);
}

async function handleRename(cloneId: string): Promise<void> {
  const existing = clones.myClones.find((item) => item.cloneId === cloneId);
  const nextName = window.prompt("新的克隆人名称", existing?.name || "");
  if (nextName === null) return;
  const trimmed = nextName.trim();
  if (!trimmed) return;
  try {
    await clones.renameClone(cloneId, trimmed);
    setStatus("克隆人改名成功");
  } catch (error) {
    setStatus((error as Error).message || "克隆人改名失败", true);
  }
}

async function handleRemove(cloneId: string): Promise<void> {
  if (!window.confirm("确定删除这个克隆人吗？")) return;
  try {
    await clones.deleteClone(cloneId);
    if (cloneIdFromRoute.value === cloneId) {
      await router.replace("/app");
    }
    setStatus("克隆人已删除");
  } catch (error) {
    setStatus((error as Error).message || "克隆人删除失败", true);
  }
}

function setStatus(message: string, isError = false): void {
  status.value = message;
  statusError.value = isError;
}

function handleStatus(message: string, isError = false): void {
  setStatus(message, isError);
}

async function handleLoadById(cloneId: string): Promise<void> {
  await router.push(`/app/clones/${encodeURIComponent(cloneId)}`);
}
</script>

<template>
  <section class="layout" aria-label="克隆人工作台">
    <CloneCreateForm
      :current="currentClone"
      @status="handleStatus"
      @load-by-id="handleLoadById"
    />

    <MyClonesPanel
      :clones="clones.myClones"
      :loading="clones.loadingList"
      :error-message="clones.listError"
      :active-clone-id="currentClone?.cloneId ?? null"
      @refresh="clones.refreshList()"
      @use="handleUse"
      @rename="handleRename"
      @remove="handleRemove"
    />

    <ProfilePanel ref="profilePanel" :clone="currentClone" />

    <VoiceActionsPanel
      :clone-id="currentClone?.cloneId ?? null"
      @status="handleStatus"
    />

    <ChatPanel
      :clone-id="currentClone?.cloneId ?? null"
      :clone="currentClone"
      :inference-steps="inferenceSteps"
      :cfg-value="cfgValue"
      @clone-updated="(clone) => (clones.current = clone)"
      @status="handleStatus"
    />

    <p
      class="status"
      :class="{ error: statusError }"
      role="status"
      style="grid-column: 1 / -1;"
    >
      {{ status }}
    </p>
  </section>
</template>
