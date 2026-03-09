import io
import pdfplumber
import requests
import re
import os
from datetime import date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def sample_fmcsa_fitness_leads():
    print("Script started - sampling 10 FITNESS-ONLY Interstate common carrier leads")

    today = date.today()
    dates_to_try = [today, today - timedelta(days=1)]
    found_entries = []
    target_authority = "Interstate common carrier (except household goods)"

    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    for d in dates_to_try:
        url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        print(f"Trying URL: {url}")

        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"PDF for {d} not available (status {resp.status_code})")
                continue

            print(f"Downloaded PDF for {d}")
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

            lines = [line.strip() for line in full_text.split('\n') if line.strip()]

            in_fitness = False
            in_target_authority = False
            idx = 0

            while idx < len(lines) and len(found_entries) < 10:
                line = lines[idx].lower()

                # Detect start of FITNESS section
                if "fitness" in line and ("fitness-only" in line or "motor common" in line):
                    in_fitness = True
                    print("Entered FITNESS section")
                    idx += 1
                    continue

                if not in_fitness:
                    idx += 1
                    continue

                # Check for target authority phrase
                if target_authority.lower() in line:
                    in_target_authority = True
                    print(f"Found target authority block: {lines[idx]}")
                    idx += 1
                    continue

                if in_target_authority:
                    # Look for MC- line to start a new entry
                    mc_match = re.match(r'(MC-\d{5,8}(?:-[A-Z])?)', lines[idx])
                    if mc_match:
                        mc = mc_match.group(1)

                        # Name: usually next line
                        name = lines[idx + 1] if idx + 1 < len(lines) else ""

                        # City/State: often next or after name
                        location = ""
                        tel = ""
                        entry_date = ""

                        # Scan ahead up to 10 lines for location, tel, date
                        for k in range(idx + 1, min(idx + 15, len(lines))):
                            l = lines[k]

                            # Tel:
                            if re.search(r'tel:|phone:', l, re.I):
                                tel = l.strip()
                                break  # stop early if tel found

                            # Date (mm/dd/yyyy or similar)
                            date_match = re.search(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', l)
                            if date_match:
                                entry_date = date_match.group(1)

                            # Location: look for city-like patterns (e.g., CITY, ST or full addr)
                            if ',' in l and len(l.split()) <= 4 and not tel and not date_match:
                                location = l.strip()

                        # Clean up
                        if tel:
                            tel = re.sub(r'(tel:|phone:|\(|\)|\-|\s+)', '', tel, flags=re.I).strip()
                            if len(tel) == 10:
                                tel = f"({tel[:3]}) {tel[3:6]}-{tel[6:]}"

                        entry = {
                            "mc": mc,
                            "name": name.strip(),
                            "location": location.strip(),
                            "tel": tel,
                            "date": entry_date or d.strftime('%m/%d/%Y'),
                            "authority": target_authority
                        }

                        # Only add if we have MC and name
                        if entry["name"]:
                            found_entries.append(entry)
                            print(f"Added entry {len(found_entries)}: {mc} - {name}")

                        idx += 3  # skip ahead a bit to avoid overlap
                    else:
                        idx += 1

                else:
                    idx += 1

            if found_entries:
                print("\nSample 10 FITNESS-ONLY leads (or fewer):")
                for i, e in enumerate(found_entries, 1):
                    print(f"{i}. MC: {e['mc']}")
                    print(f"   Name: {e['name']}")
                    print(f"   Location: {e['location'] or 'N/A'}")
                    print(f"   Tel: {e['tel'] or 'N/A'}")
                    print(f"   Date: {e['date']}")
                    print(f"   Authority: {e['authority']}")
                    print("-" * 60)
                break  # success, stop trying earlier dates
            else:
                print("No matching entries found in this PDF")

        except Exception as e:
            print(f"Error processing {d}: {str(e)}")
            continue

    if not found_entries:
        print("No leads found across tried dates.")

if __name__ == "__main__":
    sample_fmcsa_fitness_leads()
