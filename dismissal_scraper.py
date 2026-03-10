from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA DISMISSAL Scraper - RAW TEXT DEBUG")
    print("No sheet writes - console only for validation\n")

    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    print(f"Today in Central Time: {today_str}\n")

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

            # Target DISMISSAL section
            dismissal_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'DISMISSAL', tag.get_text(strip=True), re.I):
                    dismissal_header = tag
                    print("✅ Located DISMISSAL section header")
                    break

            if not dismissal_header:
                print("DISMISSAL section not found.")
                return

            # === RAW TEXT AROUND DISMISSAL HEADER ===
            print("\n=== RAW TEXT AROUND DISMISSAL HEADER (first 1500 chars) ===")
            section_text = dismissal_header.parent.get_text(separator='\n', strip=True)[:1500]
            print(section_text)

            # Search for any table with 'Published' or 'Decided'
            print("\n=== TABLES CONTAINING 'Published' OR 'Decided' ===")
            target_table = None
            for table in soup.find_all('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Published' in headers or 'Decided' in headers:
                        target_table = table
                        print(f"✅ Found table with 'Published' or 'Decided': {headers}")
                        break

            if not target_table:
                print("No table containing 'Published' or 'Decided' found on the page.")
                return

            # Show first few rows for verification
            print("\n=== FIRST 3 ROWS OF THE TABLE ===")
            rows = target_table.find_all('tr')[:4]
            for i, r in enumerate(rows):
                cells = [cell.get_text(strip=True) for cell in r.find_all(['th', 'td'])]
                print(f"Row {i}: {cells}")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()