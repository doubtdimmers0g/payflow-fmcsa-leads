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
    
    for i in range(1):  # change to 30 after test
        d = today - timedelta(days=i)
        url = f"https://li-public.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        print("Trying URL:", url)
        
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                print("Downloaded PDF for", d)
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    full_text = "".join(page.extract_text() or "" for page in pdf.pages)
                
                # RESTRICTED TO GRANT SECTION: Skip boilerplate/other sections, focus on detailed grants after header
                print(f"DEBUG {d}: Scanning GRANT section for MC entries...")
                grant_match = re.search(r"GRANT DECISION NOTICES", full_text, re.IGNORECASE)
                if grant_match:
                    # Start from after header (boilerplate is first, then the list)
                    grant_text = full_text[grant_match.end():]
                    
                    mc_matches = re.finditer(r'(MC-\d{5,8}[A-Z]?)', grant_text, re.IGNORECASE)
                    
                    found_count = 0
                    seen_mcs_this_run = set()
                    for match in mc_matches:
                        mc = match.group(1).upper()
                        if mc in existing_mcs or mc in seen_mcs_this_run:
                            continue
                        seen_mcs_this_run.add(mc)
                        
                        # Context from grant_text only
                        start = max(0, match.start() - 150)
                        end = min(len(grant_text), match.end() + 400)
                        context = grant_text[start:end]
                        
                        # Company extraction
                        company_match = re.search(r'\b' + re.escape(mc) + r'\b\s*[:\-]?\s*([A-Z][A-Za-z0-9&\'\.\-\s/]{8,120}?)', context)
                        company = company_match.group(1).strip() if company_match else "Unknown Company"
                        company = re.sub(r'\s+', ' ', company)[:250]
                        
                        # Date
                        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', context)
                        idate = date_match.group(1) if date_match else d.strftime('%m/%d/%Y')
                        
                        new_rows.append([
                            today.strftime('%Y-%m-%d'),
                            idate,
                            mc,
                            company,
                            re.sub(r'\s+', ' ', context.strip())[:600],
                            "",
                            ""
                        ])
                        print(f"Found new MC: {mc} | {company} | Date: {idate}")
                        found_count += 1
                    
                    print(f"DEBUG {d}: {found_count} new MCs added from GRANT section")             
                else:
                    print(f"DEBUG {d}: No GRANT section found")

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