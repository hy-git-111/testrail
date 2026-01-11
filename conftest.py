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
suite_case_ids = []  # Suite의 케이스 ID 리스트 (순서대로)
test_case_mapping = {}  # 테스트 실행 순서와 Case ID 매핑


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


def get_testrail_config():
    """Milestone과 Test Run 생성에 필요한 설정값 가져오기 및 검증"""
    testrun_config = testrail_config.get_testrun_config()
    milestone_config = testrail_config.get_milestone_config()
    filter_config = testrail_config.get_filter_config()

    config = {
        "project_id": testrun_config.get("project_id"),
        "suite_id": testrun_config.get("suite_id"),
        # "assignedto_id": testrun_config.get("assignedto_id"),
        "description": testrun_config.get("description", "Automated test execution"),
        "milestone_name": milestone_config.get("name"),
        "filter_name": filter_config.get("type"),
        "section_ids": filter_config.get("section_ids")
    }
    
    print(f"[TestRail] 설정 로드 완료: project_id={config['project_id']}, suite_id={config['suite_id']}, milestone_name={config['milestone_name']}")
    return config


def create_milestone(config):
    """가져온 설정으로 Milestone 생성 또는 기존 Milestone 가져오기"""
    global milestone_id
    try:
        project_id = config["project_id"]
        milestone_name = config["milestone_name"]
        
        # 기존 Milestone 확인
        url = f"{TESTRAIL_URL}/index.php?/api/v2/get_milestones/{project_id}"
        response = requests.get(url, auth=(TESTRAIL_USER, TESTRAIL_API_KEY))
        response.raise_for_status()
        milestones = response.json()
        
        # milestones가 dict로 래핑된 경우 처리
        if isinstance(milestones, dict):
            milestones = milestones.get("milestones", [])
        elif not isinstance(milestones, list):
            print(f"[Warning] Milestones 응답 형식이 예상과 다릅니다: {type(milestones)}")
            milestones = []
        
        # 같은 이름의 Milestone 찾기
        for milestone in milestones:
            if milestone.get("name") == milestone_name:
                milestone_id = milestone.get("id")
                print(f"[TestRail] 기존 Milestone 발견: {milestone_name} (ID: {milestone_id})")
                return milestone_id
        
        # Milestone이 없으면 생성
        url = f"{TESTRAIL_URL}/index.php?/api/v2/add_milestone/{project_id}"
        payload = {
            "name": milestone_name
        }
        response = requests.post(
            url,
            json=payload,
            auth=(TESTRAIL_USER, TESTRAIL_API_KEY),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        milestone_data = response.json()
        milestone_id = milestone_data.get("id")
        print(f"[TestRail] Milestone 생성 완료: {milestone_name} (ID: {milestone_id})")
        return milestone_id
    except Exception as e:
        print(f"[TestRail Error] Milestone 생성/확인 실패: {e}")
        return None


def get_sections(project_id, suite_id):
    """Suite의 모든 섹션(폴더) 목록 가져오기"""
    try:
        url = f"{TESTRAIL_URL}/index.php?/api/v2/get_sections/{project_id}"
        params = {
            "suite_id": suite_id
        }
        response = requests.get(url, params=params, auth=(TESTRAIL_USER, TESTRAIL_API_KEY))
        response.raise_for_status()
        sections = response.json()
        
        # sections가 dict로 래핑된 경우 처리
        if isinstance(sections, dict):
            sections = sections.get("sections", [])
        elif not isinstance(sections, list):
            print(f"[Warning] Sections 응답 형식이 예상과 다릅니다: {type(sections)}")
            sections = []
        
        print(f"[TestRail] 섹션 {len(sections)}개 발견")
        print(f"[TestRail] 섹션 목록: {sections}")
        return sections
    except Exception as e:
        print(f"[TestRail Error] 섹션 가져오기 실패: {e}")
        return []


def get_case_type_ids(filter_name):
    """TestRail의 Case Type 목록에서 filter_name과 일치하는 type_id 리스트 반환"""
    try:
        url = f"{TESTRAIL_URL}/index.php?/api/v2/get_case_types"
        response = requests.get(url, auth=(TESTRAIL_USER, TESTRAIL_API_KEY))
        response.raise_for_status()
        case_types = response.json()
        
        # case_types가 dict로 래핑된 경우 처리
        if isinstance(case_types, dict):
            case_types = case_types.get("case_types", [])
        elif not isinstance(case_types, list):
            print(f"[Warning] Case Types 응답 형식이 예상과 다릅니다: {type(case_types)}")
            case_types = []

        # filter_name과 일치하는 type_id 찾기
        filtered_ids = []
        filter_name_lower = filter_name.lower() if filter_name else ""
        
        for case_type in case_types:
            type_name = case_type.get("name", "").lower()
            type_id = case_type.get("id")
            
            # type name에 filter_name이 포함되면 id 추가
            if type_id and filter_name_lower in type_name:
                filtered_ids.append(type_id)
        
        print(f'[DEBUG] filter_name="{filter_name}"에 해당하는 type_ids: {filtered_ids}')    
        return filtered_ids
        
    except Exception as e:
        print(f"[TestRail Error] Case Type 가져오기 실패: {e}")
        return []


def create_test_runs(config):
    """가져온 설정으로 Test Run 생성"""
    global suite_case_ids, testrail_run_ids, case_id_to_section_id
    try:
        project_id = config["project_id"]
        suite_id = config["suite_id"]
        filter_name = config["filter_name"]
        section_ids = config["section_ids"]
        
        # 1. 섹션(폴더) ID 찾기
        all_sections = get_sections(project_id, suite_id)
        # all_section_ids = [s["id"] for s in all_sections]
        # print(all_section_ids)

        # section_ids가 지정된 경우 해당 섹션과 하위 섹션 필터링
        target_section_ids = []
        if section_ids:
            # 지정된 section_ids에 해당하는 섹션과 그 하위 섹션 찾기
            for section in all_sections:
                section_id = section.get("id")
                parent_id = section.get("parent_id")
                
                # 직접 지정된 섹션이거나, 지정된 섹션의 하위 섹션인 경우
                if section_id in section_ids:
                    target_section_ids.append(section_id)
                    print(f"[TestRail] 대상 섹션 발견: {section.get('name')} (ID: {section_id})")
                elif parent_id and parent_id in section_ids:
                    target_section_ids.append(section_id)
                    print(f"[TestRail] 하위 섹션 포함: {section.get('name')} (ID: {section_id}, 부모: {parent_id})")
            print(f"[TestRail] 대상 섹션: {target_section_ids}")
        else:
            # section_ids가 없으면 모든 섹션 사용
            target_section_ids = [section.get("id") for section in all_sections]
            print(f"[TestRail] 모든 섹션 사용: {len(target_section_ids)}개")
        
        if not target_section_ids:
            print("[TestRail] 대상 섹션이 없습니다.")
            return []


        # 2. 각 섹션별로 케이스 가져오기, Type 필터링, Run 생성
        testrail_run_ids = {}  # 섹션 ID와 Run ID 매핑
        case_id_to_section_id = {}  # 케이스 ID와 섹션 ID 매핑
        all_case_ids = []  # 모든 섹션의 케이스 ID (테스트 매핑용)
        
        for section_id in target_section_ids:
            # 2-1. 섹션의 케이스 목록 가져오기
            url = f"{TESTRAIL_URL}/index.php?/api/v2/get_cases/{project_id}"
            params = {
                "suite_id": suite_id,
                "section_id": section_id
            }
            print(f"[DEBUG] 섹션 {section_id}의 케이스 가져오기 중...")
            response = requests.get(url, params=params, auth=(TESTRAIL_USER, TESTRAIL_API_KEY))
            response.raise_for_status()
            cases = response.json()
            print(f"[DEBUG] 섹션 {section_id}에서 {len(cases)}개 케이스 발견")
            print(f"[DEBUG] 케이스: {cases}")

            # 2-2. Type 필터링
            allowed_type_ids = get_case_type_ids(filter_name)
            filtered_cases = []
            for case in cases:
                # Case의 type_id가 허용된 type_ids에 있는지 확인
                case_type_id = case.get("type_id")
                if case_type_id in allowed_type_ids:
                    filtered_cases.append(case)
                    print(f"[DEBUG] 케이스 {case.get('id')} 필터링 통과: type_id={case_type_id}")
            
            # 2-3. Case ID 배열 만들기
            case_ids = [case.get("id") for case in filtered_cases]
            print(f"[TestRail] 섹션 {section_id} 필터링된 케이스 {len(case_ids)}개: {case_ids}")
            
            # 2-4. 각 섹션별로 Run 생성
            if case_ids:
                run_id = create_testrail_run(case_ids, config)
                if run_id:
                    testrail_run_ids[section_id] = run_id
                    print(f"[TestRail] 섹션 {section_id}에 대한 Run 생성 완료: Run ID {run_id}")
                    all_case_ids.extend(case_ids)  # 테스트 매핑용으로 모든 케이스 ID 저장
                    # 케이스 ID와 섹션 ID 매핑 저장
                    for case_id in case_ids:
                        case_id_to_section_id[case_id] = section_id
            else:
                print(f"[TestRail] 섹션 {section_id}에 필터링된 케이스가 없어 Run을 생성하지 않습니다.")
        
        # 모든 섹션의 케이스 ID를 suite_case_ids에 저장 (테스트 매핑용)
        suite_case_ids = all_case_ids
        print(f"[TestRail] 전체 필터링된 케이스 {len(suite_case_ids)}개: {suite_case_ids}")
        print(f"[TestRail] 생성된 Run 개수: {len(testrail_run_ids)}개 (섹션별)")
        return suite_case_ids
    except Exception as e:
        print(f"[TestRail Error] Test Run 생성 실패: {e}")
        return []


def create_testrail_run(case_ids, config):
    """필터링된 케이스로 TestRail에 테스트 런 생성"""
    global testrail_run_id
    try:
        project_id = config["project_id"]
        suite_id = config["suite_id"]
        
        # if not case_ids:
        #     print("[TestRail] 필터링된 케이스가 없습니다.")
        #     return None

        url = f"{TESTRAIL_URL}/index.php?/api/v2/add_run/{project_id}"
        payload = {
            "suite_id": suite_id,
            "name": f"Automated Test Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            # "description": config.get("description", "Automated test execution"),
            # "assignedto_id": config.get("assignedto_id"),
            "include_all": False,
            "case_ids": case_ids
        }
        
        if milestone_id:
            payload["milestone_id"] = milestone_id
        print(f"[DEBUG] payload: {payload["milestone_id"]}")
        response = requests.post(
            url,
            json=payload,
            auth=(TESTRAIL_USER, TESTRAIL_API_KEY),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        run_data = response.json()
        print(f"[DEBUG] run_data: {run_data}")
        testrail_run_id = run_data.get("id")
        print(f"[TestRail] Test Run 생성 완료: Run ID {testrail_run_id} (케이스 {len(case_ids)}개)")
        return testrail_run_id
    except Exception as e:
        print(f"[TestRail Error] Run 생성 실패: {e}")
        return None


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
    
    try:
        url = f"{TESTRAIL_URL}/index.php?/api/v2/add_result_for_case/{run_id}/{test_case_id}"
        
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
        
        response = requests.post(
            url,
            json=payload,
            auth=(TESTRAIL_USER, TESTRAIL_API_KEY),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        print(f"[TestRail] Test case {test_case_id}: {status} 저장 완료")
    except Exception as e:
        print(f"[TestRail Error] Test case {test_case_id} 결과 전송 실패: {e}")


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


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """각 테스트의 결과를 수집"""
    global test_case_mapping
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
        
        # Suite 케이스 순서대로 매핑
        test_index = len(test_results) - 1  # 현재 테스트의 인덱스
        if test_index < len(suite_case_ids):
            case_id = suite_case_ids[test_index]
            test_case_mapping[item.nodeid] = case_id
            # TestRail에 결과 전송
            send_result_to_testrail(
                case_id, 
                rep.outcome, 
                test_result["error_message"],
                rep.duration
            )
        else:
            print(f"[Warning] 테스트 {item.nodeid}에 매핑할 케이스가 없습니다. (케이스 개수: {len(suite_case_ids)})")


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

