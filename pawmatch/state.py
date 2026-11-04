"""여러 화면이 같이 쓰는 화면 상태(st.session_state)의 key.

입력칸에는 persist_state=PERSIST를 주어, 다른 화면에 갔다 와도 값이 남게 합니다.
(Streamlit은 기본적으로 화면을 옮기면 이전 화면의 입력값을 지웁니다)
"""

PERSIST = "session"

# 입양 매칭
MATCH_SURVEY = "match_survey"  # 제출한 설문(matching.Survey). 둘러보기의 '나와 잘 맞는 순'에도 씀
MATCH = "match"  # 매칭 화면 입력칸 key 앞부분 (위치 선택도 이 이름을 씀: match_mode, match_region ...)
MATCH_NOTICE = "match_notice"  # 둘러보기에서 조건을 가져왔을 때 한 번 보여줄 안내


def match_key(name: str) -> str:
    return f"{MATCH}_{name}"


# 보호견 둘러보기
BROWSE = "browse_"  # 둘러보기 화면 입력칸 key 앞부분
BROWSE_ORDER, BROWSE_LIMIT = f"{BROWSE}order", f"{BROWSE}limit"
