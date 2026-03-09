from playwright.sync_api import sync_playwright
import re
from datetime import date
import time

def main():
    print("TEST MODE: Playwright HTML Detail scraper - no sheet writes")
    print("Only printing leads to console for validation")

    today = date.today()
    today_str = today.strftime('%m/%d/%y')  # e.g., 03/09/26

    entries = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            print("Loading selection page...")
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            print(f"Looking for row with date '{today_str}'...")
            row = page.locator(f"tr:has-text('{today_str}')")
            if row.count() == 0:
                print("Today's row not found. Register may not be updated yet.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            if detail_button.count() == 0:
                print("HTML Detail button not found in row.")
                return

            print("Submitting HTML Detail form...")
            with page.expect_navigation(timeout=60000):
                detail_button.click()

            page.wait_for_load_state("networkidle", timeout=60000)
            print("HTML Detail page loaded")

            # Debug: print first chunk of content
            content_preview = page.inner_text("body")[:1000]
            print("Content preview (first 1000 chars):")
            print(content_preview)
            print("...")

            content = page.inner_text("body")
            lines = [line.strip() for line in content.split('\n') if line.strip()]

            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            in_block = False
            current_authority = None
            i = 0
            while i < len(lines):
                line = lines[i]

                if any(p in line for p in target_phrases):
                    in_block = True
                    current_authority = line
                    print(f"Found block: {current_authority[:80]}...")
                    i += 1
                    continue

                if not in_block:
                    i += 1
                    continue

                mc_match = re.search(r'(MC-180\d{4,5}(?:-[A-Z])?)', line)
                if mc_match:
                    mc = mc_match.group(1)

                    name = ""
                    tel = ""
                    location = "N/A"
                    j = 1
                    while j < 10 and i + j < len(lines):
                        next_line = lines[i + j]
                        if "Tel:" in next_line:
                            tel_match = re.search(r'Tel:\s*(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})', next_line, re.I)
                            if tel_match:
                                tel_clean = re.sub(r'[\s().-]', '', tel_match.group(1))
                                if len(tel_clean) == 10:
                                    tel = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"
                            break
                        if len(next_line) > 12 and not "Tel:" in next_line:
                            if not name:
                                name = next_line.strip()
                            elif re.search(r'[A-Z]{2}\s*\d{5}', next_line) and location == "N/A":
                                location = next_line.strip()
                        j += 1

                    if tel:
                        entry = {
                            "mc": mc,
                            "name": name,
                            "location": location,
                            "tel": tel,
                            "authority": current_authority,
                            "scrape_date": today.strftime('%Y-%m-%d')
                        }
                        entries.append(entry)
                        print(f"Added: {mc} - {name[:60]}... Tel: {tel} | Location: {location}")

                    if len(entries) >= 10:
                        break

                i += 1

            if entries:
                print(f"\nFound {len(entries)} leads")
                print("\nSAMPLE LEADS (TEST MODE):")
                for i, e in enumerate(entries[:10], 1):
                    print(f"{i}. MC: {e['mc']}")
                    print(f"   Name: {e['name']}")
                    print(f"   Location: {e['location']}")
                    print(f"   Tel: {e['tel']}")
                    print(f"   Authority: {e['authority'][:80]}...")
                    print("-" * 60)
            else:
                print("No matching MCs with Tel found in target blocks.")

        except Exception as e:
            print(f"Playwright error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
