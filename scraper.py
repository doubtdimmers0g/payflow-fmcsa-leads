from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - extracting MC, Date, Company Name, Authority")
    print("No sheet writes - console only for validation")

    # Central Time lock (Houston)
    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')
    print(f"Today in Central Time (your local date): {today_str}")

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
                print("HTML Detail button not found.")
                return

            print("Submitting HTML Detail...")
            with page.expect_navigation(timeout=60000):
                detail_button.click()

            page.wait_for_load_state("networkidle", timeout=60000)
            print("HTML Detail loaded")

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # === UPGRADED DEBUG: Find the REAL data tables with MC numbers ===
            print("\n=== DEBUG: TABLES WITH MC NUMBERS (the ones we care about) ===")
            tables = soup.find_all('table')
            data_tables_found = 0
            for i, table in enumerate(tables):
                mc_matches = table.find_all(string=re.compile(r'MC-\d{4,8}', re.I))
                if len(mc_matches) > 5:  # only tables with real data
                    data_tables_found += 1
                    print(f"\nTable {i+1} (of {len(tables)}) — {len(mc_matches)} MCs found")
                    rows = table.find_all('tr')
                    print(f"  Total rows: {len(rows)}")

                    # Header row
                    if rows:
                        header_cells = [cell.get_text(strip=True) for cell in rows[0].find_all(['th', 'td'])]
                        print(f"  HEADER: {header_cells[:10]}...")

                    # Sample data rows (first 3 that have MC)
                    sample_count = 0
                    for r in rows[1:]:
                        cells = [cell.get_text(strip=True) for cell in r.find_all(['th', 'td'])]
                        if any(re.search(r'MC-\d{4,8}', c, re.I) for c in cells):
                            print(f"  SAMPLE ROW: {cells[:8]}...")
                            sample_count += 1
                            if sample_count >= 3:
                                break

                    # Any colspan?
                    colspans = table.find_all(attrs={'colspan': True})
                    if colspans:
                        print(f"  Colspans present: {len(colspans)}")

                    if data_tables_found >= 2:  # usually only 1 main table
                        break

            if data_tables_found == 0:
                print("No data tables with MCs found — site changed again.")

            print("\nDebug complete — share these logs and I'll send the full working parser immediately (MC + Date filter + Name + Authority).")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()