"""testrail.cfg 파일에서 설정을 읽는 유틸리티 모듈"""
import configparser
import os

_config = None


def load_config():
    """testrail.cfg 파일에서 설정 로드 (캐싱)"""
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), "testrail.cfg")
        if os.path.exists(config_path):
            _config.read(config_path, encoding="utf-8")
    return _config


def get_testrun_config():
    """TESTRUN 섹션의 설정 반환"""
    config = load_config()
    if "TESTRUN" in config:
        return {
            "project_id": config.getint("TESTRUN", "project_id", fallback=None),
            "suite_id": config.getint("TESTRUN", "suite_id", fallback=None),
            "assignedto_id": config.getint("TESTRUN", "assignedto_id", fallback=None),
            "description": config.get("TESTRUN", "description", fallback="")
        }
    return {}


def get_api_config():
    """API 섹션의 설정 반환"""
    config = load_config()
    if "API" in config:
        return {
            "url": config.get("API", "url", fallback=""),
            "email": config.get("API", "email", fallback=""),
            "password": config.get("API", "password", fallback="")
        }
    return {}


# 편의를 위한 함수
def get_suite_id():
    """Suite ID 반환"""
    return get_testrun_config().get("suite_id")


def get_project_id():
    """Project ID 반환"""
    return get_testrun_config().get("project_id")


def get_milestone_config():
    """MILESTONE 섹션의 설정 반환"""
    config = load_config()
    if "MILESTONE" in config:
        return {
            "name": config.get("MILESTONE", "name", fallback="")
        }
    return {}


def get_filter_config():
    """FILTER 섹션의 설정 반환"""
    config = load_config()
    if "FILTER" in config:
        section_ids_str = config.get("FILTER", "section_ids", fallback="")
        section_ids = []
        
        # 쉼표로 구분된 section_ids 파싱
        if section_ids_str:
            for id_str in section_ids_str.split(","):
                id_str = id_str.strip()
                if id_str:
                    try:
                        section_ids.append(int(id_str))
                    except ValueError:
                        print(f"[Warning] 잘못된 section_id 형식: {id_str}")
        
        return {
            "type": config.get("FILTER", "type", fallback=""),
            "section_ids": section_ids if section_ids else None
        }
    return {}


def get_google_sheets_config():
    """GOOGLE_SHEETS 섹션의 설정 반환"""
    config = load_config()
    if "GOOGLE_SHEETS" in config:
        return {
            "spreadsheet_id": config.get("GOOGLE_SHEETS", "spreadsheet_id", fallback="")
        }
    return {}

