from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - extracting MC, Company Name, Decided Date")
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

            # Find the Grant Decision table
            target_table = None
            for table in soup.find_all('table'):
                header_row = table.find('tr')
                if header_row:
                    headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                    if 'Decided' in headers:
                        target_table = table
                        print(f"✅ Found Grant Decision table with columns: {headers}")
                        break

            if not target_table:
                print("Could not find table with 'Decided' column.")
                return

            # Extract ALL rows (this is today's fresh batch)
            entries = []
            rows = target_table.find_all('tr')[1:]  # skip header

            for r in rows:
                cells = [cell.get_text(strip=True) for cell in r.find_all(['th', 'td'])]
                if len(cells) < 3:
                    continue

                mc = cells[0].strip()
                title = cells[1].strip()
                decided = cells[2].strip()

                # Clean company name (split off location)
                name = title.split(' - ', 1)[0] if ' - ' in title else title

                if re.search(r'MC-\d{4,8}', mc, re.I):
                    entry = {
                        "mc": mc,
                        "name": name,
                        "decided_date": decided,
                        "location": title.split(' - ', 1)[1] if ' - ' in title else ""
                    }
                    entries.append(entry)
                    print(f"EXTRACTED → {mc} | {name} | Decided: {decided}")

            # Quick summary for visibility
            decided_dates = {e["decided_date"] for e in entries}
            print(f"\n✅ Found {len(entries)} new leads in today's register.")
            print(f"Decided dates present: {sorted(decided_dates)}")
            if entries:
                print("\nMC Number | Company Name | Location | Decided")
                print("-" * 70)
                for e in entries:
                    print(f"{e['mc']} | {e['name']} | {e['location']} | {e['decided_date']}")
            else:
                print("No grants in today's register (quiet day).")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()