from playwright.sync_api import sync_playwright
import re
from datetime import date
import os
import gspread
from google.oauth2.service_account import Credentials

def main():
    print("Playwright scraper: Fetches HTML Detail for today's FMCSA Register")

    today = date.today()
    today_str = today.strftime('%m/%d/%y')  # e.g., 03/09/26 for row match

    entries = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            print("Loading selection page...")
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)

            print(f"Looking for row with date '{today_str}'...")
            row = page.locator(f"tr:has-text('{today_str}')")
            if row.count() == 0:
                print("Today's row not found - register may not be published yet.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found in row.")
                return

            print("Submitting HTML Detail form...")
            with page.expect_navigation(timeout=60000):
                detail_button.click()

            page.wait_for_load_state("networkidle", timeout=60000)
            print("HTML Detail page loaded")

            content = page.inner_text("body")
            lines = [line.strip() for line in content.split('\n') if line.strip()]

            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            in_block = False
            current_authority = None
            i = 0
            while i < len(lines):
                line = lines[i]

                if any(p in line for p in target_phrases):
                    in_block = True
                    current_authority = line
                    print(f"Found authority block: {current_authority[:80]}...")
                    i += 1
                    continue

                if not in_block:
                    i += 1
                    continue

                mc_match = re.search(r'(MC-180\d{4,5}(?:-[A-Z])?)', line)
                if mc_match:
                    mc = mc_match.group(1)

                    name = ""
                    tel = ""
                    location = "N/A"
                    j = 1
                    while j < 10 and i + j < len(lines):
                        next_line = lines[i + j]
                        if "Tel:" in next_line:
                            tel_match = re.search(r'Tel:\s*(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})', next_line, re.I)
                            if tel_match:
                                tel_clean = re.sub(r'[\s().-]', '', tel_match.group(1))
                                if len(tel_clean) == 10:
                                    tel = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"
                            break
                        if len(next_line) > 12 and not "Tel:" in next_line:
                            if not name:
                                name = next_line.strip()
                            elif re.search(r'[A-Z]{2}\s*\d{5}', next_line) and location == "N/A":
                                location = next_line.strip()
                        j += 1

                    if tel:
                        entry = {
                            "mc": mc,
                            "name": name,
                            "location": location,
                            "tel": tel,
                            "authority": current_authority,
                            "scrape_date": today.strftime('%Y-%m-%d')
                        }
                        entries.append(entry)
                        print(f"Added: {mc} - {name[:60]}... Tel: {tel}")

                    if len(entries) >= 10:
                        break

                i += 1

            if entries:
                print(f"\nFound {len(entries)} leads in target blocks")
                append_to_sheet(entries)
            else:
                print("No matching MCs with Tel found in authority blocks.")

        except Exception as e:
            print(f"Playwright error: {str(e)}")
        finally:
            browser.close()

def append_to_sheet(entries):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('creds.json', scopes=scope)
    client = gspread.authorize(creds)

    sheet_id = os.environ.get('SHEET_ID')
    if not sheet_id:
        print("SHEET_ID env var missing - skipping sheet append")
        return

    try:
        sheet = client.open_by_key(sheet_id).worksheet("FitnessPrelim")  # Change tab name if needed
        rows = []
        for e in entries:
            rows.append([
                e['mc'],
                e['name'],
                e['location'],
                e['tel'],
                e['scrape_date'],
                e['authority'][:100]
            ])
        sheet.append_rows(rows)
        print(f"Appended {len(entries)} leads to FitnessPrelim tab")
    except Exception as e:
        print(f"Sheet append error: {str(e)}")

if __name__ == "__main__":
    main()
