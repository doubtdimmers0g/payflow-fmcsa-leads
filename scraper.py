import io
import pdfplumber
import requests
import re
import os
import json
from datetime import date, timedelta
from google.oauth2.service_account import Credentials
import gspread
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def scrape_fmcsa_actives():
    print("Script started")
    SHEET_ID = os.environ['SHEET_ID']
    creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    print("Credentials loaded")
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).worksheet("Sheet1")
    print("Sheet opened")
    
    existing_data = sheet.get_all_records()
    existing_mcs = {row['mc_number'] for row in existing_data if 'mc_number' in row}
    
    today = date.today()
    new_rows = []
    
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    print("Session created")
    
    for i in range(30):
        d = today - timedelta(days=i)
        url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        print("Trying URL:", url)
        
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                print("Downloaded PDF for", d)
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    full_text = "".join(page.extract_text() or "" for page in pdf.pages)
                
                # GRANT DECISION NOTICES
                grant_match = re.search(r"GRANT DECISION NOTICES:(.*?)(?=NAME CHANGES|REVOCATION|DISMISSALS|NON-FITNESS|DECISIONS AND NOTICES|$)", 
                                        full_text, re.DOTALL | re.IGNORECASE)
                if grant_match:
                    section = grant_match.group(1)
                    lines = [line.strip() for line in section.split('\n') if line.strip()]
                    print(f"DEBUG {d}: GRANT section found — {len(lines)} lines")
                    print("Sample first 20 lines:", [repr(l) for l in lines[:20]])
                    idx = 0
                    while idx < len(lines):
                        if re.match(r'MC-\d{6,7}', lines[idx]):
                            print(f"DEBUG {d} MC match: {lines[idx]}")
                            print("  Next 5 lines:", [repr(l) for l in lines[idx+1:idx+6]])
                            mc = lines[idx].strip()
                            if mc in existing_mcs:
                                idx += 1
                                continue
                            # Grab next few lines for company
                            company_raw = ' '.join(lines[idx+1:idx+5])[:250] if idx+1 < len(lines) else ''
                            company = re.sub(r'\s+', ' ', company_raw.strip())
                            # Date fallback
                            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', ' '.join(lines[idx:idx+8]))
                            idate = date_match.group(1) if date_match else d.strftime('%m/%d/%Y')
                            
                            new_rows.append([
                                today.strftime('%Y-%m-%d'),
                                idate,
                                mc,
                                company,
                                ' '.join(lines[idx:idx+12])[:500],  # more raw context
                                "",  # called_status
                                ""   # notes
                            ])
                            print("Found new MC:", mc, company)
                            idx += 4  # safe skip for multi-line entries
                        else:
                            idx += 1
        except Exception as e:
            print("Error for", d, ":", str(e))
            continue
              
    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")
        print(f"Added {len(new_rows)} new grant MCs to Google Sheet.")
    else:
        print("No new grant decisions today.")

if __name__ == "__main__":
    scrape_fmcsa_actives()