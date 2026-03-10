from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - GRANT DECISION NOTICES only (detailed table - DEBUG MODE)")
    print("No sheet writes - console only for validation\n")

    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    print(f"Today in Central Time: {today_str}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            row = page.locator(f"tr:has-text('{today_str}')")
            if row.count() == 0:
                print("Today's row not found.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found.")
                return

            with page.expect_navigation(timeout=60000):
                detail_button.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            print("✅ HTML Detail page loaded successfully\n")

            soup = BeautifulSoup(page.content(), 'html.parser')

            # Locate GRANT DECISION NOTICES section
            grant_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'GRANT DECISION NOTICES', tag.get_text(strip=True), re.I):
                    grant_header = tag
                    print("✅ Located GRANT DECISION NOTICES section header")
                    break

            if not grant_header:
                print("Could not locate GRANT section.")
                return

            # Find detailed table
            target_table = None
            for table in grant_header.find_all_next('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Filed' in headers and 'Applicant' in headers and 'Representative' in headers:
                        target_table = table
                        print(f"✅ Found detailed GRANT table with columns: {headers}")
                        break

            if not target_table:
                print("Could not find detailed GRANT table.")
                return

            # === DEBUG: Show raw row structure ===
            rows = target_table.find_all('tr')[1:]  # skip header
            print(f"\n=== DEBUG: Total rows in GRANT table: {len(rows)} ===")
            for i, r in enumerate(rows[:8]):  # first 8 rows only
                cells = r.find_all(['th', 'td'])
                print(f"\nRow {i+1} — {len(cells)} cells:")
                for j, cell in enumerate(cells):
                    text = cell.get_text(strip=True).replace('\n', ' | ')
                    print(f"   Cell {j}: '{text}'")

            print("\nDebug complete — share these logs and I'll send the final working parser immediately.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()