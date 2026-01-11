"""testrail.cfg 파일에서 설정을 읽는 유틸리티 모듈"""
import configparser
import os

_config = None


def load_config():
    """testrail.cfg 파일에서 설정 로드 (캐싱)"""
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        _config.optionxform = str  # 대소문자 유지
        config_path = os.path.join(os.path.dirname(__file__), "testrail.cfg")
        if os.path.exists(config_path):
            _config.read(config_path, encoding="utf-8")
    return _config


def get_section_id_mapping(option):
    """SECTION_ID 섹션에서 이름과 section_id 매핑 반환
    
    Returns:
        dict: {이름: section_id} 형태의 딕셔너리
        예: {"Prerequisites": 30, "Installation": 33, ...}
    """
    config = load_config()
    mapping = {}
    if option in config:
        for key in config.options(option):
            try:
                mapping[key] = config.getint(option, key)
            except ValueError:
                print(f"[Warning] 잘못된 option 형식: {key}")
    return mapping


def get_section_id_by_name(name, option):
    """Section 이름으로 section_id 반환
    
    Args:
        name: Section 이름 (대소문자 구분 없음)
    
    Returns:
        int or None: section_id 또는 없으면 None
    """
    mapping = get_section_id_mapping(option)
    # 대소문자 구분 없이 검색
    name_lower = name.lower()
    for key, value in mapping.items():
        if key.lower() == name_lower:
            return value
    return None


def get_all_section_names(option="SECTION_ID"):
    """testrail.cfg의 [SECTION_ID]에서 모든 섹션 이름 반환
    
    Returns:
        list: 섹션 이름 리스트 (예: ["Prerequisites", "Installation", ...])
    """
    mapping = get_section_id_mapping(option)
    # 원래 대소문자 유지를 위해 config에서 직접 가져옴
    config = load_config()
    if option in config:
        return [key for key in config.options(option)]
    return []

