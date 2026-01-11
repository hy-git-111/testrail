import pytest
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import data
import os
import testrail_config

# ===== 설정값 =====
TESTRAIL_URL = data.TRAIL_URL
TESTRAIL_USER = data.TRAIL_USER
TESTRAIL_API_KEY = data.TRAIL_API
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "gspread_account.json")
SPREADSHEET_ID = data.SPREADSHEET_ID

# 테스트 결과 저장용 리스트
test_results = []
testrail_run_id = None  # 현재 사용 중인 Run ID (마지막으로 생성된 Run)
testrail_run_ids = {}  # 섹션별 Run ID 매핑 {section_id: run_id}
case_id_to_section_id = {}  # 케이스 ID와 섹션 ID 매핑 {case_id: section_id}
milestone_id = None
test_case_ids = []  # Suite의 케이스 ID 리스트 (순서대로)
test_case_mapping = {}  # 테스트 실행 순서와 Case ID 매핑
selected_suite_names = []  # 커맨드라인에서 선택된 suite 이름들

# 섹션별 인덱스 관리를 위한 변수 추가
suite_case_ids_by_section = {}  # {suite_name: [case_ids]}
suite_test_index = {}  # {suite_name: 현재 인덱스}
section_id_to_suite_name = {}  # {section_id: suite_name}


def pytest_addoption(parser):
    """pytest 커맨드라인 옵션 추가"""
    parser.addoption(
        "--suite",
        action="append",
        default=[],
        help="실행할 Suite 이름 (여러 개 지정 가능, 예: --suite=Prerequisites --suite=Installation)"
    )

def pytest_configure(config):
    """pytest 설정 시 선택된 suite 이름 저장"""
    global selected_suite_names
    selected_suite_names = config.getoption("--suite", [])
    if selected_suite_names:
        print(f"[TestRail] 선택된 Suite: {selected_suite_names}")

def pytest_collection_modifyitems(config, items):
    """테스트 수집 후 suite 마커로 필터링"""
    global selected_suite_names
    
    # --suite 옵션이 지정되지 않으면 필터링 안함
    if not selected_suite_names:
        return
    
    selected_items = []
    deselected_items = []
    
    for item in items:
        # 테스트의 suite 마커 확인
        suite_marker = item.get_closest_marker("suite")
        if suite_marker:
            suite_name = suite_marker.args[0] if suite_marker.args else None
            # 선택된 suite에 포함되면 실행
            if suite_name and suite_name.lower() in [s.lower() for s in selected_suite_names]:
                selected_items.append(item)
            else:
                deselected_items.append(item)
        else:
            # suite 마커가 없는 테스트는 제외
            deselected_items.append(item)
    
    if deselected_items:
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items
        print(f"[TestRail] {len(selected_items)}개 테스트 선택됨, {len(deselected_items)}개 제외됨")


def get_testrail_config():
    """설정 파일에서 필요한 값 가져오기
    
    --suite 옵션이 지정된 경우, 해당 이름으로 testrail.cfg의 [SECTION_ID]에서 section_id를 가져옴
    """
    global selected_suite_names, section_id_to_suite_name
    
    config = testrail_config.load_config()
    
    # section_ids 결정: --suite 옵션이 있으면 모든 이름으로 section_id 조회
    section_ids = []
    section_id_to_suite_name = {}  # section_id와 suite_name 매핑 초기화
    
    if selected_suite_names:
        for suite_name in selected_suite_names:
            section_id = testrail_config.get_section_id_by_name(suite_name, "SECTION_ID")
            if section_id:
                section_ids.append(section_id)
                section_id_to_suite_name[section_id] = suite_name  # 매핑 저장
                print(f"[TestRail] 마커 '{suite_name}'에서 section_id={section_id} 추가")
            else:
                print(f"[Warning] 이름 '{suite_name}'에 해당하는 section_id를 찾을 수 없습니다.")
    
    result = {
        "project_id": config.getint("PROJECT", "project_id", fallback=None),
        "suite_id": config.getint("PROJECT", "test_suite_id", fallback=None),
        "milestone_name": config.get("MILESTONE", "milestone_name", fallback=""),
        "filter_name": config.get("TESTRUN", "type", fallback=""),
        "section_ids": section_ids
    }
    
    print(f"[TestRail] 설정 로드 완료: {result}")
    print(f"[TestRail] section_id_to_suite_name: {section_id_to_suite_name}")
    return result


def create_milestone(config):
    """milestone_name으로 기존 마일스톤 검색, 없으면 생성
    
    - milestone_name이 비어있으면 생성 안함
    - TestRail에서 같은 이름의 마일스톤이 있으면 그 ID 사용
    - 없으면 새로 생성
    """
    global milestone_id
    
    milestone_name = config.get("milestone_name", "").strip()
    project_id = config.get("project_id")
    
    # milestone_name이 비어있으면 건너뜀
    if not milestone_name:
        print("[TestRail] milestone_name이 비어있어서 Milestone 생성을 건너뜁니다.")
        return None
    
    # 1. TestRail API로 마일스톤 목록 조회
    milestones_data = testrail_api(f"get_milestones/{project_id}")
    if milestones_data:
        # milestones 리스트에서 name으로 기존 마일스톤 찾기
        for ms in milestones_data.get("milestones", []):
            if ms.get("name") == milestone_name:
                milestone_id = ms.get("id")
                print(f"[TestRail] 기존 Milestone 발견: '{milestone_name}' (ID: {milestone_id}) - 생성 생략")
                return milestone_id
    
    # 2. 없으면 새로 생성
    milestone_data = testrail_api(
        f"add_milestone/{project_id}",
        method="POST",
        payload={"name": milestone_name}
    )
    if milestone_data:
        milestone_id = milestone_data.get("id")
        print(f"[TestRail] Milestone 생성 완료: '{milestone_name}' (ID: {milestone_id})")
        return milestone_id
    
    return None

def get_case_type_ids(filter_name):
    """TestRail API에서 filter_name과 일치하는 Case Type의 id 반환
    
    Args:
        filter_name: Case Type 이름 (예: "Regression")
    
    Returns:
        int or None: 일치하는 type_id, 없으면 None
    """
    if not filter_name:
        return None
    
    case_types = testrail_api("get_case_types")
    if case_types:
        # filter_name과 일치하는 type_id 찾기 (대소문자 구분 없이)
        filter_name_lower = filter_name.lower()
        for case_type in case_types:
            if case_type.get("name", "").lower() == filter_name_lower:
                type_id = case_type.get("id")
                print(f"[TestRail] '{filter_name}' → type_id: {type_id}")
                return type_id
        
        print(f"[Warning] '{filter_name}'에 해당하는 Case Type을 찾을 수 없습니다.")
    return None


def get_filtered_case_ids(config):
    """설정에 맞는 Test Case IDs 반환
    
    config["section_ids"]가 있으면 해당 섹션들의 케이스만 가져옴
    """
    project_id = config["project_id"]
    section_ids = config.get("section_ids", [])
    filter_name = config.get("filter_name", "")

    if not section_ids:
        print("[TestRail] section_ids가 없습니다.")
        return {}

    # 각 섹션별로 케이스 가져오기 및 Type 필터링
    filtered_case_ids_by_section = {}  # {section_id: [case_ids]}
    allowed_type_id = get_case_type_ids(filter_name)  # TestRail API에서 name→id 변환
    print(f"[TestRail] filter_name: {filter_name}, type_id: {allowed_type_id}")
    
    for section_id in section_ids:
        cases_data = testrail_api(f"get_cases/{project_id}", params={"section_id": section_id})
        if not cases_data:
            continue
        
        # cases가 dict로 래핑된 경우 처리
        cases = cases_data.get("cases", []) if isinstance(cases_data, dict) else cases_data

        section_case_ids = []
        for case in cases:
            # filter_name이 있으면 Type 필터링
            if allowed_type_id is not None:
                case_type_id = case.get("type_id")
                if case_type_id == allowed_type_id:
                    section_case_ids.append(case.get("id"))
            else:
                section_case_ids.append(case.get("id"))
        
        if section_case_ids:
            filtered_case_ids_by_section[section_id] = section_case_ids
            print(f"[TestRail] 섹션 {section_id}: {section_case_ids} 케이스 선택됨")

    return filtered_case_ids_by_section

def create_testrail_run(case_ids, config):
    """필터링된 케이스로 TestRail에 테스트 런 생성"""
    global testrail_run_id
    
    project_id = config["project_id"]
    payload = {
        "suite_id": config["suite_id"],
        "name": f"Automated Test Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "include_all": False,
        "case_ids": case_ids
    }
    
    run_data = testrail_api(f"add_run/{project_id}", method="POST", payload=payload)
    if run_data:
        # print(f"[DEBUG] run_data: {run_data}")
        testrail_run_id = run_data.get("id")
        print(f"[TestRail] Test Run 생성 완료: Run ID {testrail_run_id} (케이스 {len(case_ids)}개)")
        return testrail_run_id
    
    return None

def create_test_runs(config):
    """가져온 설정으로 Test Run 생성 - 섹션별 케이스 리스트 관리"""
    global suite_case_ids, testrail_run_ids, case_id_to_section_id, suite_case_ids_by_section, suite_test_index
    try:
        # 1. Test Case IDs 가져오기 (Refactored logic)
        filtered_case_ids = get_filtered_case_ids(config)
        
        # 2. Run 생성 및 섹션별 케이스 리스트 초기화
        testrail_run_ids = {}
        case_id_to_section_id = {}
        suite_case_ids_by_section = {}  # 초기화
        suite_test_index = {}  # 초기화
        all_case_ids = []
        
        for section_id, case_ids in filtered_case_ids.items():
            # 각 섹션별로 Run 생성
            run_id = create_testrail_run(case_ids, config)
            if run_id:
                testrail_run_ids[section_id] = run_id
                print(f"[TestRail] 섹션 {section_id}에 대한 Run 생성 완료: Run ID {run_id}")
                all_case_ids.extend(case_ids)
                
                for case_id in case_ids:
                    case_id_to_section_id[case_id] = section_id
                
                # suite_name으로 케이스 리스트 매핑 (섹션별 인덱스 관리용)
                suite_name = section_id_to_suite_name.get(section_id)
                if suite_name:
                    suite_case_ids_by_section[suite_name] = case_ids
                    suite_test_index[suite_name] = 0  # 인덱스 초기화
                    print(f"[TestRail] suite '{suite_name}' 케이스: {case_ids}")
        
        suite_case_ids = all_case_ids
        print(f"[TestRail] 전체 필터링된 케이스 {len(suite_case_ids)}개: {suite_case_ids}")
        return suite_case_ids
    except Exception as e:
        print(f"[TestRail Error] Test Run 생성 실패: {e}")
        return []


def link_runs_to_milestone():
    """생성된 Test Run들을 Milestone에 연결

    사용 예:
        pytest_sessionstart()에서 create_test_runs() 이후에 호출
        또는 테스트 완료 후 pytest_sessionfinish()에서 호출
    """
    global milestone_id, testrail_run_ids
    
    if not milestone_id:
        print("[TestRail] Milestone ID가 없어서 Run 연결을 건너뜁니다.")
        return False
    
    if not testrail_run_ids:
        print("[TestRail] 연결할 Test Run이 없습니다.")
        return False
    
    success_count = 0
    for section_id, run_id in testrail_run_ids.items():
        result = testrail_api(
            f"update_run/{run_id}",
            method="POST",
            payload={"milestone_id": milestone_id}
        )
        if result:
            print(f"[TestRail] Run {run_id} → Milestone {milestone_id} 연결 완료")
            success_count += 1
        else:
            print(f"[TestRail Error] Run {run_id} → Milestone 연결 실패")
    
    print(f"[TestRail] 총 {success_count}/{len(testrail_run_ids)}개 Run이 Milestone에 연결됨")
    return success_count == len(testrail_run_ids)

def send_result_to_testrail(test_case_id, status, comment="", duration=0):
    """TestRail에 테스트 결과 전송"""
    global testrail_run_id, testrail_run_ids, case_id_to_section_id
    
    # test_case_id가 속한 섹션 ID 찾기
    section_id = case_id_to_section_id.get(test_case_id)
    
    # 섹션 ID로 Run ID 찾기
    run_id = None
    if section_id and section_id in testrail_run_ids:
        run_id = testrail_run_ids[section_id]
        print(f"[TestRail] Test case {test_case_id} → 섹션 {section_id} → Run {run_id}")
    else:
        # 매핑 정보가 없으면 첫 번째 Run 사용 (fallback)
        if testrail_run_ids:
            run_id = next(iter(testrail_run_ids.values()))
            print(f"[Warning] Test case {test_case_id}의 섹션 매핑을 찾을 수 없어 첫 번째 Run 사용: {run_id}")
        elif testrail_run_id:
            run_id = testrail_run_id
            print(f"[Warning] Test case {test_case_id}의 섹션 매핑을 찾을 수 없어 마지막 Run 사용: {run_id}")
    
    if not run_id:
        print(f"[TestRail Error] Run ID가 없어 결과를 전송할 수 없습니다. (Test Case: {test_case_id})")
        return
    
    # status_id: 1=Passed, 2=Blocked, 3=Untested, 4=Retest, 5=Failed
    status_map = {
        "passed": 1,
        "failed": 5,
        "skipped": 2,
        "blocked": 2
    }
    status_id = status_map.get(status, 3)
    
    payload = {
        "status_id": status_id,
        "comment": comment[:255] if comment else "",  # TestRail comment 길이 제한
        "elapsed": f"{int(duration)}s" if duration else None
    }
    
    result = testrail_api(f"add_result_for_case/{run_id}/{test_case_id}", method="POST", payload=payload)
    if result:
        print(f"[TestRail] Test case {test_case_id}: {status} 저장 완료")
    else:
        print(f"[TestRail Error] Test case {test_case_id} 결과 전송 실패")

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """각 테스트의 결과를 수집 - 섹션별 인덱스 기반 매핑"""
    global test_case_mapping, suite_test_index
    outcome = yield
    rep = outcome.get_result()
    
    # 테스트 결과 정보 수집
    if rep.when == "call":  # 테스트 실행 단계만 수집
        test_result = {
            "test_name": item.nodeid,
            "status": rep.outcome,  # passed, failed, skipped
            "duration": round(rep.duration, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": str(rep.longrepr) if rep.failed else ""
        }
        test_results.append(test_result)
        
        # 테스트의 suite 마커에서 suite 이름 가져오기
        suite_marker = item.get_closest_marker("suite")
        suite_name = suite_marker.args[0] if suite_marker and suite_marker.args else None

        case_id = None
        if suite_name and suite_name in suite_case_ids_by_section:
            # 해당 섹션의 케이스 리스트
            section_case_ids = suite_case_ids_by_section[suite_name]
            # 해당 섹션의 현재 인덱스
            current_index = suite_test_index.get(suite_name, 0)
            
            if current_index < len(section_case_ids):
                case_id = section_case_ids[current_index]
                print(f"[DEBUG makereport] 매핑된 case_id: {case_id}")
                # 인덱스 증가
                suite_test_index[suite_name] = current_index + 1
        
        if case_id:
            test_case_mapping[item.nodeid] = case_id
            # TestRail에 결과 전송
            send_result_to_testrail(
                case_id, 
                rep.outcome, 
                test_result["error_message"],
                rep.duration
            )
            print(f"[DEBUG makereport] send_result_to_testrail 호출 완료")
        else:
            print(f"[Warning] 테스트 {item.nodeid}에 매핑할 케이스가 없습니다. (suite: {suite_name})")

def pytest_sessionstart(session):
    """테스트 세션 시작 시 Milestone 생성 및 TestRail Run 생성"""
    global testrail_run_id, suite_case_ids
    print("\n[Session Start] TestRail 설정 중...")
    
    # 1. 필요한 설정값 가져오기
    config = get_testrail_config()
    
    # 2. Milestone 생성/확인
    create_milestone(config)
    
    # 3. Test Run 생성
    create_test_runs(config)

    # 4. Test Run 연결
    link_runs_to_milestone()

def get_sheet():
    """구글 시트 연결 함수"""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scopes,
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet

def pytest_sessionfinish(session, exitstatus):
    """모든 테스트 완료 후 결과를 Google Sheets에 저장"""
    if test_results:
        print(f"\n[Session Finish] 총 {len(test_results)}개 테스트 실행 완료")
        print(f"  - Passed: {sum(1 for r in test_results if r['status'] == 'passed')}")
        print(f"  - Failed: {sum(1 for r in test_results if r['status'] == 'failed')}")
        print(f"  - Skipped: {sum(1 for r in test_results if r['status'] == 'skipped')}")
        save_results_to_google_sheets(test_results)
        if testrail_run_id:
            print(f"[TestRail] Run ID {testrail_run_id}에 결과 저장 완료")
    else:
        print("\n[Session Finish] 실행된 테스트가 없습니다.")

def save_results_to_google_sheets(results):
    """구글 시트에 테스트 결과 저장 (덮어쓰기)"""
    try:
        sheet = get_sheet()
        
        # 헤더 정의
        header = ["Test Name", "Status", "Duration (s)", "Timestamp", "Error Message"]
        sheet.clear()  # 기존 내용 지우기 (덮어쓰기)
        sheet.append_row(header)
        
        # 테스트 결과를 한 줄씩 추가
        for result in results:
            row = [
                result.get("test_name", ""),
                result.get("status", ""),
                result.get("duration", ""),
                result.get("timestamp", ""),
                result.get("error_message", "")
            ]
            sheet.append_row(row)
        
        print(f"[Google Sheets] {len(results)}개 테스트 결과 저장 완료")
    except Exception as e:
        print(f"[Google Sheets Error] {e}")

def testrail_api(endpoint, method="GET", params=None, payload=None):
    """TestRail API 공통 호출 함수
    
    Args:
        endpoint: API 엔드포인트 (예: "get_milestones/3", "add_run/3")
        method: "GET" 또는 "POST"
        params: GET 쿼리 파라미터 (dict)
        payload: POST body (dict)
    
    Returns:
        dict: API 응답 (성공 시) 또는 None (실패 시)
    """
    try:
        url = f"{TESTRAIL_URL}/index.php?/api/v2/{endpoint}"
        
        if method.upper() == "POST":
            response = requests.post(
                url,
                json=payload,
                auth=(TESTRAIL_USER, TESTRAIL_API_KEY),
                headers={"Content-Type": "application/json"}
            )
        else:
            response = requests.get(
                url,
                params=params,
                auth=(TESTRAIL_USER, TESTRAIL_API_KEY)
            )
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[TestRail Error] API 호출 실패 ({method} {endpoint}): {e}")
        return None

