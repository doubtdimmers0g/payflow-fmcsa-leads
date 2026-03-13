from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import json
import gspread
from google.oauth2 import service_account
import os
import requests

def send_telegram(summary_line):
    token = "8733411381:AAHK0TqW0SE6yRu3VwHpuUZcTeB9dsEejH0"   # TODO: move to GitHub Secret next week
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
    print("🚀 FMCSA GRANT Scraper - PRODUCTION (FITNESS-ONLY + Rep Name)")
    central = ZoneInfo("America/Chicago")
    today = datetime.now(central)
    today_str = today.strftime('%m/%d/%Y')
    run_date = today.strftime('%Y-%m-%d')
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

            grant_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'GRANT DECISION NOTICES', tag.get_text(strip=True), re.I):
                    grant_header = tag
                    break

            if not grant_header:
                print("GRANT section not found.")
                return

            # Use the SECOND matching table (FITNESS-ONLY)
            target_table = None
            count = 0
            for table in grant_header.find_all_next('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Filed' in headers and 'Applicant' in headers:
                        count += 1
                        if count == 2:
                            target_table = table
                            break

            if not target_table:
                print("FITNESS-ONLY table not found.")
                return

            # Extract leads
            entries = []
            rows = target_table.find_all('tr')[1:]
            current_authority = ""

            for r in rows:
                cells = r.find_all(['th', 'td'])

                if len(cells) == 1:
                    text = cells[0].get_text(strip=True).rstrip(':').strip()
                    if "Interstate" in text or "carrier" in text.lower():
                        current_authority = text
                    continue

                if len(cells) != 4:
                    continue

                mc_cell = cells[0].get_text(strip=True)
                filed_text = cells[1].get_text(strip=True)
                applicant_text = cells[2].get_text(separator='\n', strip=True)
                rep_text = cells[3].get_text(separator='\n', strip=True)

                mc_match = re.search(r'(MC-\d{4,8}(?:-[A-Z])?)', mc_cell, re.I)
                if not mc_match:
                    continue
                mc = mc_match.group(1)

                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', filed_text)
                filed_date = date_match.group(1) if date_match else ""

                applicant_lines = [line.strip() for line in applicant_text.splitlines() if line.strip()]
                name = applicant_lines[0] if applicant_lines else ""
                address = " ".join(applicant_lines[1:]) if len(applicant_lines) > 1 else ""

                rep_lines = [line.strip() for line in rep_text.splitlines() if line.strip()]
                rep_name = rep_lines[0] if rep_lines else "N/A"

                phone_match = re.search(r'Phone:\s*([\(\)\d\s-]+)', rep_text, re.I)
                phone = phone_match.group(1).strip() if phone_match else "N/A"
                phone = re.sub(r'\D', '', phone)
                if len(phone) == 10:
                    phone = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"

                entry = {
                    "run_date": run_date,
                    "mc_number": mc,
                    "company_name": name,
                    "authority_type": current_authority,
                    "filed_date": filed_date,
                    "address": address,
                    "rep_name": rep_name,
                    "phone": phone
                }
                entries.append(entry)

            print(f"Found {len(entries)} leads in FITNESS-ONLY table.")

            # === Google Sheets + Dedupe (fixed scopes) ===
            if entries:
                creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
                client = gspread.authorize(creds)
                sheet = client.open_by_key(os.getenv("SHEET_ID")).sheet1

                existing_mcs = {row[1] for row in sheet.get_all_values()[1:]}

                new_rows = []
                for e in entries:
                    if e["mc_number"] and e["mc_number"] not in existing_mcs:
                        new_rows.append([
                            e["run_date"],
                            e["mc_number"],
                            e["company_name"],
                            e["authority_type"],
                            e["filed_date"],
                            e["address"],
                            e["rep_name"],
                            e["phone"]
                        ])

                if new_rows:
                    sheet.append_rows(new_rows)
                    print(f"✅ Added {len(new_rows)} NEW leads to your Payflow sheet.")
                else:
                    print("No new leads today.")
            else:
                print("No leads in FITNESS-ONLY table today.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

        entries_count = len(entries) if 'entries' in locals() else 0
        added_count = len(new_rows) if 'new_rows' in locals() else 0
        send_telegram(f"daily-scrape: {len(entries)} Grants. Added {len(new_rows) if 'new_rows' in locals() else 0} to sheet.")

if __name__ == "__main__":
    main()