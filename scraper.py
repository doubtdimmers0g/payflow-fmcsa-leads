from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA GRANT DIAGNOSTIC - showing EXACT raw text the script sees")
    print("No sheet writes - console only\n")

    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    print(f"Date: {today_str}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            print("Loading selection page...")
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            row = page.locator(f"tr:has-text('{today_str}')")
            if row.count() == 0:
                print("Today's row not found.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found — only PDF links exist now.")
                return

            print("Navigating to HTML Detail page...")
            with page.expect_navigation(timeout=60000):
                detail_button.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            print("✅ HTML Detail page loaded successfully\n")

            soup = BeautifulSoup(page.content(), 'html.parser')

            # Search for exact phrase from your screenshots
            phrase_matches = soup.find_all(string=re.compile(r'except household goods', re.I))
            print(f"Found '{len(phrase_matches)}' occurrences of 'except household goods' on the page:")
            for m in phrase_matches:
                print(f"  → {m.strip()}")

            # All authority headers
            print("\n=== ALL AUTHORITY HEADERS FOUND (exact text) ===")
            authority_rows = soup.find_all('tr')
            for r in authority_rows:
                cells = r.find_all(['th', 'td'])
                if len(cells) == 1:
                    text = cells[0].get_text(strip=True).rstrip(':').strip()
                    if "Interstate" in text or "carrier" in text.lower():
                        print(f"Authority: '{text}'")

            # GRANT section raw text
            grant_section = soup.find(string=re.compile(r'GRANT DECISION NOTICES', re.I))
            if grant_section:
                print("\n=== RAW TEXT AROUND GRANT DECISION NOTICES ===")
                section_text = grant_section.parent.get_text(separator='\n', strip=True)[:2000]  # first 2000 chars
                print(section_text)

            # Sample tables
            print("\n=== TABLES WITH 'Filed' OR 'Applicant' ===")
            for table in soup.find_all('table'):
                header = table.find('tr')
                if header:
                    headers = [c.get_text(strip=True) for c in header.find_all(['th', 'td'])]
                    if 'Filed' in headers or 'Applicant' in headers:
                        print(f"Table headers: {headers}")
                        rows = table.find_all('tr')[:3]
                        for row in rows:
                            print("  Row:", [c.get_text(strip=True) for c in row.find_all(['th', 'td'])])

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()