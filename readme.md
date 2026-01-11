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

    - 구글 클라우드 콘솔(https://console.cloud.google.com/) > 좌측 내비게이션 메뉴 > IAM & Admin > Service Accounts
    - API Library > 'google sheets api' 검색
    - Google Sheets API > Manage > Credentials > +Create credentials 버튼 > API Keys, Service Accounts 생성

2. Service Account 설정
    - 구글 클라우드 콘솔(https://console.cloud.google.com/) > 좌측 내비게이션 메뉴 > IAM & Admin > Service Accounts
    - +Create Service Account 버튼 > Service Account Name 입력 > Create
    - 생성된 Service Account > Keys > +Add Key > Create New Key > JSON > Create
    - 생성된 JSON 파일을 프로젝트 폴더에 복사
    - 구글 시트 > 생성한 계정에 공유해주기

3. 파이썬 환경설정
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
pytest --suite=Prerequisites --suite=Installation 실행
  │
  ├─ [conftest.py] pytest_addoption()
  │     └─ --suite 옵션 등록
  │
  ├─ [conftest.py] pytest_configure()
  │     └─ selected_suite_names 저장
  │
  ├─ [conftest.py] pytest_collection_modifyitems()
  │     └─ @pytest.mark.suite 마커로 테스트 케이스 필터링
  │
  ├─ [conftest.py] pytest_sessionstart()
  │     │
  │     ├─ [testrail_client.py] get_testrail_config()
  │     │     ├─ testrail.cfg 로드
  │     │     └─ section_id ↔ suite_name 매핑
  │     │
  │     ├─ [testrail_client.py] create_milestone()
  │     │     ├─ testrail_api("get_milestones/...")
  │     │     └─ testrail_api("add_milestone/...", POST) (없으면 생성)
  │     │
  │     ├─ [testrail_client.py] create_test_runs()
  │     │     ├─ get_filtered_case_ids()
  │     │     │     ├─ get_case_type_ids() → type_id 조회
  │     │     │     └─ testrail_api("get_cases/...") (섹션별)
  │     │     │
  │     │     └─ create_test_run() (섹션별 반복)
  │     │           └─ testrail_api("add_run/...", POST)
  │     │
  │     └─ [testrail_client.py] link_runs_to_milestone()
  │           └─ testrail_api("update_run/...", POST) (각 Run별)
  │
  ├─ [테스트 실행] 각 테스트마다:
  │     │
  │     └─ [conftest.py] pytest_runtest_makereport()
  │           ├─ get_case_id_for_test() → 인덱스 기반 case_id 조회
  │           └─ [testrail_client.py] send_result_to_testrail()
  │                 └─ testrail_api("add_result_for_case/...", POST)
  │
  └─ [conftest.py] pytest_sessionfinish()
        ├─ 통계 출력
        └─ [google_sheets.py] save_summary_sheets()
              └─ get_sheet() → 구글 시트 연결 및 저장
```

## 파일 구조
```
testrail/
├── conftest.py          # Pytest hook 함수 (진입점)
├── testrail_client.py   # TestRail API 함수
├── google_sheets.py     # Google Sheets 함수
├── testrail_config.py   # 설정 파일 로드
├── testrail.cfg         # 설정 값
├── data.py              # API 키, URL 등 민감정보
└── test_example.py      # 테스트 코드
```

5. 실행 방법
  ```
  # 특정 suite만 실행
  pytest -m "suite"  # suite 마커가 있는 모든 테스트
  pytest -k "Prerequisites"  # 특정 suite 이름으로 필터링
  # 또는 커스텀 옵션 추가 가능
  pytest --suite=Prerequisites
  ```