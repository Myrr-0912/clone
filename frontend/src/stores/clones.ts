import { defineStore } from "pinia";
import { ref } from "vue";

import * as clonesApi from "@/api/clones";
import * as voiceApi from "@/api/voice";
import type { CloneProfile, UploadedFile, VoiceStatus } from "@/types";

export const useClonesStore = defineStore("clones", () => {
  const myClones = ref<CloneProfile[]>([]);
  const current = ref<CloneProfile | null>(null);
  const loadingList = ref(false);
  const listError = ref<string | null>(null);

  async function refreshList(): Promise<void> {
    loadingList.value = true;
    listError.value = null;
    try {
      const body = await clonesApi.listClones();
      myClones.value = body.clones ?? [];
    } catch (error) {
      listError.value = (error as Error).message;
      myClones.value = [];
    } finally {
      loadingList.value = false;
    }
  }

  async function loadById(cloneId: string): Promise<CloneProfile> {
    const body = await clonesApi.getClone(cloneId);
    current.value = body.clone;
    return body.clone;
  }

  async function createClone(payload: clonesApi.CloneCreatePayload): Promise<CloneProfile> {
    const body = await clonesApi.createClone(payload);
    current.value = body.clone;
    await refreshList();
    return body.clone;
  }

  async function updateClone(
    cloneId: string,
    payload: Partial<clonesApi.CloneCreatePayload>
  ): Promise<CloneProfile> {
    const body = await clonesApi.updateClone(cloneId, payload);
    current.value = body.clone;
    await refreshList();
    return body.clone;
  }

  async function renameClone(cloneId: string, targetName: string): Promise<CloneProfile> {
    const body = await clonesApi.renameClone(cloneId, targetName);
    if (current.value?.cloneId === cloneId) {
      current.value = body.clone;
    }
    await refreshList();
    return body.clone;
  }

  async function deleteClone(cloneId: string): Promise<void> {
    await clonesApi.deleteClone(cloneId);
    if (current.value?.cloneId === cloneId) {
      current.value = null;
    }
    await refreshList();
  }

  async function uploadVoiceSamples(
    cloneId: string,
    voiceFiles: UploadedFile[]
  ): Promise<VoiceStatus | null> {
    const body = await voiceApi.uploadVoiceSamples(cloneId, voiceFiles);
    if (current.value?.cloneId === cloneId) {
      current.value = body.clone;
    }
    return body.voice;
  }

  async function trainVoice(cloneId: string): Promise<VoiceStatus> {
    const body = await voiceApi.trainVoiceModel(cloneId);
    if (current.value?.cloneId === cloneId) {
      current.value = body.clone;
    }
    return body.voice;
  }

  async function refreshVoiceStatus(cloneId: string): Promise<VoiceStatus> {
    const body = await voiceApi.getVoiceStatus(cloneId);
    if (current.value?.cloneId === cloneId) {
      current.value = body.clone;
    }
    return body.voice;
  }

  function reset(): void {
    current.value = null;
  }

  return {
    myClones,
    current,
    loadingList,
    listError,
    refreshList,
    loadById,
    createClone,
    updateClone,
    renameClone,
    deleteClone,
    uploadVoiceSamples,
    trainVoice,
    refreshVoiceStatus,
    reset,
  };
});
