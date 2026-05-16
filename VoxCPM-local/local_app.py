import argparse
from pathlib import Path
from threading import Lock

import gradio as gr
import numpy as np
import torch
from voxcpm import VoxCPM


DEFAULT_MODEL_PATH = Path(
    "models/models--openbmb--VoxCPM2/snapshots/bffb3df5a29440629464e5e839f4d214c8714c3d"
)


class LocalVoxCPM:
    def __init__(self, model_path: Path, device: str, concurrency: int) -> None:
        self.model_path = model_path
        self.device = self._resolve_device(device)
        self.concurrency = concurrency
        self._model = None
        self._load_lock = Lock()

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def model(self) -> VoxCPM:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    self._model = VoxCPM(
                        voxcpm_model_path=str(self.model_path),
                        zipenhancer_model_path=None,
                        enable_denoiser=False,
                        optimize=False,
                        device=self.device,
                    )
        return self._model

    def generate(
        self,
        text: str,
        control: str,
        reference_audio: str | None,
        prompt_text: str,
        cfg_value: float,
        steps: int,
        normalize: bool,
    ):
        text = (text or "").strip()
        if not text:
            raise gr.Error("请输入要合成的文本。")

        control = (control or "").strip()
        final_text = f"({control}){text}" if control else text
        prompt_text = (prompt_text or "").strip()

        kwargs = {
            "text": final_text,
            "reference_wav_path": reference_audio or None,
            "cfg_value": float(cfg_value),
            "inference_timesteps": int(steps),
            "normalize": bool(normalize),
            "denoise": False,
        }
        if reference_audio and prompt_text:
            kwargs["prompt_wav_path"] = reference_audio
            kwargs["prompt_text"] = prompt_text

        model = self.model()
        chunks = []
        for chunk in model.generate_streaming(**kwargs):
            chunks.append(chunk)
            yield model.tts_model.sample_rate, np.concatenate(chunks)

        if not chunks:
            raise gr.Error("没有生成音频，请调整文本或参数后重试。")


def create_app(engine: LocalVoxCPM) -> gr.Blocks:
    with gr.Blocks(title="VoxCPM 本地语音模型") as app:
        gr.Markdown("# VoxCPM 本地语音模型")
        with gr.Row():
            with gr.Column():
                text = gr.Textbox(
                    label="目标文本",
                    value="你好，欢迎使用本地部署的 VoxCPM 语音模型。",
                    lines=3,
                )
                control = gr.Textbox(
                    label="声音控制描述",
                    placeholder="例如：年轻女声，温柔自然，语速适中",
                    lines=2,
                )
                reference_audio = gr.Audio(
                    label="参考音频",
                    sources=["upload", "microphone"],
                    type="filepath",
                )
                prompt_text = gr.Textbox(
                    label="参考音频文本",
                    placeholder="可选。填写参考音频对应文本，可用于更细致的续写式克隆。",
                    lines=2,
                )
                with gr.Row():
                    cfg_value = gr.Slider(1.0, 3.0, value=2.0, step=0.1, label="CFG 引导强度")
                    steps = gr.Slider(1, 30, value=4, step=1, label="推理步数")
                normalize = gr.Checkbox(value=False, label="文本规范化")
                with gr.Row():
                    run = gr.Button("生成语音", variant="primary")
                    pause = gr.Button("暂停生成", variant="secondary")
            with gr.Column():
                audio = gr.Audio(label="生成结果")

        generate_event = run.click(
            fn=engine.generate,
            inputs=[text, control, reference_audio, prompt_text, cfg_value, steps, normalize],
            outputs=audio,
            show_progress=True,
            trigger_mode="multiple",
            concurrency_limit=engine.concurrency,
            concurrency_id="voxcpm-generate",
        )
        pause.click(
            fn=None,
            inputs=None,
            outputs=None,
            cancels=[generate_event],
            queue=False,
        )
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8808)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--queue-size", type=int, default=16)
    args = parser.parse_args()
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    if args.queue_size < 1:
        raise SystemExit("--queue-size must be >= 1")

    engine = LocalVoxCPM(Path(args.model_path), args.device, args.concurrency)
    print(f"Using device: {engine.device}", flush=True)
    print(f"Using model: {Path(args.model_path).resolve()}", flush=True)
    print(f"Queue concurrency: {args.concurrency}, max size: {args.queue_size}", flush=True)
    create_app(engine).queue(
        default_concurrency_limit=args.concurrency,
        max_size=args.queue_size,
    ).launch(
        server_name=args.host,
        server_port=args.port,
        show_error=True,
    )


if __name__ == "__main__":
    main()
