from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import date, datetime
from zoneinfo import ZoneInfo
import re  # added so the MC check doesn't crash later

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - extracting MC, Date, Company Name, Authority")
    print("No sheet writes - console only for validation")

    # Central Time (Houston) so it always matches your local day
    central = ZoneInfo("America/Chicago")
    today_str = datetime.now(central).strftime('%m/%d/%Y')  # e.g., 03/09/2026
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

            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            entries = []
            authority_cells = soup.find_all('td', attrs={'colspan': '4'})
            for cell in authority_cells:
                authority_text = cell.get_text(strip=True)
                if any(p in authority_text for p in target_phrases):
                    row = cell.find_parent('tr')
                    if not row:
                        continue

                    cells = row.find_all(['th', 'td'])
                    if len(cells) < 3:
                        continue

                    mc_cell = cells[0]
                    mc = mc_cell.get_text(strip=True)
                    if not re.match(r'MC-180\d{4,5}(?:-[A-Z])?', mc, re.I):
                        continue

                    date_cell = cells[1]
                    date_str = date_cell.get_text(strip=True)

                    name_cell = cells[2]
                    name_div = name_cell.find('div')
                    name = name_div.get_text(strip=True) if name_div else "N/A"

                    entry = {
                        "mc": mc,
                        "date": date_str,
                        "name": name,
                        "authority": authority_text
                    }
                    entries.append(entry)
                    print(f"EXTRACTED: {mc} | Date: {date_str} | Name: {name} | Authority: {authority_text[:80]}...")

                    if len(entries) >= 10:
                        break

            if entries:
                print(f"\nFound {len(entries)} leads")
                print("\nSAMPLE LEADS (TEST MODE):")
                print("MC Number | Date | Company Name | Authority Type")
                print("-" * 80)
                for e in entries:
                    print(f"{e['mc']} | {e['date']} | {e['name']} | {e['authority']}")
            else:
                print("No matching rows found with target authority phrases - check if colspan=4 cells exist.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()