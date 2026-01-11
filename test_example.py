import pytest
import time

'''
TestRail 케이스는 conftest.py에서 섹션별 인덱스 기반으로 자동 매핑
- 테스트의 @pytest.mark.suite("이름")을 기준으로 해당 섹션의 케이스 리스트에서 순서대로 매핑

Suite 마커 사용법:
- @pytest.mark.suite("Suite이름")으로 테스트에 Suite 지정
- pytest --suite=Prerequisites 로 특정 Suite만 실행
'''


@pytest.mark.suite("Prerequisites")
def test_cypress_scenario_1():
    """통과하는 테스트 예제"""
    time.sleep(2)  # 테스트 실행 시간 시뮬레이션
    assert 1 + 1 == 2


@pytest.mark.suite("Prerequisites")
def test_pytest_scenario_2():
    """실패하는 테스트 예제"""
    time.sleep(2)
    assert 1 + 1 == 3, "의도적인 실패 테스트"


@pytest.mark.suite("Installation")
def test_pytest_scenario_3():
    """통과하는 테스트 예제"""
    time.sleep(2)        
    assert "hello" == "hello"


@pytest.mark.suite("Updates")
def test_pytest_scenario_4():
    """통과하는 테스트 예제"""
    time.sleep(2)
    assert "hello" == "hello"


@pytest.mark.suite("Feature2")
def test_pytest_scenario_5():
    """통과하는 테스트 예제"""
    time.sleep(3)
    assert "hello" == "hello"


@pytest.mark.suite("Search")
def test_pytest_scenario_6():
    """통과하는 테스트 예제"""
    time.sleep(2)
    assert "hello" == "hello"

