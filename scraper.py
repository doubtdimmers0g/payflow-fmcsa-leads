import io
import pdfplumber
import requests
import re
from datetime import date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def sample_fmcsa_fitness_leads():
    print("Updated FITNESS-ONLY sampler - targeting Interstate common carrier blocks")

    today = date.today()
    dates_to_try = [today, today - timedelta(days=1)]
    found_entries = []
    target_phrase = "Interstate common carrier (except household goods)".lower()

    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    for d in dates_to_try:
        url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        print(f"Trying: {url}")

        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"No PDF for {d} (status {resp.status_code})")
                continue

            print(f"PDF downloaded for {d}")
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                full_text = "\n".join(page.extract_text() or "" for page in pdf.pages if page.extract_text())

            lines = [line.strip() for line in full_text.split('\n') if line.strip()]

            in_fitness = False
            in_block = False
            current_entry = {}
            idx = 0

            while idx < len(lines) and len(found_entries) < 10:
                line_lower = lines[idx].lower()

                # Enter FITNESS
                if "fitness" in line_lower and ("fitness-only" in line_lower or "motor common" in line_lower):
                    in_fitness = True
                    print("Entered FITNESS section")
                    idx += 1
                    continue

                if not in_fitness:
                    idx += 1
                    continue

                # Start/End block
                if target_phrase in line_lower:
                    if current_entry:
                        # Save previous if valid
                        if current_entry.get("mc") and current_entry.get("name") and current_entry.get("tel"):
                            found_entries.append(current_entry.copy())
                            print(f"Added valid: {current_entry['mc']} - {current_entry['name']}")
                    in_block = True
                    current_entry = {"authority": target_phrase}
                    print(f"New block start: {lines[idx]}")
                    idx += 1
                    continue

                if in_block and ("interstate" in line_lower or "fitness" in line_lower or len(line_lower) < 5):
                    # End block
                    if current_entry.get("mc") and current_entry.get("name") and current_entry.get("tel"):
                        found_entries.append(current_entry.copy())
                    in_block = False
                    current_entry = {}
                    idx += 1
                    continue

                if not in_block:
                    idx += 1
                    continue

                # Parse entry parts
                # MC start
                mc_match = re.search(r'(MC-\d{5,8}(?:-[A-Z])?)', lines[idx])
                if mc_match:
                    if current_entry.get("mc"):  # Save prev if open
                        if current_entry.get("tel"):
                            found_entries.append(current_entry.copy())
                    current_entry = {"mc": mc_match.group(1), "authority": target_phrase}
                    idx += 1
                    continue

                # Tel (strict)
                tel_match = re.search(r'(?:tel|phone):?\s*(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', lines[idx], re.I)
                if tel_match:
                    tel_raw = tel_match.group(1)
                    tel_clean = re.sub(r'[\s().-]', '', tel_raw)
                    if len(tel_clean) == 10:
                        formatted = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"
                        current_entry["tel"] = formatted
                    idx += 1
                    continue

                # Date mm/dd/yyyy
                date_match = re.search(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', lines[idx])
                if date_match and not current_entry.get("date"):
                    current_entry["date"] = date_match.group(1)
                    idx += 1
                    continue

                # Location: CITY, ST or CITY STATE ZIP pattern
                loc_match = re.search(r'([A-Z\s]+(?:[A-Z]{2}|\d{5}(?:-\d{4})?))$', lines[idx].upper())
                if loc_match and len(lines[idx].split()) <= 5 and not current_entry.get("location"):
                    current_entry["location"] = lines[idx].strip()
                    idx += 1
                    continue

                # Name: default to next substantial line after MC
                if current_entry.get("mc") and not current_entry.get("name") and len(lines[idx]) > 10 and not tel_match and not date_match:
                    name_candidate = lines[idx].strip()
                    if not re.search(r'\d{5}', name_candidate):  # skip pure ZIPs
                        current_entry["name"] = name_candidate
                    idx += 1
                    continue

                idx += 1

            # Save last entry
            if current_entry.get("mc") and current_entry.get("name") and current_entry.get("tel"):
                found_entries.append(current_entry.copy())

            if found_entries:
                print("\nCleaned sample 10 leads (prioritized with Tel):")
                for i, e in enumerate(found_entries[:10], 1):
                    print(f"{i}. MC: {e.get('mc', 'N/A')}")
                    print(f"   Name: {e.get('name', 'N/A')}")
                    print(f"   Location: {e.get('location', 'N/A')}")
                    print(f"   Tel: {e.get('tel', 'N/A')}")
                    print(f"   Date: {e.get('date', 'N/A')}")
                    print(f"   Authority: {e['authority']}")
                    print("-" * 60)
                break

            else:
                print("No valid entries with Tel found this run")

        except Exception as e:
            print(f"Error on {d}: {str(e)}")
            continue

    if not found_entries:
        print("No usable leads across dates. Debug: add print(lines[idx-5:idx+5]) around MC matches.")

if __name__ == "__main__":
    sample_fmcsa_fitness_leads()
