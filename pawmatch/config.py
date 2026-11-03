"""환경 변수 설정을 읽어오는 모듈.

API 키는 코드에 직접 쓰지 않고 .env 파일(로컬) 또는
배포 환경의 환경 변수(Secrets)에서 읽어옵니다.
"""

import os

from dotenv import load_dotenv

load_dotenv()

API_KEY_ENV = "DATA_GO_KR_API_KEY"


def get_api_key() -> str | None:
    """공공데이터포털 API 키를 반환합니다. 설정되어 있지 않으면 None."""
    key = os.getenv(API_KEY_ENV, "").strip()
    return key or None
