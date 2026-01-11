"""TestRail API 클라이언트 모듈

TestRail API 호출 관련 함수들을 모아둔 모듈입니다.
"""
import requests
from datetime import datetime
import testrail_config
import data

# ===== 설정값 =====
TESTRAIL_URL = data.TRAIL_URL
TESTRAIL_USER = data.TRAIL_USER
TESTRAIL_API_KEY = data.TRAIL_API

# 전역 상태 변수
testrail_run_id = None  # 현재 사용 중인 Run ID (마지막으로 생성된 Run)
testrail_run_ids = {}  # 섹션별 Run ID 매핑 {section_id: run_id}
case_id_to_section_id = {}  # 케이스 ID와 섹션 ID 매핑 {case_id: section_id}
milestone_id = None
suite_case_ids = []  # 전체 케이스 ID 리스트
suite_case_ids_by_section = {}  # {suite_name: [case_ids]}
suite_test_index = {}  # {suite_name: 현재 인덱스}
section_id_to_suite_name = {}  # {section_id: suite_name}


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


def get_testrail_config(selected_suite_names):
    """설정 파일에서 필요한 값 가져오기
    
    Args:
        selected_suite_names: 선택된 suite 이름 리스트
    
    Returns:
        dict: 설정 값 딕셔너리
    """
    global section_id_to_suite_name
    
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
    """milestone_name으로 기존 마일스톤 검색, 없으면 생성"""
    global milestone_id
    
    milestone_name = config.get("milestone_name", "").strip()
    project_id = config.get("project_id")
    
    if not milestone_name:
        print("[TestRail] milestone_name이 비어있어서 Milestone 생성을 건너뜁니다.")
        return None
    
    # 1. TestRail API로 마일스톤 목록 조회
    milestones_data = testrail_api(f"get_milestones/{project_id}")
    if milestones_data:
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
    """TestRail API에서 filter_name과 일치하는 Case Type의 id 반환"""
    if not filter_name:
        return None
    
    case_types = testrail_api("get_case_types")
    if case_types:
        filter_name_lower = filter_name.lower()
        for case_type in case_types:
            if case_type.get("name", "").lower() == filter_name_lower:
                return case_type.get("id")
        
        print(f"[Warning] '{filter_name}'에 해당하는 Case Type을 찾을 수 없습니다.")
    return None


def get_filtered_case_ids(config):
    """설정에 맞는 Test Case IDs 반환"""
    project_id = config["project_id"]
    section_ids = config.get("section_ids", [])
    filter_name = config.get("filter_name", "")

    if not section_ids:
        print("[TestRail] section_ids가 없습니다.")
        return {}

    filtered_case_ids_by_section = {}
    allowed_type_id = get_case_type_ids(filter_name)
    print(f"[TestRail] filter_name: {filter_name}, type_id: {allowed_type_id}")
    
    for section_id in section_ids:
        cases_data = testrail_api(f"get_cases/{project_id}", params={"section_id": section_id})
        if not cases_data:
            continue
        
        cases = cases_data.get("cases", []) if isinstance(cases_data, dict) else cases_data

        section_case_ids = []
        for case in cases:
            if allowed_type_id is not None:
                if case.get("type_id") == allowed_type_id:
                    section_case_ids.append(case.get("id"))
            else:
                section_case_ids.append(case.get("id"))
        
        if section_case_ids:
            filtered_case_ids_by_section[section_id] = section_case_ids
            print(f"[TestRail] 섹션 {section_id}: {section_case_ids} 케이스 선택됨")

    return filtered_case_ids_by_section


def create_test_run(case_ids, config, section_name=None):
    """필터링된 케이스로 TestRail에 테스트 런 생성"""
    global testrail_run_id
    
    project_id = config["project_id"]
    
    if section_name:
        run_name = f"{section_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        run_name = f"Automated Test Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    payload = {
        "suite_id": config["suite_id"],
        "name": run_name,
        "include_all": False,
        "case_ids": case_ids
    }
    
    run_data = testrail_api(f"add_run/{project_id}", method="POST", payload=payload)
    if run_data:
        testrail_run_id = run_data.get("id")
        print(f"[TestRail] Test Run 생성 완료: '{run_name}' (Run ID {testrail_run_id}, 케이스 {len(case_ids)}개)")
        return testrail_run_id
    
    return None


def create_test_runs(config):
    """가져온 설정으로 Test Run 생성 - 섹션별 케이스 리스트 관리"""
    global suite_case_ids, testrail_run_ids, case_id_to_section_id, suite_case_ids_by_section, suite_test_index
    
    try:
        filtered_case_ids = get_filtered_case_ids(config)
        
        testrail_run_ids = {}
        case_id_to_section_id = {}
        suite_case_ids_by_section = {}
        suite_test_index = {}
        all_case_ids = []
        
        for section_id, case_ids in filtered_case_ids.items():
            section_name = section_id_to_suite_name.get(section_id)
            run_id = create_test_run(case_ids, config, section_name)
            if run_id:
                testrail_run_ids[section_id] = run_id
                all_case_ids.extend(case_ids)
                
                for case_id in case_ids:
                    case_id_to_section_id[case_id] = section_id
                
                suite_name = section_id_to_suite_name.get(section_id)
                if suite_name:
                    suite_case_ids_by_section[suite_name] = case_ids
                    suite_test_index[suite_name] = 0
                    print(f"[TestRail] suite '{suite_name}' 케이스: {case_ids}")
        
        suite_case_ids = all_case_ids
        print(f"[TestRail] 전체 필터링된 케이스 {len(suite_case_ids)}개: {suite_case_ids}")
        return suite_case_ids
    except Exception as e:
        print(f"[TestRail Error] Test Run 생성 실패: {e}")
        return []


def link_runs_to_milestone():
    """생성된 Test Run들을 Milestone에 연결"""
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
    
    section_id = case_id_to_section_id.get(test_case_id)
    
    run_id = None
    if section_id and section_id in testrail_run_ids:
        run_id = testrail_run_ids[section_id]
        print(f"[TestRail] Test case {test_case_id} → 섹션 {section_id} → Run {run_id}")
    else:
        if testrail_run_ids:
            run_id = next(iter(testrail_run_ids.values()))
            print(f"[Warning] Test case {test_case_id}의 섹션 매핑을 찾을 수 없어 첫 번째 Run 사용: {run_id}")
        elif testrail_run_id:
            run_id = testrail_run_id
            print(f"[Warning] Test case {test_case_id}의 섹션 매핑을 찾을 수 없어 마지막 Run 사용: {run_id}")
    
    if not run_id:
        print(f"[TestRail Error] Run ID가 없어 결과를 전송할 수 없습니다. (Test Case: {test_case_id})")
        return
    
    status_map = {
        "passed": 1,
        "failed": 5,
        "skipped": 2,
        "blocked": 2
    }
    status_id = status_map.get(status, 3)
    
    payload = {
        "status_id": status_id,
        "comment": comment[:255] if comment else "",
        "elapsed": f"{int(duration)}s" if duration else None
    }
    
    result = testrail_api(f"add_result_for_case/{run_id}/{test_case_id}", method="POST", payload=payload)
    if result:
        print(f"[TestRail] Test case {test_case_id}: {status} 저장 완료")
    else:
        print(f"[TestRail Error] Test case {test_case_id} 결과 전송 실패")


def get_case_id_for_test(suite_name):
    """테스트에 해당하는 case_id 반환 (인덱스 기반)"""
    global suite_case_ids_by_section, suite_test_index
    
    if suite_name and suite_name in suite_case_ids_by_section:
        section_case_ids = suite_case_ids_by_section[suite_name]
        current_index = suite_test_index.get(suite_name, 0)
        
        if current_index < len(section_case_ids):
            case_id = section_case_ids[current_index]
            suite_test_index[suite_name] = current_index + 1
            return case_id
    
    return None
