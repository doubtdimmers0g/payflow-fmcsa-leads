from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re
from collections import defaultdict

def main():
    print("TEST MODE: FMCSA Authority Header Debug (exact text from page)")
    print("No sheet writes - just showing what the page actually contains\n")

    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    print(f"Date: {today_str}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            row = page.locator(f"tr:has-text('{today_str}')")
            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found.")
                return

            with page.expect_navigation(timeout=60000):
                detail_button.click()
            page.wait_for_load_state("networkidle")

            soup = BeautifulSoup(page.content(), 'html.parser')

            grant_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'GRANT DECISION NOTICES', tag.get_text(strip=True), re.I):
                    grant_header = tag
                    break

            target_table = None
            for table in grant_header.find_all_next('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Filed' in headers and 'Applicant' in headers:
                        target_table = table
                        break

            if not target_table:
                print("Table not found.")
                return

            rows = target_table.find_all('tr')[1:]
            authority_count = defaultdict(int)
            current_authority = "No authority header"

            print("=== EVERY AUTHORITY HEADER ON TODAY'S PAGE (exact text) ===\n")
            for i, r in enumerate(rows):
                cells = r.find_all(['th', 'td'])
                if len(cells) == 1:
                    text = cells[0].get_text(strip=True).rstrip(':').strip()
                    if text and ("carrier" in text.lower() or "Interstate" in text):
                        current_authority = text
                        print(f"Authority header #{len(authority_count)+1}: '{text}'")
                    continue

                if len(cells) == 4:
                    mc_cell = cells[0].get_text(strip=True)
                    if re.search(r'MC-\d{4,8}', mc_cell, re.I):
                        authority_count[current_authority] += 1

            print("\n=== SUMMARY - Leads per authority type ===")
            for auth, count in authority_count.items():
                print(f"• {auth}: {count} leads")

        finally:
            browser.close()

if __name__ == "__main__":
    main()