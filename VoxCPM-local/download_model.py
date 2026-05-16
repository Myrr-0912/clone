import os
from pathlib import Path

from huggingface_hub import hf_hub_download


REPO_ID = "openbmb/VoxCPM2"
FILES = [
    ".gitattributes",
    "README.md",
    "config.json",
    "special_tokens_map.json",
    "tokenization_voxcpm2.py",
    "tokenizer.json",
    "tokenizer_config.json",
    "audiovae.pth",
    "model.safetensors",
]


def main() -> None:
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    cache_dir = Path("models")
    cache_dir.mkdir(exist_ok=True)

    for index, filename in enumerate(FILES, start=1):
        print(f"[{index}/{len(FILES)}] downloading {filename}", flush=True)
        path = hf_hub_download(
            repo_id=REPO_ID,
            filename=filename,
            cache_dir=str(cache_dir),
            resume_download=True,
        )
        print(f"saved {filename}: {path}", flush=True)


if __name__ == "__main__":
    main()
