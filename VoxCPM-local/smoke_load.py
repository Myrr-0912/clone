from pathlib import Path

import torch
from voxcpm import VoxCPM


MODEL_PATH = Path("models/models--openbmb--VoxCPM2/snapshots/bffb3df5a29440629464e5e839f4d214c8714c3d")


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading model from {MODEL_PATH.resolve()}", flush=True)
    print(f"device={device}", flush=True)
    model = VoxCPM(
        voxcpm_model_path=str(MODEL_PATH),
        zipenhancer_model_path=None,
        enable_denoiser=False,
        optimize=False,
        device=device,
    )
    print(f"loaded sample_rate={model.tts_model.sample_rate}", flush=True)


if __name__ == "__main__":
    main()
