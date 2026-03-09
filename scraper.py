import io
import pdfplumber
import requests
import re
from datetime import date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def sample_fmcsa_fitness_leads():
    print("FINAL column-aware FITNESS sampler (tuned to your screenshot layout)")

    today = date.today()
    dates_to_try = [today, today - timedelta(days=1)]
    found_entries = []
    target = "Interstate common carrier (except household goods)"

    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    for d in dates_to_try:
        url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        print(f"Trying {d}")

        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"PDF not ready")
                continue

            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                # Start from page 78+ where FITNESS lives + new entries
                pages = pdf.pages[78:]
                full_text = "\n".join(page.extract_text() or "" for page in pages)

            # Regex tuned to your screenshot: MC + Date + Name + Tel (handles column repeats)
            pattern = re.compile(
                r'(MC-(?:1[7-9]|2[0-9])\d{5,6}(?:-[A-Z])?)'
                r'(\d{2}/\d{2}/\d{4})\s+'
                r'(.+?)\s+'
                r'(?:[A-Z\s]+,?\s*[A-Z]{2}\s*\d{5})?\s*'  # optional location bleed
                r'Tel:\s*(\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4})',
                re.IGNORECASE | re.DOTALL
            )

            matches = pattern.findall(full_text)

            for mc, dec_date, raw_name, tel_raw in matches:
                # Clean name (remove address bleed and repeats)
                name = re.sub(r'\s+', ' ', raw_name.strip())
                name = re.sub(r'^\d+\s+[A-Z].*?ST\s+', '', name, flags=re.I)  # remove street fragments
                name = re.sub(r'\bLLC\b.*', 'LLC', name)  # trim long repeats

                # Clean Tel
                tel_clean = re.sub(r'[\s().-]', '', tel_raw)
                if len(tel_clean) == 10:
                    tel = f"({tel_clean[:3]}) {tel_clean[3:6]}-{tel_clean[6:]}"
                else:
                    continue  # skip bad phone

                # Location (look near the match)
                loc_match = re.search(r'([A-Z][A-Za-z\s,]+[A-Z]{2}\s*\d{5}(?:-\d{4})?)', full_text[full_text.find(mc):full_text.find(mc)+400])
                location = loc_match.group(1).strip() if loc_match else "N/A"

                entry = {
                    "mc": mc,
                    "name": name,
                    "location": location,
                    "tel": tel,
                    "date": dec_date,
                    "authority": target
                }

                if len(name) > 10 and tel:
                    found_entries.append(entry)
                    print(f"Added: {mc} - {name[:60]}...")

                if len(found_entries) >= 10:
                    break

            if found_entries:
                print("\n=== CLEAN SAMPLE 10 LEADS (ready for calls) ===")
                for i, e in enumerate(found_entries[:10], 1):
                    print(f"{i}. MC: {e['mc']}")
                    print(f"   Name: {e['name']}")
                    print(f"   Location: {e['location']}")
                    print(f"   Tel: {e['tel']}")
                    print(f"   Date: {e['date']}")
                    print("-" * 60)
                break

        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    sample_fmcsa_fitness_leads()
