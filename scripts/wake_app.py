# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""배포된 앱(Streamlit Community Cloud)이 잠들지 않게 실제 브라우저로 열어 봅니다.

Streamlit Community Cloud는 한동안(약 12시간) 아무도 접속하지 않으면 앱을 재웁니다.
주소에 단순히 요청(HTTP GET)만 보내면 빈 HTML만 받고 앱은 시작되지 않아서, 헤드리스 브라우저로
화면을 실제로 열고, 잠들어 있으면 "Yes, get this app back up!" 버튼을 눌러 깨웁니다.
GitHub Actions(.github/workflows/keep-awake.yml)가 몇 시간마다 실행합니다.

    python scripts/wake_app.py                      # 기본 주소
    APP_URL=http://localhost:8501 python scripts/wake_app.py

앱 화면이 끝까지 뜨지 않으면 종료 코드 1로 끝나서 워크플로가 실패로 표시됩니다.
"""

from __future__ import annotations

import os
import re
import sys
import time

from playwright.sync_api import Page, sync_playwright

APP_URL = os.getenv("APP_URL", "https://pawmatch-kr.streamlit.app")
READY_TEXT = "가족을 기다리는 아이들"  # 홈 화면이 다 떴을 때 보이는 문구
WAKE_BUTTON = re.compile(r"get this app back up", re.IGNORECASE)
TIMEOUT_S = 240  # 잠든 앱을 깨우면 1분 정도 걸립니다


def app_is_ready(page: Page) -> bool:
    """앱 화면이 떴는지: Streamlit Cloud는 앱을 iframe 안에 띄우므로 모든 frame을 확인합니다."""
    for frame in page.frames:
        try:
            if frame.get_by_text(READY_TEXT).count():
                return True
        except Exception:  # 다른 주소로 바뀌는 중인 frame 등
            continue
    return False


def press_wake_button(page: Page) -> bool:
    for frame in page.frames:
        try:
            button = frame.get_by_role("button", name=WAKE_BUTTON)
            if button.count():
                button.first.click()
                return True
        except Exception:
            continue
    return False


def main() -> int:
    started = time.monotonic()
    woke = False
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page()
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=90_000)
        while time.monotonic() - started < TIMEOUT_S:
            if app_is_ready(page):
                break
            if not woke and press_wake_button(page):
                woke = True
                print("앱이 잠들어 있어서 깨우기 버튼을 눌렀습니다.")
            page.wait_for_timeout(3_000)
        else:
            print(f"{TIMEOUT_S}초 안에 앱 화면이 뜨지 않았습니다: {APP_URL}", file=sys.stderr)
            page.screenshot(path="wake_app_failed.png")
            browser.close()
            return 1
        browser.close()
    state = "깨워서 열림" if woke else "이미 깨어 있음"
    print(f"{APP_URL}: {state} ({time.monotonic() - started:.0f}초)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
