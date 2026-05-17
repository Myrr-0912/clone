<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

function goWorkspace(): void {
  router.push("/app");
}
</script>

<template>
  <section class="auth-card" style="margin-top: 24px;">
    <p class="eyebrow">404</p>
    <h1>页面不存在</h1>
    <p class="lede">这个前端路由还没有定义。</p>
    <button class="secondary compact-button" type="button" @click="goWorkspace">
      回到工作台
    </button>
  </section>
</template>
