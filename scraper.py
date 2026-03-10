from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - GRANT DECISION NOTICES only (detailed table)")
    print("No sheet writes - console only for validation\n")

    # Central Time lock (Houston)
    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    print(f"Today in Central Time: {today_str}")
    print(f"Loading register for: {today_str}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            print("Loading selection page...")
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            row = page.locator(f"tr:has-text('{today_str}')")
            if row.count() == 0:
                print("Today's register row not found.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found.")
                return

            print("Navigating to HTML Detail page...")
            with page.expect_navigation(timeout=60000):
                detail_button.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            print("✅ HTML Detail page loaded successfully\n")

            soup = BeautifulSoup(page.content(), 'html.parser')

            # === TARGET GRANT DECISION NOTICES SECTION ===
            grant_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'GRANT DECISION NOTICES', tag.get_text(strip=True), re.I):
                    grant_header = tag
                    print("✅ Located GRANT DECISION NOTICES section header")
                    break

            if not grant_header:
                print("Could not locate GRANT DECISION NOTICES section.")
                return

            # Find the detailed table with "Filed" / "Applicant" / "Representative" (exact match to your screenshot)
            target_table = None
            for table in grant_header.find_all_next('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Filed' in headers and 'Applicant' in headers and 'Representative' in headers:
                        target_table = table
                        print(f"✅ Found detailed GRANT DECISION NOTICES table with columns: {headers}")
                        break

            if not target_table:
                print("Found section header but could not locate the detailed data table.")
                return

            # Extract leads from the detailed table
            entries = []
            rows = target_table.find_all('tr')[1:]  # skip header

            for r in rows:
                cells = r.find_all(['th', 'td'])
                if len(cells) < 3:
                    continue

                filed_cell = cells[0].get_text(strip=True)
                applicant_cell = cells[1].get_text(separator='\n', strip=True)
                rep_cell = cells[2].get_text(separator='\n', strip=True)

                # Pull MC and filed date
                mc_match = re.search(r'(MC-\d{4,8}(?:-[A-Z])?)', filed_cell, re.I)
                if not mc_match:
                    continue
                mc = mc_match.group(1)
                filed_date = re.search(r'\d{2}/\d{2}/\d{4}', filed_cell)
                filed_date = filed_date.group(0) if filed_date else ""

                # Clean applicant (first line = name, rest = address)
                applicant_lines = [line.strip() for line in applicant_cell.split('\n') if line.strip()]
                name = applicant_lines[0] if applicant_lines else ""
                address = ' '.join(applicant_lines[1:]) if len(applicant_lines) > 1 else ""

                # Pull phone from rep cell
                phone_match = re.search(r'Phone:\s*([\(\)\d\s-]+)', rep_cell, re.I)
                phone = phone_match.group(1).strip() if phone_match else "N/A"

                entry = {
                    "mc": mc,
                    "name": name,
                    "filed_date": filed_date,
                    "address": address,
                    "rep_info": rep_cell.split('\n')[0] if rep_cell else "",
                    "phone": phone
                }
                entries.append(entry)
                print(f"EXTRACTED → {mc} | {name} | Filed: {filed_date} | Phone: {phone}")

            print(f"\n✅ Found {len(entries)} new leads in the GRANT DECISION NOTICES detailed table.")
            if entries:
                print("\nMC Number | Company Name | Filed Date | Phone | Address")
                print("-" * 90)
                for e in entries:
                    print(f"{e['mc']} | {e['name']} | {e['filed_date']} | {e['phone']} | {e['address'][:60]}...")
            else:
                print("No grants found in the detailed GRANT section (quiet day).")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()