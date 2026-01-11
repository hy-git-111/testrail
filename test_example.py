import pytest
import time

'''
TestRail 케이스는 conftest.py에서 자동으로 순서대로 매핑
(@pytest.mark.testrail_case_id(케이스ID) 생략)

Suite 마커 사용법:
- @pytest.mark.suite("Suite이름")으로 테스트에 Suite 지정
- pytest --suite=Prerequisites 로 특정 Suite만 실행
- testrail.cfg의 [SUIT_ID] 섹션에서 Suite 이름과 ID 매핑 관리
'''


@pytest.mark.suite("Prerequisites")
def test_cypress_scenario_1():
    try:
        """통과하는 테스트 예제"""
        assert 1 + 1 == 2
        time.sleep(2)  # 테스트 실행 시간 시뮬레이션

    except Exception as e:
        print(e)


@pytest.mark.suite("Prerequisites")
def test_pytest_scenario_2():
    try:
        """실패하는 테스트 예제"""
        assert 1 + 1 == 3, "의도적인 실패 테스트"

    except Exception as e:
        print(e)


@pytest.mark.suite("Installation")
def test_pytest_scenario_3():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        
    except Exception as e:
        print(e)


@pytest.mark.suite("Installation")
def test_pytest_scenario_4():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        
    except Exception as e:
        print(e)


@pytest.mark.suite("Updates")
def test_pytest_scenario_5():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        
    except Exception as e:
        print(e)


@pytest.mark.suite("Tutorial")
def test_pytest_scenario_6():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        
    except Exception as e:
        print(e)

