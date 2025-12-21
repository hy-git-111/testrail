# Pytest 연동
## 사전 환경 설정
- 파이썬 확장프로그램 설치
- 가상 환경 설정 : 
    python -m venv venv
    .\.venv\Scripts\activate
- 인터프리터 가상환경으로 설정

TestRail: API 활성화 + API Key
Google: Google Sheets API + 서비스 계정(키 파일) + 시트 공유
Python 스크립트: 둘 다 붙어서 데이터 한 줄 써보기
   
## Google Sheets 연동
1. Google Sheets API 설정  
사전 조건 : 구글 2단계 인증 설정

    - 구글 클라우드 콘솔 진입(https://console.cloud.google.com/)
    - 좌측 내비게이션 메뉴 > API&Services
    - API Library > 'google sheets api' 검색
    - Google Sheets API > Manage > Credentials > +Create credentials 버튼 > API Keys, Service Accounts 생성

    - 구글 시트 > 생성한 계정에 공유해주기

2. 파이썬 환경설정
pip install gspread google-auth requests

## TestRail 연동
1. TestRail API 설정
* 관리자 계정에서 API 활성화
    - 설정 > Site Settings
    - API > Enable API 체크 > Save
    - API > Enable session authentication for API 체크 > Save

* 개인 계정에서 API 키 생성
    - My Settings > API KEYS
    - Add Key > Name 입력 후 API 키 복사해두기 > Add Key
    - Save Configuration

2. 파이썬 설정
pip install pytest-testrail

3. config 파일 추가(testrail.cfg)

4. conftest.py 작성


# 전체 흐름 다이어그램

```
pytest 실행
  ↓
pytest_sessionstart
  ├─ 1. Milestone 생성/확인
  └─ 2. get_filtered_cases()
      ├─ 섹션 목록 가져오기
      └─ 각 섹션별로:
          ├─ 케이스 가져오기
          ├─ Type 필터링
          ├─ Case ID 배열 생성
          └─ Run 생성 (섹션별)
  ↓
테스트 실행
  ├─ 테스트 1 → TestRail 결과 저장
  ├─ 테스트 2 → TestRail 결과 저장
  └─ 테스트 3 → TestRail 결과 저장
  ↓
pytest_sessionfinish
  ├─ 통계 출력
  └─ Google Sheets 저장 (덮어쓰기)
```