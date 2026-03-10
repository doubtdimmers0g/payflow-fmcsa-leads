from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA GRANT - Full Section Scan (Fixed)")
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

            # Locate GRANT DECISION NOTICES section
            grant_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'GRANT DECISION NOTICES', tag.get_text(strip=True), re.I):
                    grant_header = tag
                    print("✅ Located GRANT DECISION NOTICES section header")
                    break

            if not grant_header:
                print("Could not locate GRANT section.")
                return

            # Get ALL content inside the GRANT section
            grant_section = grant_header.find_parent('div') or grant_header.find_next_sibling()
            if not grant_section:
                grant_section = soup

            # Find all MC data rows and their preceding authority
            entries = []
            current_authority = ""
            target_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            # Scan every row in the entire section
            for tr in grant_section.find_all('tr'):
                cells = tr.find_all(['th', 'td'])

                # Check for target authority header anywhere in the row
                row_text = tr.get_text(strip=True)
                for phrase in target_phrases:
                    if phrase in row_text:
                        current_authority = phrase
                        print(f"→ Matched target authority: {current_authority}")
                        break

                # Data row with MC
                if len(cells) >= 3:
                    mc_cell = cells[0].get_text(strip=True)
                    mc_match = re.search(r'(MC-\d{4,8}(?:-[A-Z])?)', mc_cell, re.I)
                    if mc_match:
                        mc = mc_match.group(1)

                        filed_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        applicant_text = cells[2].get_text(separator='\n', strip=True) if len(cells) > 2 else ""
                        rep_text = cells[3].get_text(separator='\n', strip=True) if len(cells) > 3 else ""

                        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', filed_text)
                        filed_date = date_match.group(1) if date_match else ""

                        applicant_lines = [line.strip() for line in applicant_text.splitlines() if line.strip()]
                        name = applicant_lines[0] if applicant_lines else ""
                        address = " ".join(applicant_lines[1:]) if len(applicant_lines) > 1 else ""

                        phone_match = re.search(r'Phone:\s*([\(\)\d\s-]+)', rep_text, re.I)
                        phone = phone_match.group(1).strip() if phone_match else "N/A"

                        if current_authority:
                            entry = {
                                "mc": mc,
                                "name": name,
                                "address": address,
                                "filed_date": filed_date,
                                "phone": phone,
                                "authority_type": current_authority
                            }
                            entries.append(entry)
                            print(f"EXTRACTED → {mc} | {name} | {address[:40]}... | {filed_date} | {phone}")

            print(f"\n✅ Found {len(entries)} leads matching your target authority types.")
            if entries:
                print("\nMC Number | Company Name | Address | Filed Date | Phone | Authority Type")
                print("-" * 130)
                for e in entries:
                    print(f"{e['mc']} | {e['name']} | {e['address']} | {e['filed_date']} | {e['phone']} | {e['authority_type']}")
            else:
                print("Still no target leads — but the debug will show us the next step.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()