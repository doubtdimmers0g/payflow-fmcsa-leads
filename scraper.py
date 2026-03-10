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

            # Find the real data table INSIDE that section (has 'Decided' column + many rows)
            target_table = None
            for table in grant_header.find_all_next('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Decided' in headers and len(table.find_all('tr')) > 10:  # skip tiny tables
                        target_table = table
                        print(f"✅ Found real GRANT DECISION NOTICES data table with columns: {headers}")
                        break

            if not target_table:
                print("Found section header but could not locate the data table.")
                return

            # Extract leads
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

            print(f"\n✅ Found {len(entries)} new leads in GRANT DECISION NOTICES section.")
            if entries:
                print("\nMC Number | Company Name | Location | Decided")
                print("-" * 70)
                for e in entries:
                    print(f"{e['mc']} | {e['name']} | {e['location']} | {e['decided_date']}")
            else:
                print("No grants found in GRANT DECISION NOTICES (quiet day).")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()