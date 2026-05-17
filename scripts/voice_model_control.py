from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from typing import Any, Callable
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = Path(
    "VoxCPM-local/models/models--openbmb--VoxCPM2/snapshots/"
    "bffb3df5a29440629464e5e839f4d214c8714c3d"
)


@dataclass(slots=True)
class VoiceModelServiceConfig:
    project_root: Path
    python_path: str
    script_path: Path
    host: str
    port: int
    device: str
    model_path: Path
    state_path: Path
    log_path: Path
    zipenhancer_model_path: Path | None = None
    enable_denoiser: bool = False
    optimize: bool = False
    health_timeout_seconds: float = 1.5
    startup_timeout_seconds: float = 12.0

    @classmethod
    def from_env(
        cls,
        project_root: Path = PROJECT_ROOT,
        env: dict[str, str] | None = None,
        env_path: Path | None = None,
    ) -> "VoiceModelServiceConfig":
        root = project_root.resolve()
        source: dict[str, str] = {}
        _load_env_file(env_path or root / ".env", source)
        source.update(os.environ if env is None else env)

        python_path = source.get("VOXCPM_BRIDGE_PYTHON") or str(_default_bridge_python(root))
        script_path = _resolve_path(
            source.get("VOXCPM_BRIDGE_SCRIPT"),
            root,
            root / "scripts" / "run_voxcpm_bridge.py",
        )
        model_path = _resolve_path(source.get("VOXCPM_MODEL_PATH"), root, root / DEFAULT_MODEL_PATH)
        zipenhancer_path = _optional_path(source.get("VOXCPM_ZIPENHANCER_MODEL_PATH"), root)

        return cls(
            project_root=root,
            python_path=python_path,
            script_path=script_path,
            host=source.get("VOXCPM_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_int_value(source.get("VOXCPM_BRIDGE_PORT"), 8810),
            device=source.get("VOXCPM_BRIDGE_DEVICE", "auto").strip() or "auto",
            model_path=model_path,
            state_path=_resolve_path(
                source.get("VOXCPM_BRIDGE_STATE_PATH"),
                root,
                root / "data" / "voice-model-control" / "voxcpm-bridge.json",
            ),
            log_path=_resolve_path(
                source.get("VOXCPM_BRIDGE_LOG_PATH"),
                root,
                root / "logs" / "voxcpm-bridge.log",
            ),
            zipenhancer_model_path=zipenhancer_path,
            enable_denoiser=_bool_value(source.get("VOXCPM_BRIDGE_ENABLE_DENOISER"), False),
            optimize=_bool_value(source.get("VOXCPM_BRIDGE_OPTIMIZE"), False),
            health_timeout_seconds=_float_value(source.get("VOXCPM_BRIDGE_HEALTH_TIMEOUT_SECONDS"), 1.5),
            startup_timeout_seconds=_float_value(source.get("VOXCPM_BRIDGE_STARTUP_TIMEOUT_SECONDS"), 12.0),
        )

    def command(self) -> list[str]:
        command = [
            self.python_path,
            str(self.script_path),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--device",
            self.device,
            "--model-path",
            str(self.model_path),
        ]
        if self.zipenhancer_model_path:
            command.extend(["--zipenhancer-model-path", str(self.zipenhancer_model_path)])
        if self.enable_denoiser:
            command.append("--enable-denoiser")
        if self.optimize:
            command.append("--optimize")
        return command

    @property
    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}/health"


class VoiceModelServiceController:
    def __init__(
        self,
        config: VoiceModelServiceConfig,
        popen: Callable[..., Any] = subprocess.Popen,
        health_check: Callable[[VoiceModelServiceConfig], bool] | None = None,
        process_exists: Callable[[int], bool] | None = None,
        stop_process: Callable[[int], None] | None = None,
    ) -> None:
        self.config = config
        self._popen = popen
        self._health_check = health_check or bridge_health_check
        self._process_exists = process_exists if process_exists is not None else globals()["process_exists"]
        self._stop_process = stop_process if stop_process is not None else stop_process_tree

    def status(self) -> dict[str, Any]:
        state = self._read_state()
        pid = _int_or_none(state.get("pid"))
        pid_running = bool(pid and self._process_exists(pid))
        healthy = self._health_check(self.config)
        launched_at = str(state.get("launchedAt") or "")
        age_seconds = _seconds_since(launched_at)

        if healthy and pid_running:
            service_state = "running"
            message = "VoxCPM bridge is running and healthy."
            running = True
        elif healthy:
            service_state = "external"
            message = "A bridge is healthy on this port, but it was not started by this control page."
            running = True
        elif pid_running and (age_seconds is None or age_seconds <= self.config.startup_timeout_seconds):
            service_state = "starting"
            message = "Bridge process is starting; health check is not ready yet."
            running = False
        elif pid_running:
            service_state = "unhealthy"
            message = "Bridge process exists, but health check is failing."
            running = False
        else:
            service_state = "stopped"
            message = "VoxCPM bridge is stopped."
            running = False

        return {
            "state": service_state,
            "running": running,
            "healthy": healthy,
            "pid": pid if pid_running else None,
            "host": self.config.host,
            "port": self.config.port,
            "healthUrl": self.config.health_url,
            "command": self.config.command(),
            "logPath": str(self.config.log_path),
            "statePath": str(self.config.state_path),
            "launchedAt": launched_at,
            "message": message,
        }

    def start(self) -> dict[str, Any]:
        current = self.status()
        if current["running"] or current["state"] in {"starting", "unhealthy"}:
            return current

        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)

        command = self.config.command()
        flags = 0
        if platform.system().lower() == "windows":
            flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

        popen_kwargs: dict[str, Any] = {
            "cwd": str(self.config.project_root),
            "stdin": subprocess.DEVNULL,
            "stdout": None,
            "stderr": subprocess.STDOUT,
        }
        if platform.system().lower() == "windows":
            popen_kwargs["creationflags"] = flags
        else:
            popen_kwargs["start_new_session"] = True

        log_file = self.config.log_path.open("ab")
        try:
            popen_kwargs["stdout"] = log_file
            process = self._popen(command, **popen_kwargs)
        finally:
            log_file.close()

        self._write_state(
            {
                "pid": int(process.pid),
                "command": command,
                "launchedAt": _utc_now(),
                "logPath": str(self.config.log_path),
            }
        )
        return self.status()

    def stop(self) -> dict[str, Any]:
        state = self._read_state()
        pid = _int_or_none(state.get("pid"))
        if pid and self._process_exists(pid):
            self._stop_process(pid)
        self._clear_state()
        result = self.status()
        if result["state"] == "stopped":
            result["message"] = "VoxCPM bridge has been stopped."
        return result

    def recent_logs(self, lines: int = 80) -> list[str]:
        if not self.config.log_path.exists():
            return []
        text = self.config.log_path.read_text(encoding="utf-8", errors="replace")
        return text.splitlines()[-max(1, lines) :]

    def _read_state(self) -> dict[str, Any]:
        if not self.config.state_path.exists():
            return {}
        try:
            data = json.loads(self.config.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_state(self, state: dict[str, Any]) -> None:
        self.config.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _clear_state(self) -> None:
        try:
            self.config.state_path.unlink()
        except FileNotFoundError:
            return


class VoiceModelControlHandler(BaseHTTPRequestHandler):
    controller: VoiceModelServiceController
    server_version = "VoiceModelControl/0.1"

    def do_GET(self) -> None:  # noqa: N802 - http.server naming convention.
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_html(CONTROL_PAGE_HTML)
            return
        if parsed.path == "/api/status":
            self._send_json(self.controller.status())
            return
        if parsed.path == "/api/logs":
            query = parse_qs(parsed.query)
            lines = _int_value((query.get("lines") or ["80"])[0], 80)
            self._send_json({"lines": self.controller.recent_logs(lines)})
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - http.server naming convention.
        parsed = urlparse(self.path)
        if parsed.path == "/api/start":
            self._send_json(self.controller.start())
            return
        if parsed.path == "/api/stop":
            self._send_json(self.controller.stop())
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_control_handler(controller: VoiceModelServiceController) -> type[VoiceModelControlHandler]:
    class BoundVoiceModelControlHandler(VoiceModelControlHandler):
        pass

    BoundVoiceModelControlHandler.controller = controller
    return BoundVoiceModelControlHandler


def bridge_health_check(config: VoiceModelServiceConfig) -> bool:
    opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
    try:
        with opener.open(config.health_url, timeout=config.health_timeout_seconds) as response:
            if response.status != HTTPStatus.OK:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError, urlerror.URLError):
        return False
    return bool(isinstance(payload, dict) and payload.get("ok") is True)


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if platform.system().lower() == "windows":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_process_tree(pid: int) -> None:
    if platform.system().lower() == "windows":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 8
    while time.time() < deadline:
        if not process_exists(pid):
            return
        time.sleep(0.2)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        os.kill(pid, signal.SIGKILL)


def run(
    host: str = "127.0.0.1",
    port: int = 8820,
    project_root: Path = PROJECT_ROOT,
) -> None:
    config = VoiceModelServiceConfig.from_env(project_root)
    controller = VoiceModelServiceController(config)
    server = ThreadingHTTPServer((host, port), create_control_handler(controller))
    print(f"Voice model control page running at http://{host}:{port}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a standalone VoxCPM bridge control page.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8820)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()
    run(host=args.host, port=args.port, project_root=Path(args.project_root))


def _default_bridge_python(project_root: Path) -> Path:
    if platform.system().lower() == "windows":
        candidate = project_root / "VoxCPM-local" / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = project_root / "VoxCPM-local" / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def _load_env_file(path: Path, target: dict[str, str]) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            target[key] = value


def _resolve_path(value: str | None, root: Path, default: Path) -> Path:
    if not value or not value.strip():
        return default
    path = Path(value.strip())
    return path if path.is_absolute() else root / path


def _optional_path(value: str | None, root: Path) -> Path | None:
    if not value or not value.strip():
        return None
    path = Path(value.strip())
    return path if path.is_absolute() else root / path


def _bool_value(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_value(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: str | None, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seconds_since(value: str) -> float | None:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - timestamp).total_seconds())


def _windows_process_exists(pid: int) -> bool:
    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


CONTROL_PAGE_HTML = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>VoxCPM 控制台</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #eef2f6;
        --panel: #ffffff;
        --text: #18202a;
        --muted: #637083;
        --line: #d8e0ea;
        --blue: #2563eb;
        --green: #17803d;
        --red: #c0392b;
        --amber: #a05a00;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: Inter, "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
        background: var(--bg);
        color: var(--text);
      }
      header {
        padding: 28px clamp(18px, 5vw, 56px) 14px;
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: end;
      }
      h1, h2, p { margin: 0; }
      h1 { font-size: clamp(28px, 4vw, 44px); font-weight: 760; }
      .eyebrow {
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: 8px;
      }
      main {
        width: min(1120px, calc(100vw - 32px));
        margin: 0 auto 32px;
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) minmax(300px, .9fr);
        gap: 18px;
      }
      section {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 22px;
        box-shadow: 0 14px 34px rgba(31, 43, 58, .08);
      }
      .status-panel { display: grid; gap: 18px; }
      .status-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
      }
      .state {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-size: 20px;
        font-weight: 760;
      }
      .dot {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: var(--muted);
        box-shadow: 0 0 0 6px rgba(99, 112, 131, .12);
      }
      .state-running .dot { background: var(--green); box-shadow: 0 0 0 6px rgba(23, 128, 61, .14); }
      .state-starting .dot, .state-unhealthy .dot { background: var(--amber); box-shadow: 0 0 0 6px rgba(160, 90, 0, .14); }
      .state-stopped .dot { background: var(--red); box-shadow: 0 0 0 6px rgba(192, 57, 43, .12); }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      button {
        border: 0;
        border-radius: 7px;
        padding: 10px 14px;
        font-weight: 720;
        cursor: pointer;
        color: white;
        background: var(--blue);
      }
      button.secondary { background: #415166; }
      button.danger { background: var(--red); }
      button:disabled { opacity: .45; cursor: not-allowed; }
      .message {
        color: var(--muted);
        line-height: 1.6;
      }
      dl {
        display: grid;
        grid-template-columns: 120px minmax(0, 1fr);
        gap: 10px 14px;
        margin: 0;
      }
      dt { color: var(--muted); }
      dd {
        margin: 0;
        min-width: 0;
        overflow-wrap: anywhere;
        font-family: Consolas, "SFMono-Regular", monospace;
      }
      .logs {
        grid-column: 1 / -1;
      }
      pre {
        min-height: 160px;
        max-height: 360px;
        overflow: auto;
        margin: 14px 0 0;
        padding: 14px;
        border-radius: 8px;
        background: #101820;
        color: #d9e7f2;
        font-size: 13px;
        line-height: 1.55;
        white-space: pre-wrap;
      }
      @media (max-width: 820px) {
        header { align-items: start; flex-direction: column; }
        main { grid-template-columns: 1fr; }
        dl { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <header>
      <div>
        <p class="eyebrow">Local Voice Service</p>
        <h1>VoxCPM 控制台</h1>
      </div>
      <div class="actions">
        <button id="refresh-button" class="secondary" type="button">刷新</button>
      </div>
    </header>
    <main>
      <section class="status-panel" aria-labelledby="status-title">
        <div class="status-row">
          <div>
            <p class="eyebrow">Bridge Status</p>
            <h2 id="status-title" class="state state-stopped"><span class="dot"></span><span id="state-label">读取中</span></h2>
          </div>
          <div class="actions">
            <button id="start-button" type="button">启动模型</button>
            <button id="stop-button" class="danger" type="button">关闭模型</button>
          </div>
        </div>
        <p id="message" class="message"></p>
      </section>
      <section aria-labelledby="config-title">
        <p class="eyebrow">Runtime</p>
        <h2 id="config-title">当前配置</h2>
        <dl>
          <dt>地址</dt><dd id="health-url">-</dd>
          <dt>PID</dt><dd id="pid">-</dd>
          <dt>日志</dt><dd id="log-path">-</dd>
          <dt>命令</dt><dd id="command">-</dd>
        </dl>
      </section>
      <section class="logs" aria-labelledby="logs-title">
        <div class="status-row">
          <div>
            <p class="eyebrow">Bridge Log</p>
            <h2 id="logs-title">运行日志</h2>
          </div>
          <button id="log-button" class="secondary" type="button">刷新日志</button>
        </div>
        <pre id="logs">暂无日志</pre>
      </section>
    </main>
    <script>
      const stateLabel = document.querySelector("#state-label");
      const stateTitle = document.querySelector("#status-title");
      const message = document.querySelector("#message");
      const startButton = document.querySelector("#start-button");
      const stopButton = document.querySelector("#stop-button");
      const refreshButton = document.querySelector("#refresh-button");
      const logButton = document.querySelector("#log-button");
      const labels = {
        running: "运行中",
        external: "外部运行中",
        starting: "启动中",
        unhealthy: "异常",
        stopped: "已停止"
      };

      async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "请求失败");
        return body;
      }

      async function refreshStatus() {
        setBusy(true);
        try {
          renderStatus(await requestJson("/api/status"));
        } catch (error) {
          message.textContent = error.message;
        } finally {
          setBusy(false);
        }
      }

      async function startService() {
        setBusy(true);
        try {
          renderStatus(await requestJson("/api/start", { method: "POST" }));
          await refreshLogs();
        } catch (error) {
          message.textContent = error.message;
        } finally {
          setBusy(false);
        }
      }

      async function stopService() {
        setBusy(true);
        try {
          renderStatus(await requestJson("/api/stop", { method: "POST" }));
          await refreshLogs();
        } catch (error) {
          message.textContent = error.message;
        } finally {
          setBusy(false);
        }
      }

      async function refreshLogs() {
        const body = await requestJson("/api/logs?lines=120");
        document.querySelector("#logs").textContent = body.lines.length ? body.lines.join("\\n") : "暂无日志";
      }

      function renderStatus(status) {
        stateTitle.className = `state state-${status.state}`;
        stateLabel.textContent = labels[status.state] || status.state;
        message.textContent = status.message || "";
        document.querySelector("#health-url").textContent = status.healthUrl || "-";
        document.querySelector("#pid").textContent = status.pid || "-";
        document.querySelector("#log-path").textContent = status.logPath || "-";
        document.querySelector("#command").textContent = (status.command || []).join(" ");
        startButton.disabled = status.running || status.state === "starting" || status.state === "unhealthy";
        stopButton.disabled = status.state === "stopped" || status.state === "external";
      }

      function setBusy(isBusy) {
        refreshButton.disabled = isBusy;
        logButton.disabled = isBusy;
      }

      startButton.addEventListener("click", startService);
      stopButton.addEventListener("click", stopService);
      refreshButton.addEventListener("click", refreshStatus);
      logButton.addEventListener("click", refreshLogs);
      refreshStatus();
      refreshLogs();
      setInterval(refreshStatus, 5000);
    </script>
  </body>
</html>
"""


if __name__ == "__main__":
    main()
