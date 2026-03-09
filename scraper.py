import requests
from datetime import date
from bs4 import BeautifulSoup
import re
import time

def fmcsa_html_detail_leads():
    print("HTML Detail scraper: Targets today's register via POST form")

    today = date.today()
    pd_date = today.strftime('%d-%b-%y').upper()  # e.g., 09-MAR-26
    print(f"Using pd_date: {pd_date}")

    session = requests.Session()

    # Step 1: Fetch selection page to mimic browser (optional, but good for headers)
    selection_url = "https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list"
    session.get(selection_url)  # sets any cookies if needed

    # Step 2: POST to get HTML Detail
    detail_url = "https://li-public.fmcsa.dot.gov/LIVIEW/pkg_register.prc_reg_detail"
    post_data = {"pd_date": pd_date}

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        print(f"Attempt {attempt}/{max_attempts} to get HTML Detail...")
        try:
            resp = session.post(detail_url, data=post_data, timeout=30)
            print(f"  Status: {resp.status_code}")

            if resp.status_code != 200:
                print("  Not ready - waiting 60s...")
                time.sleep(60)
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            content = soup.get_text(separator='\n', strip=True)

            if len(content) < 5000:
                print("  Content too short - retrying...")
                time.sleep(60)
                continue

            print("  HTML Detail loaded! Extracting target authority blocks...")

            # Find sections with exact phrases
            authority_phrases = [
                "Interstate common carrier (except household goods)",
                "Interstate contract carrier (except household goods)"
            ]

            lines = [line for line in content.split('\n') if line.strip()]
            found_entries = []
            in_block = False
            current_authority = None

            for line in lines:
                if any(phrase in line for phrase in authority_phrases):
                    in_block = True
                    current_authority = line.strip()
                    continue

                if not in_block:
                    continue

                # MC line
                mc_match = re.search(r'(MC-180\d{4,5}(?:-[A-Z])?)', line)
                if mc_match:
                    mc = mc_match.group(1)

                    # Name: next line(s)
                    name = ""
                    tel = ""
                    location = "N/A"
                    for i in range(1, 10):  # scan ahead
                        next_line_idx = lines.index(line) + i
                        if next_line_idx >= len(lines):
                            break
                        next_line = lines[next_line_idx]

                        if "Tel:" in next_line:
                            tel_match = re.search(r'Tel:\s*(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})', next_line, re.I)
                            if tel_match:
                                tel_clean = re.sub(r'[\s().-]', '', tel_match.group(1))
                                if len(tel_clean) == 10:
                                    tel = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"
                            break  # stop at Tel

                        if len(next_line) > 10 and not "Tel:" in next_line and not mc in next_line:
                            if not name:
                                name = next_line.strip()
                            elif "," in next_line or re.search(r'\d{5}', next_line):
                                location = next_line.strip()

                    entry = {
                        "mc": mc,
                        "name": name,
                        "location": location,
                        "tel": tel,
                        "authority": current_authority
                    }

                    if tel and mc.startswith("MC-18"):
                        found_entries.append(entry)
                        print(f"Added: {mc} - {name[:60]}... Tel: {tel}")

                    if len(found_entries) >= 10:
                        break

            if found_entries:
                print("\n=== SAMPLE 10 LEADS (exact authority phrases, HTML Detail) ===")
                for i, e in enumerate(found_entries[:10], 1):
                    print(f"{i}. MC: {e['mc']}")
                    print(f"   Name: {e['name']}")
                    print(f"   Location: {e['location']}")
                    print(f"   Tel: {e['tel']}")
                    print(f"   Authority: {e['authority']}")
                    print("-" * 60)
                return
            else:
                print("  No matching entries in HTML Detail - check if phrases present.")

        except Exception as e:
            print(f"  Error: {str(e)}")
            time.sleep(60)

    print("Failed to get HTML Detail. PDF fallback or wait longer.")

if __name__ == "__main__":
    fmcsa_html_detail_leads()
