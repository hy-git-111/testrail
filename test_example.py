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
    try:
        """통과하는 테스트 예제"""
        time.sleep(2)  # 테스트 실행 시간 시뮬레이션
        assert 1 + 1 == 2

    except Exception as e:
        print(e)


@pytest.mark.suite("Prerequisites")
def test_pytest_scenario_2():
    try:
        """실패하는 테스트 예제"""
        time.sleep(2)
        assert 1 + 1 == 3, "의도적인 실패 테스트"

    except Exception as e:
        print(e)


@pytest.mark.suite("Installation")
def test_pytest_scenario_3():
    try:
        """또 다른 테스트 예제"""
        time.sleep(2)        
        assert "hello" == "hello"
        
    except Exception as e:
        print(e)


@pytest.mark.suite("Updates")
def test_pytest_scenario_4():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        time.sleep(2)
        
    except Exception as e:
        print(e)


@pytest.mark.suite("Updates")
def test_pytest_scenario_5():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        time.sleep(2)
        
    except Exception as e:
        print(e)


@pytest.mark.suite("Tutorial")
def test_pytest_scenario_6():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        time.sleep(2)
        
    except Exception as e:
        print(e)

