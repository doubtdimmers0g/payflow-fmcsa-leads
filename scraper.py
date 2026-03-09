import io
import pdfplumber
import requests
import re
import time
from datetime import date
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def sample_fmcsa_fitness_leads_today_only():
    print("Scraper: ONLY tries TODAY's date repeatedly until live | MC-180xxxx+ filter")

    today = date.today()
    date_str = today.strftime('%Y%m%d')
    url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{date_str}.PDF"
    print(f"Targeting today's PDF: {url}")

    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        print(f"Attempt {attempt}/{max_retries}...")
        try:
            resp = session.get(url, timeout=30)
            print(f"  Status: {resp.status_code}")

            if resp.status_code != 200:
                print("  Not ready yet (non-200). Waiting 60s before retry...")
                time.sleep(60)
                continue

            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                # Focus on later pages (FITNESS + new grants)
                start_page = max(0, len(pdf.pages) - 60)
                text_pages = pdf.pages[start_page:]
                full_text = "\n".join(page.extract_text() or "" for page in text_pages if page.extract_text())

            if len(full_text) < 5000:
                print("  Content too short - likely incomplete PDF. Retrying...")
                time.sleep(60)
                continue

            print("  PDF loaded successfully! Extracting...")

            # Regex updated to MC-180xxxx+ only
            pattern = re.compile(
                r'(MC-180\d{4,5}(?:-[A-Z])?)\s+'
                r'(\d{2}/\d{2}/\d{4})\s+'
                r'(.+?)\s+'
                r'(?:[A-Z\s,]+[A-Z]{2}\s*\d{5}(?:-\d{4})?)?\s*'
                r'Tel:\s*(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})',
                re.IGNORECASE | re.DOTALL | re.MULTILINE
            )

            matches = pattern.findall(full_text)
            print(f"  Raw matches found: {len(matches)}")

            found_entries = []
            seen_mcs = set()  # dedupe

            for mc, dec_date, raw_name, tel_raw in matches:
                if mc in seen_mcs:
                    continue
                seen_mcs.add(mc)

                # Clean name
                name = re.sub(r'\s+', ' ', raw_name.strip())
                name = re.sub(r'^\d+\s+[A-Z].*?(?:ST|AVE|RD|DR|LN|BLVD|WAY|CT|PL|DRIVE|BLDG|APT|SUIT|STE)\s+.*', '', name, flags=re.I)
                name = re.sub(r'\s+\d+\s+[A-Z].*$', '', name).strip()  # cut trailing address
                if len(name) < 12:
                    continue

                # Clean Tel
                tel_clean = re.sub(r'[\s().-]', '', tel_raw)
                if len(tel_clean) != 10:
                    continue
                tel = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"

                # Location
                loc_start = full_text.find(mc)
                loc_snippet = full_text[loc_start:loc_start+500]
                loc_match = re.search(r'([A-Z][A-Za-z\s]+(?:[A-Z]{2}|\d{5}(?:-\d{4})?)\s*\d{5}(?:-\d{4})?)', loc_snippet, re.I)
                location = loc_match.group(1).strip() if loc_match else "N/A"

                entry = {
                    "mc": mc,
                    "name": name,
                    "location": location,
                    "tel": tel,
                    "date": dec_date
                }

                found_entries.append(entry)
                print(f"  Added: {mc} - {name[:60]}... Tel: {tel}")

                if len(found_entries) >= 10:
                    break

            if found_entries:
                print("\n=== SAMPLE 10 LEADS (MC-180xxxx+ with Tel) ===")
                for i, e in enumerate(found_entries[:10], 1):
                    print(f"{i}. MC: {e['mc']}")
                    print(f"   Name: {e['name']}")
                    print(f"   Location: {e['location']}")
                    print(f"   Tel: {e['tel']}")
                    print(f"   Date: {e['date']}")
                    print("-" * 60)
                return  # Success
            else:
                print("  No valid MC-180xxxx+ entries found (parsing or no new grants today).")

        except Exception as e:
            print(f"  Error: {str(e)}. Retrying...")
            time.sleep(60)
            continue

    print(f"Failed after {max_retries} attempts. PDF likely delayed. Try again in 30-60 min.")

if __name__ == "__main__":
    sample_fmcsa_fitness_leads_today_only()
