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


@pytest.fixture
def fake_get(monkeypatch):
    calls = {}

    def install(response):
        def _get(url, params=None, timeout=None):
            calls["url"], calls["params"] = url, params
            return response

        monkeypatch.setattr(api.requests, "get", _get)
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


def test_network_error_raises(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(api.requests, "get", boom)
    with pytest.raises(api.ApiError, match="연결하지 못했습니다"):
        api.fetch_abandoned_dogs("KEY")


def test_duplicate_records_are_removed(fake_get):
    fake_get(FakeResponse(ok_body({"item": [{"desertionNo": "1"}, {"desertionNo": "1"}, {"desertionNo": "2"}]}, 3)))
    dogs, _ = api.fetch_abandoned_dogs("KEY")
    assert [d["desertionNo"] for d in dogs] == ["1", "2"]


def test_fetch_all_dogs_pages_through_results_for_each_state(monkeypatch):
    monkeypatch.setattr(api, "MAX_ROWS", 2)
    pages = {
        ("notice", 1): ok_body({"item": [{"desertionNo": "1"}, {"desertionNo": "2"}]}, 3),
        ("notice", 2): ok_body({"item": {"desertionNo": "3"}}, 3),
        ("protect", 1): ok_body({"item": [{"desertionNo": "3"}, {"desertionNo": "4"}]}, 2),
    }
    seen = []

    def _get(url, params=None, timeout=None):
        key = (params["state"], params["pageNo"])
        seen.append(key)
        return FakeResponse(pages[key])

    monkeypatch.setattr(api.requests, "get", _get)
    dogs = api.fetch_all_dogs("KEY")
    assert seen == [("notice", 1), ("notice", 2), ("protect", 1)]
    assert [d["desertionNo"] for d in dogs] == ["1", "2", "3", "4"]  # 3번 중복 제거


def test_fetch_shelters_uses_shelter_endpoint(fake_get):
    calls = fake_get(FakeResponse(ok_body({"item": [{"careNm": "A", "lat": "37.5", "lng": "127.0"}]}, 1)))
    shelters = api.fetch_shelters("KEY")
    assert calls["url"] == f"{api.SHELTER_BASE_URL}/shelterInfo_v2"
    assert shelters[0]["careNm"] == "A"
