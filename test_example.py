import pytest
import time

'''
TestRail 케이스는 conftest.py에서 자동으로 순서대로 매핑
(@pytest.mark.testrail_case_id(케이스ID) 생략)
'''

def test_cypress_scenario_1():
    try:
        """통과하는 테스트 예제"""
        assert 1 + 1 == 2
        time.sleep(2)  # 테스트 실행 시간 시뮬레이션

    except Exception as e:
        print(e)

# @pytest.mark.skip(reason="skipping this test")
def test_pytest_scenario_1():
    try:
        """실패하는 테스트 예제"""
        assert 1 + 1 == 3, "의도적인 실패 테스트"

    except Exception as e:
        print(e)

def test_pytest_scenario_2():
    try:
        """또 다른 테스트 예제"""
        assert "hello" == "hello"
        
    except Exception as e:
        print(e)

