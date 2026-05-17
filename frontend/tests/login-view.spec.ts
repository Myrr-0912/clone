import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory, type Router } from "vue-router";

import LoginView from "@/views/LoginView.vue";
import RegisterView from "@/views/RegisterView.vue";

function setupRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div>root</div>" } },
      { path: "/login", name: "login", component: LoginView },
      { path: "/register", name: "register", component: RegisterView },
      { path: "/app", name: "workspace", component: { template: "<div>app</div>" } },
      { path: "/admin", name: "admin", component: { template: "<div>admin</div>" } },
    ],
  });
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("LoginView", () => {
  it("submits username/password and navigates to /app", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse(200, { user: { id: "1", username: "alice", role: "user" } })
      );
    const router = setupRouter();
    await router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, { global: { plugins: [router] } });
    await wrapper.find("[data-testid=login-username]").setValue("alice");
    await wrapper.find("[data-testid=login-password]").setValue("pw");
    await wrapper.find("form").trigger("submit.prevent");
    await new Promise((resolve) => setTimeout(resolve, 0));

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ username: "alice", password: "pw" });
    expect(router.currentRoute.value.path).toBe("/app");
  });

  it("shows server error message on failed login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, { error: "Invalid username or password" })
    );
    const router = setupRouter();
    await router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, { global: { plugins: [router] } });
    await wrapper.find("[data-testid=login-username]").setValue("alice");
    await wrapper.find("[data-testid=login-password]").setValue("wrong");
    await wrapper.find("form").trigger("submit.prevent");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(wrapper.get("[data-testid=login-status]").text()).toContain(
      "Invalid username or password"
    );
    expect(router.currentRoute.value.path).toBe("/login");
  });

  it("routes admin user to /admin after register", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(201, { user: { id: "9", username: "root", role: "admin" } })
    );
    const router = setupRouter();
    await router.push("/register");
    await router.isReady();

    const wrapper = mount(RegisterView, { global: { plugins: [router] } });
    await wrapper.find("[data-testid=register-username]").setValue("root");
    await wrapper.find("[data-testid=register-password]").setValue("admin-pass");
    await wrapper.find("form").trigger("submit.prevent");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(router.currentRoute.value.path).toBe("/admin");
  });
});
