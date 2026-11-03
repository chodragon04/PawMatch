# 🐾 PawMatch

**사진과 생활 환경으로 찾는 유기견 입양 매칭 웹서비스**

보호소에 있는 유기견을 사진이나 생활 환경을 기준으로 찾아볼 수 있는 웹서비스입니다.
국가동물보호정보시스템의 구조동물 공공데이터를 활용합니다.

> 🚧 현재 개발 중입니다. (오픈소스소프트웨어 텀프로젝트)

## 주요 기능

| 기능 | 설명 | 상태 |
| --- | --- | --- |
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
│   ├── api.py           # 공공데이터 API 클라이언트
│   ├── matching.py      # 설문 기반 매칭 점수 계산
│   └── image_search.py  # 이미지 유사도 검색
├── data/                # 데이터 캐시 (Git에 올리지 않음)
├── docs/images/         # README용 스크린샷
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

4. 실행

   ```bash
   streamlit run app.py
   ```

## 데이터 출처

- 농림축산식품부 농림축산검역본부, 국가동물보호정보시스템 구조동물 조회 서비스 (공공데이터포털)

## 참고자료

- [Streamlit Documentation](https://docs.streamlit.io/)
- [공공데이터포털](https://www.data.go.kr/)
- 본 프로젝트는 AI 코딩 도구(Anthropic Claude)의 도움을 받아 개발했습니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)로 배포됩니다.
