"""Download Model2Vec potion-base-8M (MIT) and shrink it to ask_model.npz. Needs only numpy.

Used by the round 3 evaluation. The file isn't kept in the repo.

    python scripts/build_ask_model.py
"""
import json
import struct
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://huggingface.co/minishlab/potion-base-8M/resolve/main"

blob = requests.get(f"{BASE}/model.safetensors", timeout=300).content
size = struct.unpack("<Q", blob[:8])[0]
entry = json.loads(blob[8:8 + size])["embeddings"]
start, end = entry["data_offsets"]
matrix = np.frombuffer(blob[8 + size + start:8 + size + end], dtype="<f4").reshape(entry["shape"])
vocabulary = requests.get(f"{BASE}/tokenizer.json", timeout=120).json()["model"]["vocab"]
tokens = [token for token, _ in sorted(vocabulary.items(), key=lambda item: item[1])]
scale = float(np.abs(matrix).max()) / 127
np.savez_compressed(
    ROOT / "ask_model.npz", tokens=np.array(tokens),
    vectors=np.rint(matrix / scale).astype(np.int8), scale=np.array(scale, dtype=np.float32),
)
print(f"wrote ask_model.npz: {(ROOT / 'ask_model.npz').stat().st_size / 1e6:.1f} MB")
