<script setup lang="ts">
import { ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const status = ref("");
const isError = ref(false);
const submitting = ref(false);

async function handleSubmit(): Promise<void> {
  submitting.value = true;
  status.value = "";
  isError.value = false;
  try {
    const user = await auth.login(username.value.trim(), password.value);
    await router.push(user.role === "admin" ? "/admin" : "/app");
  } catch (error) {
    status.value = (error as Error).message || "登录失败";
    isError.value = true;
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="auth-layout" aria-labelledby="login-title">
    <div class="auth-card">
      <p class="eyebrow">Private Clone Workspace</p>
      <h1 id="login-title">登录 Cyber Clone Lab</h1>
      <p class="lede">
        登录后再进入克隆人工作台。普通用户只能看到自己的克隆人、文本向量库和语音模型；
        管理员进入资源统计后台。
      </p>
    </div>
    <form class="auth-card" @submit.prevent="handleSubmit">
      <h2>登录</h2>
      <label>
        <span>用户名</span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          required
          data-testid="login-username"
        />
      </label>
      <label>
        <span>密码</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          data-testid="login-password"
        />
      </label>
      <button class="primary" type="submit" :disabled="submitting">
        {{ submitting ? "登录中..." : "登录" }}
      </button>
      <p class="auth-switch">
        还没有账号？<RouterLink to="/register">去注册</RouterLink>
      </p>
      <p class="status" :class="{ error: isError }" role="status" data-testid="login-status">
        {{ status }}
      </p>
    </form>
  </section>
</template>
