from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup, NavigableString
from datetime import date, datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - extracting MC, Date, Company Name, Authority")
    print("No sheet writes - console only for validation")

    # Central Time (Houston) lock
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

            # === NEW DEBUG SECTION - this is what will show us the new structure ===
            print("\n=== DEBUG: PAGE TITLE ===")
            print(soup.title.get_text(strip=True) if soup.title else "No title")

            print("\n=== DEBUG: TABLES FOUND ===")
            tables = soup.find_all('table')
            print(f"Total tables on page: {len(tables)}")

            print("\n=== DEBUG: AUTHORITY PHRASES SEARCH ===")
            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]
            for phrase in target_phrases:
                matches = soup.find_all(string=re.compile(phrase, re.I))
                print(f"Matches for '{phrase}': {len(matches)}")
                for m in matches[:2]:
                    print(f"  → {m.strip()[:150]}...")

            print("\n=== DEBUG: MC NUMBERS FOUND ANYWHERE ===")
            mc_matches = soup.find_all(string=re.compile(r'MC-\d{4,8}', re.I))
            print(f"Found {len(mc_matches)} potential MC numbers")
            for m in mc_matches[:5]:
                print(f"  → {m.strip()}")

            print("\n=== DEBUG: SAMPLE TABLE ROWS (first 3 tables) ===")
            for i, table in enumerate(tables[:3]):
                rows = table.find_all('tr')[:4]
                print(f"\nTable {i+1} - first {len(rows)} rows:")
                for r in rows:
                    cells = [cell.get_text(strip=True) for cell in r.find_all(['th', 'td'])]
                    print(f"  Row: {cells[:6]}...")  # first 6 cells to keep logs readable

            # Old parser still runs for comparison (you can delete this block later)
            entries = []
            authority_cells = soup.find_all('td', attrs={'colspan': '4'})
            for cell in authority_cells:
                authority_text = cell.get_text(strip=True)
                if any(p in authority_text for p in target_phrases):
                    # ... (your original extraction logic unchanged)
                    pass  # we'll replace this once we see the debug output

            if not entries:
                print("\nNo matching rows found with old logic (as expected). Share these debug logs and I'll send the updated parser immediately.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()