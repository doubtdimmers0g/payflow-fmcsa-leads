from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import json
import os
import gspread
from google.oauth2 import service_account
import requests

def send_telegram(summary_line):
    token = "8733411381:AAHK0TqW0SE6yRu3VwHpuUZcTeB9dsEejH0"
    chat_id = 7691951053
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    date_str = datetime.now().strftime('%A, %B %d, %Y')
    full_message = f"**{date_str} – Extractor Update**\n\n{summary_line}"
    
    try:
        requests.post(url, json={"chat_id": chat_id, "text": full_message, "parse_mode": "Markdown"})
        print("✅ Telegram sent")
    except Exception as e:
        print(f"Telegram failed: {e}")

def main():
    print("🚀 FMCSA WITHDRAWALS Scraper - PRODUCTION (MC- only + correct column order)")
    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    run_date = datetime.now(central).strftime('%Y-%m-%d')
    print(f"Running for: {today_str} (run_date = {run_date})\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            row = page.locator(f"tr:has-text('{today_str}')")
            if row.count() == 0:
                print("No register row today.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found.")
                return

            with page.expect_navigation(timeout=60000):
                detail_button.click()
            page.wait_for_load_state("networkidle", timeout=60000)

            soup = BeautifulSoup(page.content(), 'html.parser')

            # Target exact WITHDRAWALS table (same header as dismissals)
            target_table = None
            for table in soup.find_all('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if headers == ['Number', 'Title', 'Published', 'Decided']:
                        # Quick check inside the table to make sure it's Withdrawals
                        if any("WITHDRAWALS" in cell.get_text(strip=True).upper() for cell in table.find_all('td')):
                            target_table = table
                            break

            if not target_table:
                print("No WITHDRAWALS table today.")
                return

            # Extract MC- only
            entries = []
            rows = target_table.find_all('tr')[1:]

            for r in rows:
                cells = r.find_all(['th', 'td'])
                if len(cells) < 4:
                    continue

                number = cells[0].get_text(strip=True)
                title = cells[1].get_text(strip=True)
                published = cells[2].get_text(strip=True)
                decided = cells[3].get_text(strip=True)

                mc_match = re.search(r'(MC-\d{4,8}(?:-[A-Z])?)', number, re.I)
                if not mc_match:
                    continue
                mc_number = mc_match.group(1)

                company_name = title.split(' - ', 1)[0] if ' - ' in title else title

                entry = {
                    "run_date": run_date,
                    "mc_number": mc_number,
                    "company_name": company_name,
                    "published_date": published,
                    "decided_date": decided
                }
                entries.append(entry)

            print(f"Found {len(entries)} MC- withdrawal leads.")

            # === Google Sheets write + dedupe ===
            if entries:
                creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
                client = gspread.authorize(creds)
                sheet = client.open_by_key(os.getenv("SHEET_ID")).worksheet("Withdrawals")

                existing_mcs = {row[1] for row in sheet.get_all_values()[1:]}

                new_rows = []
                for e in entries:
                    if e["mc_number"] not in existing_mcs:
                        new_rows.append([
                            e["run_date"],
                            e["mc_number"],
                            e["company_name"],
                            e["published_date"],
                            e["decided_date"]
                        ])

                if new_rows:
                    sheet.append_rows(new_rows)
                    print(f"✅ Added {len(new_rows)} NEW withdrawal leads.")
                else:
                    print("No new withdrawals today.")
            else:
                print("No MC- withdrawals today.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()
            
        # Telegram (daily + cumulative for this sheet)
        entries_count = len(entries) if 'entries' in locals() else 0
        added_count = len(new_rows) if 'new_rows' in locals() else 0
        cumulative = len(sheet.get_all_values()) - 1 if 'sheet' in locals() else 0
        send_telegram(f"withdrawals-scrape: {entries_count} Withdrawals. Added {added_count} new. Cumulative in Withdrawals sheet: {cumulative}")

if __name__ == "__main__":
    main()