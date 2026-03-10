from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - GRANT DECISION NOTICES only")
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

            # === EXPLICITLY TARGET GRANT DECISION NOTICES SECTION ===
            grant_header = soup.find(string=re.compile(r"GRANT DECISION NOTICES", re.I))
            if not grant_header:
                print("Could not find 'GRANT DECISION NOTICES' section on the page.")
                return

            target_table = grant_header.find_next('table')
            if not target_table:
                print("Found GRANT DECISION NOTICES header but no table after it.")
                return

            print("✅ Found GRANT DECISION NOTICES table")

            # Extract from that exact table
            entries = []
            rows = target_table.find_all('tr')[1:]  # skip header

            for r in rows:
                cells = [cell.get_text(strip=True) for cell in r.find_all(['th', 'td'])]
                if len(cells) < 3:
                    continue

                mc = cells[0].strip()
                title = cells[1].strip()
                decided = cells[2].strip()

                name = title.split(' - ', 1)[0] if ' - ' in title else title
                location = title.split(' - ', 1)[1] if ' - ' in title else ""

                if re.search(r'MC-\d{4,8}', mc, re.I):
                    entry = {
                        "mc": mc,
                        "name": name,
                        "decided_date": decided,
                        "location": location
                    }
                    entries.append(entry)
                    print(f"EXTRACTED → {mc} | {name} | Decided: {decided}")

            decided_dates = {e["decided_date"] for e in entries}
            print(f"\n✅ Found {len(entries)} new leads in the GRANT DECISION NOTICES section.")
            print(f"Decided dates present: {sorted(decided_dates)}")

            if entries:
                print("\nMC Number | Company Name | Location | Decided")
                print("-" * 70)
                for e in entries:
                    print(f"{e['mc']} | {e['name']} | {e['location']} | {e['decided_date']}")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()