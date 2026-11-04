"""pawmatch.image_search 테스트. 실제 CLIP 모델 대신 '사진 색 → 벡터' 가짜 임베딩으로 흐름을 확인합니다."""

import io

import numpy as np
from PIL import Image

from pawmatch import image_search as I

COLORS = {"white": (250, 250, 250), "brown": (140, 80, 30), "black": (10, 10, 10), "cream": (240, 220, 180)}


def img(color):
    return Image.new("RGB", (32, 32), COLORS[color])


def fake_embed(images):
    """사진 평균 색 (R, G, B, 255-R, 255-G, 255-B)을 앞 6칸에 넣은 벡터. 색이 비슷할수록 유사도가 높음."""
    out = np.zeros((len(images), I.DIM), np.float32)
    for i, image in enumerate(images):
        rgb = np.asarray(image, np.float32).reshape(-1, 3).mean(axis=0)
        out[i, :6] = np.concatenate([rgb, 255 - rgb])
    return I.normalize(out)


def dog(no, *colors):
    d = {"desertionNo": no}
    for i, c in enumerate(colors, 1):
        d[f"popfile{i}"] = f"http://openapi.animal.go.kr/{no}_{c}_{i}.jpg"
    return d


def color_of(url):
    return url.rsplit("/", 1)[1].split("_")[1]


def fake_download(url):
    return img(color_of(url))


DOGS = [dog("1", "white", "cream"), dog("2", "brown"), dog("3", "black", "black", "black", "black")]


def test_photo_targets_limit_and_https():
    targets = I.photo_targets(DOGS)
    assert [t[0] for t in targets] == ["1", "1", "2", "3", "3", "3"]  # 한 아이 최대 3장
    assert all(url.startswith("https://") for _, url in targets)


def test_build_search_roundtrip():
    index, stats = I.build_index(DOGS, None, fake_embed, fake_download)
    assert (stats.embedded, stats.reused, stats.failed) == (6, 0, 0)
    assert index.dog_ids() == {"1", "2", "3"}

    restored = I.decode_index(I.encode_index(index))  # 저장했다 다시 읽어도 같음 (float16 저장)
    assert restored.ids.tolist() == index.ids.tolist() and np.allclose(restored.vectors, index.vectors, atol=1e-3)

    query = fake_embed([img("cream")])[0]
    results = restored.search(query, top_k=3)
    assert [r[0] for r in results] == ["1", "2", "3"]  # 크림색 사진이 있는 1번이 가장 닮음
    assert color_of(results[0][2]) == "cream"  # 가장 닮은 사진 주소
    assert results[0][1] > results[1][1] > results[2][1]
    assert [r[0] for r in restored.search(query, allowed={"2", "3"})] == ["2", "3"]  # 지역 등으로 거르기
    assert len(restored.search(query, top_k=1)) == 1


def test_previous_embeddings_are_reused_and_failures_skipped():
    first, _ = I.build_index(DOGS[:2], None, fake_embed, fake_download)
    calls = []

    def counting_download(url):
        calls.append(url)
        return None if "black_2" in url else fake_download(url)  # 한 장은 받기 실패

    index, stats = I.build_index(DOGS, first, fake_embed, counting_download)
    assert stats.reused == 3 and stats.embedded == 2 and stats.failed == 1
    assert all("/3_" in url for url in calls)  # 새로 들어온 3번 사진만 받음
    assert index.dog_ids() == {"1", "2", "3"}


def test_deadline_defers_remaining_photos():
    ticks = iter([0, 100])  # 첫 묶음은 시간 안, 두 번째 묶음에서 시간 초과
    index, stats = I.build_index(DOGS, None, fake_embed, fake_download, deadline=50, batch=2, clock=lambda: next(ticks))
    assert stats.embedded == 2 and stats.skipped_for_time == 4
    assert len(index) == 2


def test_keep_current_drops_adopted_dogs():
    index, _ = I.build_index(DOGS, None, fake_embed, fake_download)
    kept = I.keep_current(index, DOGS[1:])  # 1번이 입양됨
    assert kept.dog_ids() == {"2", "3"}


def test_other_model_embeddings_are_not_reused():
    index, _ = I.build_index(DOGS, None, fake_embed, fake_download)
    index.model = "other-model"
    _, stats = I.build_index(DOGS, index, fake_embed, fake_download)
    assert stats.reused == 0 and stats.embedded == 6


def test_load_image_fixes_rotation_and_shrinks():
    big = Image.new("RGB", (2000, 1000), (1, 2, 3))
    exif = big.getexif()
    exif[0x0112] = 6  # 휴대폰 세로 사진: 90도 돌려서 저장됨
    buf = io.BytesIO()
    big.save(buf, format="JPEG", exif=exif)
    loaded = I.load_image(buf.getvalue())
    assert loaded.size == (256, 512) and loaded.mode == "RGB"


def test_empty_index_search():
    assert I.empty_index().search(np.ones(I.DIM)) == []
