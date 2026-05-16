from pathlib import Path

import soundfile as sf
import torch
from voxcpm import VoxCPM


MODEL_PATH = Path("models/models--openbmb--VoxCPM2/snapshots/bffb3df5a29440629464e5e839f4d214c8714c3d")
OUTPUT_PATH = Path("outputs/test.wav")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading model on {device}", flush=True)
    model = VoxCPM(
        voxcpm_model_path=str(MODEL_PATH),
        zipenhancer_model_path=None,
        enable_denoiser=False,
        optimize=False,
        device=device,
    )
    print("generating audio", flush=True)
    audio = model.generate(
        text="你好，VoxCPM 本地部署测试。",
        cfg_value=2.0,
        inference_timesteps=4,
        normalize=False,
        denoise=False,
    )
    sf.write(str(OUTPUT_PATH), audio, model.tts_model.sample_rate)
    print(f"saved {OUTPUT_PATH.resolve()}", flush=True)


if __name__ == "__main__":
    main()
