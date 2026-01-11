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
