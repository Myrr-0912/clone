<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const showLoginNav = computed(() => !auth.user);
const isActive = (target: string): boolean => route.path.startsWith(target);

async function handleLogout(): Promise<void> {
  await auth.logout();
  await router.push("/login");
}
</script>

<template>
  <header class="topbar">
    <RouterLink class="brand" :to="auth.user ? '/app' : '/login'">
      <span class="eyebrow">Local MVP</span>
      <strong>Cyber Clone Lab</strong>
    </RouterLink>

    <nav class="top-nav" aria-label="主导航">
      <template v-if="auth.user">
        <RouterLink to="/app" :class="{ active: isActive('/app') }">工作台</RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin" :class="{ active: isActive('/admin') }">
          管理员
        </RouterLink>
      </template>
      <template v-else-if="showLoginNav">
        <RouterLink to="/login" :class="{ active: isActive('/login') }">登录</RouterLink>
        <RouterLink to="/register" :class="{ active: isActive('/register') }">注册</RouterLink>
      </template>
    </nav>

    <div class="account-chip" aria-live="polite">
      <span v-if="auth.user" class="user-label">
        {{ auth.user.username || auth.user.id }} ·
        {{ auth.isAdmin ? "管理员" : "普通用户" }}
      </span>
      <button
        v-if="auth.user"
        class="secondary compact-button"
        type="button"
        @click="handleLogout"
      >
        退出登录
      </button>
    </div>
  </header>

  <main class="view-root" aria-live="polite">
    <RouterView />
  </main>
</template>
