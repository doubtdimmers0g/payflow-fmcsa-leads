from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

def main():
    print("TEST MODE: FMCSA GRANT - FITNESS-ONLY section ONLY")
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

            # === TARGET ONLY THE FITNESS-ONLY SECTION ===
            fitness_header = None
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p']):
                if re.search(r'FITNESS-ONLY', tag.get_text(strip=True), re.I):
                    fitness_header = tag
                    print("✅ Located FITNESS-ONLY section header")
                    break

            if not fitness_header:
                print("FITNESS-ONLY section not found on this page.")
                return

            # Find the table immediately after the FITNESS-ONLY header
            target_table = fitness_header.find_next('table')
            if not target_table:
                print("FITNESS-ONLY table not found.")
                return

            print(f"✅ Found FITNESS-ONLY table with columns: {[cell.get_text(strip=True) for cell in target_table.find('tr').find_all(['th', 'td'])]}")

            # === Extract leads from FITNESS-ONLY table ===
            entries = []
            rows = target_table.find_all('tr')[1:]
            current_authority = ""

            for r in rows:
                cells = r.find_all(['th', 'td'])

                if len(cells) == 1:
                    text = cells[0].get_text(strip=True).rstrip(':').strip()
                    if "Interstate" in text or "carrier" in text.lower():
                        current_authority = text
                    continue

                if len(cells) != 4:
                    continue

                mc_cell = cells[0].get_text(strip=True)
                filed_text = cells[1].get_text(strip=True)
                applicant_text = cells[2].get_text(separator='\n', strip=True)
                rep_text = cells[3].get_text(separator='\n', strip=True)

                mc_match = re.search(r'(MC-\d{4,8}(?:-[A-Z])?)', mc_cell, re.I)
                if not mc_match:
                    continue
                mc = mc_match.group(1)

                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', filed_text)
                filed_date = date_match.group(1) if date_match else ""

                applicant_lines = [line.strip() for line in applicant_text.splitlines() if line.strip()]
                name = applicant_lines[0] if applicant_lines else ""
                address = " ".join(applicant_lines[1:]) if len(applicant_lines) > 1 else ""

                phone_match = re.search(r'Phone:\s*([\(\)\d\s-]+)', rep_text, re.I)
                phone = phone_match.group(1).strip() if phone_match else "N/A"

                entry = {
                    "mc": mc,
                    "name": name,
                    "address": address,
                    "filed_date": filed_date,
                    "phone": phone,
                    "authority_type": current_authority
                }
                entries.append(entry)
                print(f"EXTRACTED (FITNESS-ONLY) → {mc} | {name} | {address[:40]}... | {filed_date} | {phone} | {current_authority}")

            print(f"\n✅ Found {len(entries)} leads in the FITNESS-ONLY section.")
            if entries:
                print("\nMC Number | Company Name | Address | Filed Date | Phone | Authority Type")
                print("-" * 140)
                for e in entries:
                    print(f"{e['mc']} | {e['name']} | {e['address']} | {e['filed_date']} | {e['phone']} | {e['authority_type']}")
            else:
                print("No leads in FITNESS-ONLY section today.")

        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()