import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const routes = [
  {
    path: "/",
    redirect: (): string => {
      const auth = useAuthStore();
      if (!auth.user) return "/login";
      return auth.user.role === "admin" ? "/admin" : "/app";
    },
  },
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/LoginView.vue"),
    meta: { public: true },
  },
  {
    path: "/register",
    name: "register",
    component: () => import("@/views/RegisterView.vue"),
    meta: { public: true },
  },
  {
    path: "/app",
    name: "workspace",
    component: () => import("@/views/WorkspaceView.vue"),
  },
  {
    path: "/app/clones/:cloneId",
    name: "workspace-clone",
    component: () => import("@/views/WorkspaceView.vue"),
    props: true,
  },
  {
    path: "/admin",
    name: "admin",
    component: () => import("@/views/AdminView.vue"),
    meta: { admin: true },
  },
  {
    path: "/admin/vector-dbs",
    redirect: "/admin",
  },
  {
    path: "/:pathMatch(.*)*",
    name: "not-found",
    component: () => import("@/views/NotFoundView.vue"),
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.loaded) {
    await auth.refresh();
  }

  if (to.meta.public) {
    if (auth.user) {
      return auth.isAdmin ? "/admin" : "/app";
    }
    return true;
  }

  if (!auth.user) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }

  if (to.meta.admin && !auth.isAdmin) {
    return "/app";
  }

  return true;
});
