import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2 import service_account
import requests

central = ZoneInfo("America/Chicago")
today_str = datetime.now(central).strftime('%Y-%m-%d')
date_display = datetime.now(central).strftime('%A, %B %d, %Y')

# Load credentials
creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = service_account.Credentials.from_service_account_info(creds_info)
client = gspread.authorize(creds)
sheet_id = os.getenv("SHEET_ID")

def get_stats(ws_name):
    try:
        if ws_name == "main":
            ws = client.open_by_key(sheet_id).sheet1          # First tab = main sheet
        else:
            ws = client.open_by_key(sheet_id).worksheet(ws_name)
        
        rows = ws.get_all_values()
        cumulative = len(rows) - 1 if len(rows) > 0 else 0
        daily = sum(1 for row in rows[1:] if len(row) > 0 and row[0] == today_str)
        
        return daily, cumulative
    except Exception as e:
        print(f"Error reading {ws_name} sheet: {e}")
        return 0, 0

# Get stats for each sheet
daily_main, cum_main = get_stats("main")
daily_cpl, cum_cpl = get_stats("CPL")
daily_dismiss, cum_dismiss = get_stats("Dismissals")
daily_revoc, cum_revoc = get_stats("Revocations")

total_today = daily_main + daily_cpl + daily_dismiss + daily_revoc
grand_cum = cum_main + cum_cpl + cum_dismiss + cum_revoc

message = f"""**{date_display} – Cumulative Extractor Report**

daily-scrape (main): {daily_main} new today, cumulative {cum_main}
cpl-scrape: {daily_cpl} new today, cumulative {cum_cpl}
dismissal-scrape: {daily_dismiss} new today, cumulative {cum_dismiss}
revocations-scrape: {daily_revoc} new today, cumulative {cum_revoc}

Total today: {total_today} new leads
Grand cumulative across all sheets: {grand_cum}"""

# Send to Telegram
requests.post(
    f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
    json={
        "chat_id": os.getenv("CHAT_ID"),
        "text": message,
        "parse_mode": "Markdown"
    }
)

print("✅ Cumulative report sent")