"""Google Sheets 모듈

Google Sheets API 호출 관련 함수들을 모아둔 모듈입니다.
"""
import gspread
from google.oauth2.service_account import Credentials
import os
import data

# ===== 설정값 =====
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "gspread_account.json")
SPREADSHEET_ID = data.SPREADSHEET_ID


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


def format_duration(seconds):
    """초를 시:분:초 형식으로 변환
    
    Args:
        seconds: 초 단위 시간 (float)
    
    Returns:
        str: "HH:MM:SS" 형식 문자열
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def save_summary_sheets(milestone_name, section_stats, total_duration, total_failed):
    """구글 시트에 테스트 결과 저장
    
    Args:
        milestone_name: 마일스톤 이름
        section_stats: 섹션별 통계 딕셔너리 {section_name: {"duration": 초, "failed": 건수}}
        total_duration: 전체 수행 시간 (초)
        total_failed: 전체 fail 건수
    
    시트 형식:
        | milestone_name | section1 | section2 | ... | total    | fail건 수 |
        |----------------|----------|----------|-----|----------|----------|
        | test_v1.02     | 00:00:04 | 00:00:02 | ... | 00:00:06 | 0        |
        | test_v1.03     | 00:00:05 | 00:00:03 | ... | 00:00:08 | 1        |
    """
    try:
        sheet = get_sheet()
        section_names = list(section_stats.keys())
        
        # 현재 시트 데이터 가져오기
        all_values = sheet.get_all_values()
        
        if not all_values:
            # 시트가 비어있으면 헤더 생성
            header = ["milestone_name"] + section_names + ["total", "fail건 수"]
            sheet.append_row(header)
            all_values = [header]
        
        # 기존 헤더 확인
        existing_header = all_values[0] if all_values else []
        
        # 기존 섹션 이름들 추출 (milestone_name과 total, fail건 수 제외)
        if len(existing_header) > 3:
            existing_sections = existing_header[1:-2]
        else:
            existing_sections = []
        
        # 새로운 섹션이 있으면 헤더 업데이트
        new_sections = [s for s in section_names if s not in existing_sections]
        if new_sections:
            # 기존 섹션 + 새 섹션 (순서 유지)
            all_sections = existing_sections + new_sections
            new_header = ["milestone_name"] + all_sections + ["total", "fail건 수"]
            sheet.update('A1', [new_header])
            
            # 기존 데이터 행들도 열 확장 (새 섹션 위치에 빈 값 삽입)
            for i, row in enumerate(all_values[1:], start=2):
                if len(row) < len(new_header):
                    # total과 fail건 수 값 보존
                    total_val = row[-2] if len(row) >= 2 else ""
                    fail_val = row[-1] if len(row) >= 1 else ""
                    
                    # 섹션 값들
                    section_vals = row[1:-2] if len(row) > 3 else []
                    
                    # 새 섹션 추가 (빈 값)
                    section_vals.extend([""] * len(new_sections))
                    
                    new_row = [row[0]] + section_vals + [total_val, fail_val]
                    sheet.update(f'A{i}', [new_row])
            
            existing_sections = all_sections
        
        # milestone_name 행 찾기
        milestone_row_index = None
        for i, row in enumerate(all_values):
            if row and row[0] == milestone_name:
                milestone_row_index = i + 1  # 1-indexed
                break
        
        # 행 데이터 생성
        row_data = [milestone_name]
        for section in existing_sections:
            if section in section_stats:
                duration = section_stats[section]["duration"]
                row_data.append(format_duration(duration))
            else:
                row_data.append("")
        row_data.append(format_duration(total_duration))
        row_data.append(str(total_failed))
        
        if milestone_row_index:
            # 기존 행 업데이트
            sheet.update(f'A{milestone_row_index}', [row_data])
            print(f"[Google Sheets] milestone '{milestone_name}' 업데이트 완료")
        else:
            # 새 행 추가
            sheet.append_row(row_data)
            print(f"[Google Sheets] milestone '{milestone_name}' 추가 완료")
        
    except Exception as e:
        print(f"[Google Sheets Error] {e}")
        import traceback
        traceback.print_exc()
