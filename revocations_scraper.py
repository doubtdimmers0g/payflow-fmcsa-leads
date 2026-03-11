from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA REVOCATIONS Scraper")
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

            # Target REVOCATIONS table
            target_table = None
            for table in soup.find_all('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if headers == ['Number', 'Title', 'Decided', 'Decision Type']:
                        target_table = table
                        print("✅ Found REVOCATIONS table")
                        break

            if not target_table:
                print("No REVOCATIONS table today.")
                return

            # === EXTRACTION - MC- only ===
            entries = []
            rows = target_table.find_all('tr')[1:]

            for r in rows:
                cells = r.find_all(['th', 'td'])
                if len(cells) < 4:
                    continue

                number = cells[0].get_text(strip=True)
                title = cells[1].get_text(strip=True)
                decided = cells[2].get_text(strip=True)
                decision_type = cells[3].get_text(strip=True)

                mc_match = re.search(r'(MC-\d{4,8}(?:-[A-Z])?)', number, re.I)
                if not mc_match:
                    continue
                mc_number = mc_match.group(1)

                company_name = title.split(' - ', 1)[0] if ' - ' in title else title

                entry = {
                    "mc_number": mc_number,
                    "company_name": company_name,
                    "decided_date": decided,
                    "decision_type": decision_type
                }
                entries.append(entry)
                print(f"EXTRACTED → {mc_number} | {company_name} | Decided: {decided} | Type: {decision_type}")

            print(f"\n✅ Found {len(entries)} MC- revocation leads.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()