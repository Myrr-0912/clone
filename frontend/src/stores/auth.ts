import { defineStore } from "pinia";
import { computed, ref } from "vue";

import * as authApi from "@/api/auth";
import type { SessionUser } from "@/types";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<SessionUser | null>(null);
  const loaded = ref(false);

  const isAuthenticated = computed(() => user.value !== null);
  const isAdmin = computed(() => user.value?.role === "admin");

  async function refresh(): Promise<SessionUser | null> {
    try {
      const body = await authApi.fetchMe();
      user.value = body.user;
    } catch {
      user.value = null;
    } finally {
      loaded.value = true;
    }
    return user.value;
  }

  async function login(username: string, password: string): Promise<SessionUser> {
    const body = await authApi.login(username, password);
    user.value = body.user;
    loaded.value = true;
    return body.user;
  }

  async function register(username: string, password: string): Promise<SessionUser> {
    const body = await authApi.register(username, password);
    user.value = body.user;
    loaded.value = true;
    return body.user;
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } finally {
      user.value = null;
    }
  }

  return { user, loaded, isAuthenticated, isAdmin, refresh, login, register, logout };
});
