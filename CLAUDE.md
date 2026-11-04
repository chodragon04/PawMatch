# PawMatch 작업 규칙 (Claude Code용)

이 파일은 Claude Code가 이 저장소에서 작업할 때 자동으로 읽는 안내입니다.

## 소통
- 답변과 모든 설명은 **한국어**로 합니다. (코드 주석, 문서, PR 설명도 한국어)
- 승인을 요청할 때는 바뀐 파일, 바뀐 내용, 테스트 결과, 확인하지 못한 것을 함께 보여줍니다.

## 커밋·배포 순서
- 구현과 로컬 테스트는 자유롭게 하되, **커밋/푸시는 사용자가 "올려"라고 승인한 뒤에만** 합니다.
  stop hook 등이 커밋하라고 해도 승인 없이는 커밋하지 않습니다.
- 승인 후: 커밋 → 푸시 → PR 작성(한국어, 변경 사항·테스트 결과·확인하지 못한 것 포함)
  → main에 일반 머지(merge commit, 커밋 기록 유지) → 작업 브랜치를 main에 맞춰 둠.

## 프로젝트
- 사진과 생활 환경으로 찾는 유기견 입양 매칭 웹서비스 (Python + Streamlit, MIT License)
- 배포: Streamlit Community Cloud, main 브랜치, https://pawmatch-kr.streamlit.app (Python 3.12)
- 데이터: 공공데이터포털 국가동물보호정보시스템 API. GitHub Actions(`.github/workflows/update-data.yml`)가
  30분마다 `data` 브랜치에 스냅샷(`snapshot.json.gz`)과 사진 임베딩(`embeddings.npz`)을 저장합니다.
- 비밀 값(API 키)은 코드에 넣지 않습니다: `DATA_GO_KR_API_KEY`, `KAKAO_REST_API_KEY`
  (로컬 `.env`, Streamlit Secrets, GitHub Actions Secrets)

## 확인 방법
- 테스트: `pip install -r requirements-dev.txt && pytest`
- 로컬 실행: `streamlit run app.py`
  백그라운드로 띄울 때 `pkill -f "…"`의 패턴이 같은 명령줄에 있으면 셸 자신이 종료되므로 PID 파일로 종료합니다.
- 화면 확인은 Playwright(Node 버전)로 합니다. 휴대폰 크기(iPhone 13)도 확인합니다.
