from playwright.sync_api import sync_playwright
import re
from datetime import date

def main():
    print("TEST MODE: Playwright HTML Detail scraper - no sheet writes")
    print("Only printing to console for validation")

    today = date.today()
    today_str = today.strftime('%m/%d/%Y')  # Full year: 03/09/2026
    print(f"Searching for row with date: '{today_str}'")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()

        try:
            print("Loading selection page...")
            page.goto("https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list", timeout=60000)
            page.wait_for_load_state("networkidle")

            print(f"Page title: {page.title()}")

            # Debug: print first few rows to see format
            rows_preview = page.locator("tr").all_inner_texts()[:5]
            print("First few rows preview:")
            for r in rows_preview:
                print(r[:100] + "..." if len(r) > 100 else r)

            print(f"Looking for row with '{today_str}'...")
            row = page.locator(f"tr:has-text('{today_str}')")
            row_count = row.count()
            print(f"Row count found: {row_count}")

            if row_count == 0:
                print("Today's row still not found. Possible format mismatch or page not updated.")
                return

            detail_button = row.locator("input[value='HTML Detail']")
            button_count = detail_button.count()
            print(f"HTML Detail button count in row: {button_count}")

            if button_count == 0:
                print("Button not found. Inspecting row HTML...")
                row_html = row.inner_html()
                print("Row HTML preview:", row_html[:500])
                return

            print("Clicking HTML Detail...")
            with page.expect_navigation(timeout=60000):
                detail_button.click()

            page.wait_for_load_state("networkidle", timeout=60000)
            print("HTML Detail page loaded")
            print(f"Detail page title: {page.title()}")

            # Preview content
            content_preview = page.inner_text("body")[:1500]
            print("HTML Detail content preview (first 1500 chars):")
            print(content_preview)
            print("...")

            # Debug content length
            print(f"Content length: {len(content)} chars")

            lines = [line.strip() for line in content.split('\n') if line.strip()]

            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            entries = []
            in_block = False  # Initialize here
            current_authority = None
            i = 0
            while i < len(lines):
                line = lines[i]

                # Start of target block
                if any(p in line for p in target_phrases):
                    in_block = True
                    current_authority = line
                    print(f"Found block: {current_authority[:80]}...")
                    i += 1
                    continue

                if not in_block:
                    i += 1
                    continue

                # Look for MC-180xxxx
                mc_match = re.search(r'(MC-180\d{4,5}(?:-[A-Z])?)', line, re.I)
                if mc_match:
                    mc = mc_match.group(1).upper()

                    name = ""
                    tel = ""
                    location = "N/A"

                    # Scan ahead for name, tel, location
                    j = 1
                    while j < 15 and i + j < len(lines):
                        next_line = lines[i + j]

                        # Tel detection (more flexible)
                        tel_match = re.search(r'tel\s*:\s*(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})', next_line, re.I)
                        if tel_match:
                            tel_clean = re.sub(r'[\s().-]', '', tel_match.group(1))
                            if len(tel_clean) == 10:
                                tel = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"

                        # Name (substantial line, not Tel or location)
                        if len(next_line) > 12 and not tel_match and not re.search(r'\d{5}', next_line):
                            if not name:
                                name = next_line.strip()

                        # Location (city/state/ZIP pattern)
                        if re.search(r'[A-Za-z ]+,\s*[A-Z]{2}\s*\d{5}', next_line):
                            location = next_line.strip()

                        j += 1

                    if tel:
                        entry = {
                            "mc": mc,
                            "name": name or "N/A",
                            "location": location,
                            "tel": tel,
                            "authority": current_authority,
                            "scrape_date": today.strftime('%Y-%m-%d')
                        }
                        entries.append(entry)
                        print(f"Added: {mc} - {name[:60]}... Tel: {tel} | Location: {location}")

                    if len(entries) >= 10:
                        break

                # Reset block if we hit a major section break
                if "grant decision notices" in line.lower() or "fitness-only" in line.lower() or "certificate" in line.lower():
                    in_block = False

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
                print("No matching MCs with Tel found - check if Tel lines are parsed correctly.")
                
        except Exception as e:
            print(f"Playwright error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
