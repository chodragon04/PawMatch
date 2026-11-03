# 🐾 PawMatch

**사진과 생활 환경으로 찾는 유기견 입양 매칭 웹서비스**

보호소에 있는 유기견을 사진이나 생활 환경을 기준으로 찾아볼 수 있는 웹서비스입니다.
국가동물보호정보시스템의 구조동물 공공데이터를 활용합니다.

> 🚧 현재 개발 중입니다. (오픈소스소프트웨어 텀프로젝트)

## 주요 기능

| 기능 | 설명 | 상태 |
| --- | --- | --- |
| 가까운 보호소 우선 보기 | 내 위치(또는 선택한 지역)에서 가까운 보호소 순으로, 보호소별로 묶어 표시 | 완료 |
| 보호견 둘러보기 | 보호 중인 유기견 목록 조회, 지역·크기 등 조건별 검색 | 예정 |
| 마감 임박 우선 보기 | 공고 마감이 가까운 아이들을 우선적으로 표시 | 예정 |
| 입양 매칭 | 설문(주거 환경, 활동량 등)을 바탕으로 잘 맞을 것 같은 아이 추천 | 예정 |
| 사진으로 찾기 | 강아지 사진을 올리면 생김새가 비슷한 보호견 검색 | 예정 |

## 데모 / 스크린샷

추후 추가 예정

## 기술 스택

- **언어**: Python 3.10+
- **웹 프레임워크**: [Streamlit](https://streamlit.io/)
- **데이터**: 공공데이터포털 국가동물보호정보시스템 구조동물 조회 서비스
- **이미지 검색**: 사전학습 이미지 모델(CLIP) (예정)
- **배포**: [Streamlit Community Cloud](https://streamlit.io/cloud) (GitHub 푸시 시 자동 반영)

## 프로젝트 구조

```
PawMatch/
├── app.py               # Streamlit 진입점 (페이지 내비게이션)
├── pages/               # 화면별 페이지
│   ├── home.py          # 홈
│   ├── browse.py        # 보호견 둘러보기
│   ├── match.py         # 입양 매칭
│   └── photo_search.py  # 사진으로 찾기
├── pawmatch/            # 핵심 로직
│   ├── config.py        # 환경 변수(API 키) 로딩
│   ├── api.py           # 공공데이터 API 클라이언트 (유기견, 보호소)
│   ├── geo.py           # 거리 계산, 가까운 보호소 순 정렬
│   ├── display.py       # 나이·성별·공고 상태 표시 문구
│   ├── ui.py            # 유기견 카드 (사진 대체 처리 포함)
│   ├── matching.py      # 설문 기반 매칭 점수 계산
│   └── image_search.py  # 이미지 유사도 검색
├── tests/               # 단위 테스트 (pytest)
├── data/                # 데이터 캐시 (Git에 올리지 않음)
├── docs/
│   ├── data-analysis.md # 공공데이터 필드 분석 (채워진 비율, 매칭에 쓸 정보)
│   └── images/          # README용 스크린샷
├── requirements.txt
├── .env.example
└── LICENSE
```

## 실행 방법

1. 저장소 클론

   ```bash
   git clone https://github.com/chodragon04/PawMatch.git
   cd PawMatch
   ```

2. 가상환경 생성 및 패키지 설치

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. API 키 설정

   [공공데이터포털](https://www.data.go.kr/)에서 "구조동물 조회 서비스"를 활용신청한 뒤,
   `.env.example`을 복사해 `.env`를 만들고 일반 인증키(Decoding)를 넣습니다.

   ```bash
   cp .env.example .env
   ```

   (`.streamlit/secrets.toml`을 써도 됩니다. `.streamlit/secrets.toml.example` 참고)

4. 실행

   ```bash
   streamlit run app.py
   ```

5. 테스트 (선택)

   ```bash
   pip install -r requirements-dev.txt
   pytest
   ```

## 배포 (Streamlit Community Cloud)

1. [share.streamlit.io](https://share.streamlit.io/)에 GitHub 계정으로 로그인
2. **Create app** → 이 저장소, 브랜치, Main file `app.py` 선택
3. **Advanced settings**에서 Python 버전 선택, **Secrets** 칸에 아래 내용 입력

   ```toml
   DATA_GO_KR_API_KEY = "발급받은_일반_인증키(Decoding)"
   ```

4. **Deploy** 클릭. 이후 해당 브랜치에 푸시하면 자동으로 다시 배포됩니다.

## 데이터 출처

- 농림축산식품부 농림축산검역본부, 국가동물보호정보시스템 구조동물 조회 서비스 (공공데이터포털)
- 농림축산식품부 농림축산검역본부, 국가동물보호정보시스템 동물보호센터 정보 조회 서비스 (공공데이터포털)

공공데이터포털에서 위 두 서비스를 모두 활용신청해야 합니다. (같은 인증키 사용)

## 참고자료

- [Streamlit Documentation](https://docs.streamlit.io/)
- [streamlit-js-eval](https://github.com/aghasemi/streamlit_js_eval) (MIT License): 브라우저 위치 정보(Geolocation) 가져오기에 사용
- [공공데이터포털](https://www.data.go.kr/)
- 본 프로젝트는 AI 코딩 도구(Anthropic Claude)의 도움을 받아 개발했습니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)로 배포됩니다.
