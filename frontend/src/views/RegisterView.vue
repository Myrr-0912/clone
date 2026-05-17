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
    const user = await auth.register(username.value.trim(), password.value);
    await router.push(user.role === "admin" ? "/admin" : "/app");
  } catch (error) {
    status.value = (error as Error).message || "注册失败";
    isError.value = true;
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="auth-layout" aria-labelledby="register-title">
    <div class="auth-card">
      <p class="eyebrow">New User</p>
      <h1 id="register-title">注册普通用户</h1>
      <p class="lede">
        注册后会自动登录，并跳转到你的克隆人工作台。每个用户上传的聊天记录、向量库和
        语音模型都会隔离保存。
      </p>
    </div>
    <form class="auth-card" @submit.prevent="handleSubmit">
      <h2>注册</h2>
      <label>
        <span>用户名</span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          required
          data-testid="register-username"
        />
      </label>
      <label>
        <span>密码</span>
        <input
          v-model="password"
          type="password"
          autocomplete="new-password"
          required
          data-testid="register-password"
        />
      </label>
      <button class="primary" type="submit" :disabled="submitting">
        {{ submitting ? "注册中..." : "创建普通用户" }}
      </button>
      <p class="auth-switch">
        已有账号？<RouterLink to="/login">去登录</RouterLink>
      </p>
      <p class="status" :class="{ error: isError }" role="status" data-testid="register-status">
        {{ status }}
      </p>
    </form>
  </section>
</template>
