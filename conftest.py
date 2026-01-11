"""Pytest conftest.py

Pytest hook 함수들만 포함합니다.
"""
import pytest
from datetime import datetime

# 분리된 모듈 import
import testrail_client
import google_sheets

# 테스트 결과 저장용 리스트
test_results = []
selected_suite_names = []  # 커맨드라인에서 선택된 suite 이름들
test_case_mapping = {}  # 테스트 실행 순서와 Case ID 매핑


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


def pytest_sessionstart(session):
    """테스트 세션 시작 시 Milestone 생성 및 TestRail Run 생성"""
    global selected_suite_names
    print("\n[Session Start] TestRail 설정 중...")
    
    # 1. 필요한 설정값 가져오기
    config = testrail_client.get_testrail_config(selected_suite_names)
    
    # 2. Milestone 생성/확인
    testrail_client.create_milestone(config)
    
    # 3. Test Run 생성
    testrail_client.create_test_runs(config)

    # 4. Test Run 연결
    testrail_client.link_runs_to_milestone()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """각 테스트의 결과를 수집 - 섹션별 인덱스 기반 매핑"""
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
        
        # 테스트의 suite 마커에서 suite 이름 가져오기
        suite_marker = item.get_closest_marker("suite")
        suite_name = suite_marker.args[0] if suite_marker and suite_marker.args else None

        # testrail_client 모듈에서 case_id 가져오기
        case_id = testrail_client.get_case_id_for_test(suite_name)
        
        if case_id:
            print(f"[DEBUG makereport] 매핑된 case_id: {case_id}")
            test_case_mapping[item.nodeid] = case_id
            # TestRail에 결과 전송
            testrail_client.send_result_to_testrail(
                case_id, 
                rep.outcome, 
                test_result["error_message"],
                rep.duration
            )
            print(f"[DEBUG makereport] send_result_to_testrail 호출 완료")
        else:
            print(f"[Warning] 테스트 {item.nodeid}에 매핑할 케이스가 없습니다. (suite: {suite_name})")


def pytest_sessionfinish(session, exitstatus):
    """모든 테스트 완료 후 결과를 Google Sheets에 저장"""
    if test_results:
        print(f"\n[Session Finish] 총 {len(test_results)}개 테스트 실행 완료")
        print(f"  - Passed: {sum(1 for r in test_results if r['status'] == 'passed')}")
        print(f"  - Failed: {sum(1 for r in test_results if r['status'] == 'failed')}")
        print(f"  - Skipped: {sum(1 for r in test_results if r['status'] == 'skipped')}")
        google_sheets.save_results_to_google_sheets(test_results)
        if testrail_client.testrail_run_id:
            print(f"[TestRail] Run ID {testrail_client.testrail_run_id}에 결과 저장 완료")
    else:
        print("\n[Session Finish] 실행된 테스트가 없습니다.")
