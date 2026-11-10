# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""환경 변수 설정을 읽어오는 모듈.

API 키(공공데이터포털, 카카오)는 코드에 직접 쓰지 않고 아래 순서로 찾습니다.
1. 환경 변수 또는 .env 파일 (로컬 개발)
2. Streamlit secrets (Streamlit Community Cloud 앱 설정의 Secrets 또는 .streamlit/secrets.toml)
"""

import os

from dotenv import load_dotenv

load_dotenv()

API_KEY_ENV = "DATA_GO_KR_API_KEY"
KAKAO_KEY_ENV = "KAKAO_REST_API_KEY"  # 카카오 로컬 API (시/군/구 위치 찾기, 선택)


def _from_streamlit_secrets(name: str) -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:  # secrets 파일이 없거나 Streamlit 밖에서 실행된 경우
        return None
    return str(value).strip() if value else None


def get_secret(name: str) -> str | None:
    """환경 변수(.env 포함) → Streamlit secrets 순서로 값을 찾습니다. 없으면 None."""
    value = os.getenv(name, "").strip()
    return value or _from_streamlit_secrets(name)


def get_api_key() -> str | None:
    """공공데이터포털 API 키를 반환합니다. 설정되어 있지 않으면 None."""
    return get_secret(API_KEY_ENV)


def get_kakao_key() -> str | None:
    """카카오 REST API 키를 반환합니다. 설정되어 있지 않으면 None."""
    return get_secret(KAKAO_KEY_ENV)
