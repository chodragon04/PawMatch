"""사진으로 찾기: 사전학습 이미지 모델(CLIP)로 생김새가 비슷한 보호견을 찾습니다.

- 모델: OpenAI CLIP ViT-B/32 이미지 인코더 (MIT License)를 Qdrant가 ONNX로 변환한 것
  (Hugging Face `Qdrant/clip-ViT-B-32-vision`), fastembed(Apache-2.0)로 실행합니다.
  PyTorch 없이 onnxruntime만으로 돌아서 설치가 가볍습니다.
- 보호견 사진의 임베딩(512차원 벡터)은 GitHub Actions가 미리 계산해 `data` 브랜치에
  embeddings.npz로 저장합니다(scripts/build_embeddings.py). 앱은 사용자가 올린 사진 한 장만 계산합니다.
- 유사도: 정규화한 벡터의 내적(코사인 유사도). 한 아이의 사진이 여러 장이면 가장 닮은 사진의 점수를 씁니다.
"""

from __future__ import annotations

import io
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import requests
from PIL import Image, ImageOps

from pawmatch.data import LOCAL_SNAPSHOT_DIR, REMOTE_SNAPSHOT_URL
from pawmatch.display import photo_urls

MODEL_NAME = "Qdrant/clip-ViT-B-32-vision"
DIM = 512
EMBEDDINGS_FILE = "embeddings.npz"
MAX_PHOTOS_PER_DOG = 3  # 대부분 2장, 많으면 8장까지 있어서 앞의 3장만 씁니다
MAX_IMAGE_SIDE = 512  # 내려받은 사진은 이 크기로 줄여서 메모리를 아낍니다 (모델 입력은 224px)


# ---------------------------------------------------------------- 저장 형식


@dataclass
class PhotoIndex:
    """보호견 사진 임베딩 모음. 행마다 (구조번호, 사진 주소, 벡터)."""

    ids: np.ndarray  # (N,) str
    urls: np.ndarray  # (N,) str
    vectors: np.ndarray  # (N, DIM) float32, 길이 1로 정규화
    model: str = MODEL_NAME
    created_at: datetime | None = None

    def __len__(self) -> int:
        return len(self.ids)

    def dog_ids(self) -> set[str]:
        return set(self.ids.tolist())

    def search(
        self, query: np.ndarray, top_k: int = 24, allowed: set[str] | None = None
    ) -> list[tuple[str, float, str]]:
        """가장 닮은 아이 top_k마리: [(구조번호, 유사도, 가장 닮은 사진 주소), ...]."""
        if not len(self):
            return []
        scores = self.vectors @ normalize(query.astype(np.float32))
        results: list[tuple[str, float, str]] = []
        seen: set[str] = set()
        for row in np.argsort(-scores):
            dog_id = str(self.ids[row])
            if dog_id in seen or (allowed is not None and dog_id not in allowed):
                continue
            seen.add(dog_id)
            results.append((dog_id, float(scores[row]), str(self.urls[row])))
            if len(results) >= top_k:
                break
        return results


def empty_index() -> PhotoIndex:
    return PhotoIndex(np.array([], dtype=str), np.array([], dtype=str), np.zeros((0, DIM), np.float32))


def normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def encode_index(index: PhotoIndex) -> bytes:
    buf = io.BytesIO()
    created = (index.created_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    np.savez_compressed(
        buf, ids=index.ids.astype(str), urls=index.urls.astype(str), vectors=index.vectors.astype(np.float16),
        model=np.array(index.model), created_at=np.array(created),
    )  # fmt: skip
    return buf.getvalue()


def decode_index(blob: bytes) -> PhotoIndex:
    with np.load(io.BytesIO(blob), allow_pickle=False) as z:
        return PhotoIndex(
            ids=z["ids"].astype(str), urls=z["urls"].astype(str), vectors=z["vectors"].astype(np.float32),
            model=str(z["model"]), created_at=datetime.fromisoformat(str(z["created_at"])),
        )  # fmt: skip


def read_local_index(directory: Path | None = None) -> PhotoIndex | None:
    try:
        return decode_index(((directory or LOCAL_SNAPSHOT_DIR) / EMBEDDINGS_FILE).read_bytes())
    except (OSError, ValueError, KeyError):
        return None


def read_remote_index(base_url: str | None = None, timeout: float = 30) -> PhotoIndex | None:
    try:
        resp = requests.get(f"{(base_url or REMOTE_SNAPSHOT_URL).rstrip('/')}/{EMBEDDINGS_FILE}", timeout=timeout)
        resp.raise_for_status()
        return decode_index(resp.content)
    except (requests.RequestException, OSError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------- 사진


def photo_targets(dogs: Iterable[dict], per_dog: int = MAX_PHOTOS_PER_DOG) -> list[tuple[str, str]]:
    """임베딩할 (구조번호, 사진 주소) 목록."""
    return [
        (str(dog.get("desertionNo")), url)
        for dog in dogs
        if dog.get("desertionNo")
        for url in photo_urls(dog)[:per_dog]
    ]


def load_image(data: bytes) -> Image.Image:
    """사진 바이트 → RGB 이미지 (휴대폰 사진의 회전 정보 반영, 큰 사진은 줄임).

    JPEG는 draft로 처음부터 작게(1/2~1/8) 읽어서, 큰 휴대폰 사진도 원본 크기만큼 메모리를 쓰지 않습니다.
    """
    image = Image.open(io.BytesIO(data))
    image.draft("RGB", (MAX_IMAGE_SIDE * 2, MAX_IMAGE_SIDE * 2))
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    return image


def download_image(url: str, timeout: float = 20, retries: int = 2) -> Image.Image | None:
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                return load_image(resp.content)
            if resp.status_code < 500:
                return None
        except (requests.RequestException, OSError, ValueError):
            pass
        time.sleep(1 + attempt)
    return None


# ---------------------------------------------------------------- 모델


class ClipEmbedder:
    """CLIP 이미지 인코더. 처음 쓸 때 모델(약 340MB)을 내려받아 불러옵니다."""

    def __init__(self, cache_dir: str | None = None, threads: int | None = None):
        from fastembed import ImageEmbedding  # 무거운 모듈이라 실제로 쓸 때 불러옵니다

        self._model = ImageEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir, threads=threads)

    def __call__(self, images: list[Image.Image]) -> np.ndarray:
        vectors = np.array(list(self._model.embed(images, batch_size=32)), dtype=np.float32)
        return normalize(vectors)


# ---------------------------------------------------------------- 인덱스 만들기 (GitHub Actions)


@dataclass
class BuildStats:
    reused: int = 0
    embedded: int = 0
    failed: int = 0
    skipped_for_time: int = 0


def build_index(
    dogs: list[dict],
    previous: PhotoIndex | None,
    embed: Callable[[list[Image.Image]], np.ndarray],
    download: Callable[[str], Image.Image | None] = download_image,
    deadline: float | None = None,
    workers: int = 8,
    batch: int = 64,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[PhotoIndex, BuildStats]:
    """지금 보호 중인 아이들의 사진 임베딩을 만듭니다.

    이전 인덱스에 같은 사진 주소가 있으면 다시 계산하지 않고 그대로 씁니다(같은 모델일 때).
    deadline(clock 기준 시각)이 지나면 남은 사진은 다음 실행으로 미룹니다.
    """
    stats = BuildStats()
    targets = photo_targets(dogs)
    old: dict[str, np.ndarray] = {}
    if previous is not None and previous.model == MODEL_NAME:
        old = {str(u): v for u, v in zip(previous.urls, previous.vectors)}

    ids, urls, vectors = [], [], []
    todo = []
    for dog_id, url in targets:
        if url in old:
            ids.append(dog_id), urls.append(url), vectors.append(old[url])
            stats.reused += 1
        else:
            todo.append((dog_id, url))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(todo), batch):
            if deadline is not None and clock() > deadline:
                stats.skipped_for_time = len(todo) - start
                break
            chunk = todo[start : start + batch]
            images = list(pool.map(download, [url for _, url in chunk]))
            ok = [(item, image) for item, image in zip(chunk, images) if image is not None]
            stats.failed += len(chunk) - len(ok)
            if not ok:
                continue
            new_vectors = embed([image for _, image in ok])
            for ((dog_id, url), _), vector in zip(ok, new_vectors):
                ids.append(dog_id), urls.append(url), vectors.append(vector)
            stats.embedded += len(ok)

    index = PhotoIndex(
        ids=np.array(ids, dtype=str), urls=np.array(urls, dtype=str),
        vectors=np.array(vectors, dtype=np.float32).reshape(-1, DIM), created_at=datetime.now(timezone.utc),
    )  # fmt: skip
    return index, stats


def keep_current(previous: PhotoIndex, dogs: list[dict]) -> PhotoIndex:
    """이전 인덱스에서 지금도 보호 중인 아이의 사진만 남깁니다. (새로 만들기에 실패했을 때)"""
    current = {url for _, url in photo_targets(dogs)}
    mask = np.array([str(u) in current for u in previous.urls], dtype=bool)
    return PhotoIndex(previous.ids[mask], previous.urls[mask], previous.vectors[mask], previous.model, previous.created_at)
