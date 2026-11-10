# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""pawmatch.api 단위 테스트 (실제 API는 호출하지 않고 응답을 흉내 냅니다)."""

import pytest
import requests

from pawmatch import api


class FakeResponse:
    def __init__(self, payload=None, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def ok_body(items, total):
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {"items": items, "totalCount": total, "pageNo": 1, "numOfRows": 20},
        }
    }


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr(api, "RETRY_BACKOFF", 0)


@pytest.fixture
def fake_get(monkeypatch):
    calls = {}

    def install(response):
        def _get(url, params=None, timeout=None):
            calls["url"], calls["params"] = url, params
            return response

        monkeypatch.setattr(api._SESSION, "get", _get)
        return calls

    return install


def test_returns_list_and_total(fake_get):
    calls = fake_get(FakeResponse(ok_body({"item": [{"desertionNo": "1"}, {"desertionNo": "2"}]}, 2)))
    dogs, total = api.fetch_abandoned_dogs("KEY", rows=2)
    assert [d["desertionNo"] for d in dogs] == ["1", "2"]
    assert total == 2
    assert calls["url"].endswith("/abandonmentPublic_v2")
    assert calls["params"]["upkind"] == api.DOG_UPKIND
    assert calls["params"]["serviceKey"] == "KEY"
    assert calls["params"]["_type"] == "json"


def test_single_item_is_wrapped_in_list(fake_get):
    fake_get(FakeResponse(ok_body({"item": {"desertionNo": "1"}}, 1)))
    dogs, total = api.fetch_abandoned_dogs("KEY")
    assert dogs == [{"desertionNo": "1"}] and total == 1


def test_empty_result(fake_get):
    fake_get(FakeResponse(ok_body("", 0)))
    assert api.fetch_abandoned_dogs("KEY") == ([], 0)


def test_unset_filters_are_not_sent(fake_get):
    calls = fake_get(FakeResponse(ok_body("", 0)))
    api.fetch_abandoned_dogs("KEY", state=None, upr_cd="6110000")
    assert "state" not in calls["params"] and "bgnde" not in calls["params"]
    assert calls["params"]["upr_cd"] == "6110000"


def test_error_result_code_raises(fake_get):
    fake_get(FakeResponse({"response": {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}}))
    with pytest.raises(api.ApiError, match="SERVICE_KEY_IS_NOT_REGISTERED_ERROR"):
        api.fetch_abandoned_dogs("BAD")


def test_xml_error_response_raises(fake_get):
    fake_get(FakeResponse(None, text="<OpenAPI_ServiceResponse><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg></OpenAPI_ServiceResponse>"))
    with pytest.raises(api.ApiError, match="SERVICE_KEY_IS_NOT_REGISTERED_ERROR"):
        api.fetch_abandoned_dogs("BAD")


def test_http_error_raises(fake_get):
    fake_get(FakeResponse(None, status=500, text="Internal Server Error"))
    with pytest.raises(api.ApiError, match="HTTP 500"):
        api.fetch_abandoned_dogs("KEY")


def test_network_error_raises_after_retries(monkeypatch):
    attempts = []

    def boom(*a, **k):
        attempts.append(1)
        raise requests.ConnectionError("down")

    monkeypatch.setattr(api._SESSION, "get", boom)
    with pytest.raises(api.ApiError, match="연결하지 못했습니다"):
        api.fetch_abandoned_dogs("KEY")
    assert len(attempts) == api.RETRIES + 1


def test_transient_errors_are_retried(monkeypatch):
    responses = [
        requests.ConnectionError("reset"),
        FakeResponse(None, status=503, text="busy"),
        FakeResponse(ok_body({"item": {"desertionNo": "1"}}, 1)),
    ]

    def _get(*a, **k):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(api._SESSION, "get", _get)
    dogs, _ = api.fetch_abandoned_dogs("KEY")
    assert dogs == [{"desertionNo": "1"}] and responses == []


def test_client_errors_are_not_retried(monkeypatch):
    attempts = []

    def _get(*a, **k):
        attempts.append(1)
        return FakeResponse(None, status=403, text="Forbidden")

    monkeypatch.setattr(api._SESSION, "get", _get)
    with pytest.raises(api.ApiError, match="HTTP 403"):
        api.fetch_abandoned_dogs("KEY")
    assert len(attempts) == 1


def test_duplicate_records_are_removed(fake_get):
    fake_get(FakeResponse(ok_body({"item": [{"desertionNo": "1"}, {"desertionNo": "1"}, {"desertionNo": "2"}]}, 3)))
    dogs, _ = api.fetch_abandoned_dogs("KEY")
    assert [d["desertionNo"] for d in dogs] == ["1", "2"]


def install_pages(monkeypatch, pages, key=lambda p: (p.get("state"), p["pageNo"])):
    """(상태, 페이지) → 응답 표를 흉내 냅니다. 표에 없는 페이지는 빈 결과."""
    seen = []

    def _get(url, params=None, timeout=None):
        k = key(params)
        seen.append(k)
        return FakeResponse(pages.get(k, ok_body("", 0)))

    monkeypatch.setattr(api._SESSION, "get", _get)
    return seen


def test_fetch_all_dogs_pages_through_results_for_each_state(monkeypatch):
    monkeypatch.setattr(api, "MAX_ROWS", 2)
    monkeypatch.setattr(api, "DOG_PREFETCH_PAGES", 1)
    seen = install_pages(
        monkeypatch,
        {
            ("notice", 1): ok_body({"item": [{"desertionNo": "1"}, {"desertionNo": "2"}]}, 3),
            ("notice", 2): ok_body({"item": {"desertionNo": "3"}}, 3),
            ("protect", 1): ok_body({"item": [{"desertionNo": "3"}, {"desertionNo": "4"}]}, 2),
        },
    )
    dogs = api.fetch_all_dogs("KEY")
    # 동시에 요청하므로 순서는 정해져 있지 않지만, 결과는 상태·페이지 순서를 유지합니다.
    assert sorted(seen) == [("notice", 1), ("notice", 2), ("protect", 1)]
    assert [d["desertionNo"] for d in dogs] == ["1", "2", "3", "4"]  # 3번 중복 제거


def test_prefetched_pages_avoid_a_second_round(monkeypatch):
    monkeypatch.setattr(api, "MAX_ROWS", 2)
    monkeypatch.setattr(api, "DOG_PREFETCH_PAGES", 2)
    seen = install_pages(
        monkeypatch,
        {
            ("notice", 1): ok_body({"item": [{"desertionNo": "1"}, {"desertionNo": "2"}]}, 3),
            ("notice", 2): ok_body({"item": {"desertionNo": "3"}}, 3),
        },
    )
    dogs = api.fetch_all_dogs("KEY", states=("notice",))
    assert sorted(seen) == [("notice", 1), ("notice", 2)]
    assert [d["desertionNo"] for d in dogs] == ["1", "2", "3"]


def test_remaining_pages_are_fetched_after_prefetch(monkeypatch):
    monkeypatch.setattr(api, "MAX_ROWS", 1)
    monkeypatch.setattr(api, "DOG_PREFETCH_PAGES", 2)
    seen = install_pages(
        monkeypatch,
        {("protect", p): ok_body({"item": {"desertionNo": str(p)}}, 4) for p in range(1, 5)},
    )
    dogs = api.fetch_all_dogs("KEY", states=("protect",))
    assert sorted(seen) == [("protect", p) for p in range(1, 5)]
    assert [d["desertionNo"] for d in dogs] == ["1", "2", "3", "4"]


def test_stops_when_page_is_not_full_even_if_total_is_larger(monkeypatch):
    # 실제 보호소 API는 totalCount=861인데 338건만 내려줍니다.
    monkeypatch.setattr(api, "MAX_ROWS", 3)
    seen = install_pages(
        monkeypatch,
        {(None, 1): ok_body({"item": [{"careNm": "A"}, {"careNm": "B"}]}, 10)},
    )
    assert [s["careNm"] for s in api.fetch_shelters("KEY")] == ["A", "B"]
    assert seen == [(None, 1)]


def test_fetch_shelters_uses_shelter_endpoint(fake_get):
    calls = fake_get(FakeResponse(ok_body({"item": [{"careNm": "A", "lat": "37.5", "lng": "127.0"}]}, 1)))
    shelters = api.fetch_shelters("KEY")
    assert calls["url"] == f"{api.SHELTER_BASE_URL}/shelterInfo_v2"
    assert shelters[0]["careNm"] == "A"


def test_network_error_message_does_not_leak_api_key(monkeypatch):
    """연결 오류 문구에는 요청 주소(serviceKey 포함)가 들어 있어서, 그대로 내보내면 키가 로그·화면에 나옵니다."""
    secret = "SECRET+key/abc=="

    def _get(url, params=None, timeout=None):
        encoded = requests.utils.quote(secret, safe="")
        raise requests.ConnectionError(f"Max retries exceeded with url: /x?serviceKey={encoded}&_type=json")

    monkeypatch.setattr(api._SESSION, "get", _get)
    with pytest.raises(api.ApiError) as info:
        api.fetch_abandoned_dogs(secret)
    message = str(info.value)
    assert "ConnectionError" in message
    assert "serviceKey" not in message and "SECRET" not in message
    assert info.value.__cause__ is None  # 원래 오류를 붙여 두면 traceback에 주소가 다시 나옴
