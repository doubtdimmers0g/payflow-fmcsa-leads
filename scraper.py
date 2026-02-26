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
    
    dates_to_try = [today, today - timedelta(days=1)]
    for d in dates_to_try:
        url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        print("Trying URL:", url)
        
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                print("Downloaded PDF for", d)
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    full_text = "".join(page.extract_text() or "" for page in pdf.pages)
                
                # LINE-BY-LINE ON GRANT SECTION: Skips boilerplate, pulls MC/applicant/rep/tel from blocks
                print(f"DEBUG {d}: Scanning grant section line-by-line...")
                grant_match = re.search(r"GRANT DECISION NOTICES", full_text, re.IGNORECASE)
                if grant_match:
                    grant_text = full_text[grant_match.end():]
                    lines = [line.strip() for line in grant_text.split('\n') if line.strip()]
                    idx = 0
                    found_count = 0
                    seen_mcs_this_run = set()
                    while idx < len(lines):
                        if re.match(r'MC-\d{5,8}', lines[idx]):
                            mc = lines[idx].strip()
                            if mc in existing_mcs or mc in seen_mcs_this_run:
                                idx += 1
                                continue
                            seen_mcs_this_run.add(mc)
                            
                            # Applicant name: next line after MC
                            applicant = lines[idx+1] if idx+1 < len(lines) else ''
                            
                            # Rep name and tel: look for 'Tel:' line
                            rep = ''
                            tel = ''
                            for k in range(idx+1, min(idx+10, len(lines))):
                                if 'Tel:' in lines[k]:
                                    tel = lines[k].strip()
                                    rep = lines[k-1] if k-1 > idx else ''
                                    break
                            
                            # Date from nearby line
                            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', ' '.join(lines[idx:idx+10]))
                            idate = date_match.group(1) if date_match else d.strftime('%m/%d/%Y')
                            
                            new_rows.append([
                                today.strftime('%Y-%m-%d'),
                                idate,
                                mc,
                                applicant[:250],
                                rep,
                                tel,
                                ""
                            ])
                            print(f"Found new MC: {mc} | Applicant: {applicant} | Rep: {rep} | Tel: {tel}")
                            found_count += 1
                            idx += 5  # skip ahead
                        else:
                            idx += 1
                    print(f"DEBUG {d}: {found_count} new MCs added from grant lines")
                else:
                    print(f"DEBUG {d}: No GRANT section found")
                break  # success — stop trying earlier dates
            else:
                print(f"PDF for {d} not available yet")
                continue
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