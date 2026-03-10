from playwright.sync_api import sync_playwright
import re
from datetime import date

def main():
    print("TEST MODE: FMCSA HTML Detail scraper - extracting MC, Date, Company Name, Authority")
    print("No sheet writes - console only for validation")

    today = date.today()
    today_str = today.strftime('%m/%d/%Y')  # e.g., 03/09/2026

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

            content = page.inner_text("body")
            lines = [line.strip() for line in content.split('\n') if line.strip()]

            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            entries = []
            in_block = False
            current_authority = None
            i = 0
            while i < len(lines):
                line = lines[i]

                # Detect authority block
                matched_phrase = next((p for p in target_phrases if p in line), None)
                if matched_phrase:
                    in_block = True
                    current_authority = matched_phrase
                    print(f"Found block: {current_authority[:80]}...")
                    i += 1
                    continue

                if not in_block:
                    i += 1
                    continue

                # MC match
                mc_match = re.search(r'(MC-180\d{4,5}(?:-[A-Z])?)', line, re.I)
                if mc_match:
                    mc = mc_match.group(1).upper()

                    date_str = ""
                    name = ""

                    j = 1
                    while j < 15 and i + j < len(lines):
                        next_line = lines[i + j]

                        # Date (mm/dd/yyyy)
                        date_match = re.search(r'\d{2}/\d{2}/\d{4}', next_line)
                        if date_match and not date_str:
                            date_str = date_match.group(0)

                        # Name - first substantial line after MC/date, stop before street number
                        if len(next_line) > 10 and not date_match and not re.search(r'^\d{1,5}\s', next_line):
                            if not name:
                                name = next_line.strip()

                        j += 1

                    if name and date_str:
                        entry = {
                            "mc": mc,
                            "date": date_str,
                            "name": name,
                            "authority": current_authority
                        }
                        entries.append(entry)
                        print(f"EXTRACTED: {mc} | Date: {date_str} | Name: {name} | Authority: {current_authority[:80]}...")

                    if len(entries) >= 10:
                        break

                i += 1

            if entries:
                print(f"\nFound {len(entries)} leads")
                print("\nSAMPLE LEADS (TEST MODE):")
                print("MC Number | Date | Company Name | Authority Type")
                print("-" * 80)
                for e in entries:
                    print(f"{e['mc']} | {e['date']} | {e['name']} | {e['authority']}")
            else:
                print("No valid entries found - check if MC/date/name lines are being hit.")

        except Exception as e:
            print(f"Playwright error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
