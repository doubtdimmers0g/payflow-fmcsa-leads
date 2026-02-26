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
                    print(f"DEBUG {d}: Extracting grant tables...")
                    found_count = 0
                    seen_mcs_this_run = set()
                    grant_started = False
                    
                    for page in pdf.pages:
                        text = page.extract_text() or ''
                        if "GRANT DECISION NOTICES" in text.upper():
                            grant_started = True
                        if not grant_started:
                            continue
                        
                        tables = page.extract_tables()
                        print(f"DEBUG page {page.page_number}: {len(tables)} tables found")
                        for table in tables:
                            if not table or len(table) < 2:
                                continue
                            header = [str(cell or '').strip().upper() for cell in table[0]]
                            print(f"DEBUG table headers: {header}")  # add this for now
                            if not any('NUMBER' in h for h in header):
                                continue  # Only grant tables
                            
                            for row in table[1:]:  # skip header
                                if not row or len(row) < 1:
                                    continue
                                number = str(row[0] or '').strip()
                                if not number.startswith('MC-'):
                                    continue
                                mc = number
                                if mc in existing_mcs or mc in seen_mcs_this_run:
                                    continue
                                seen_mcs_this_run.add(mc)
                                
                                filed = str(row[1] or '').strip()
                                applicant = str(row[2] or '').replace('\n', ' ').strip() if len(row) > 2 else ''
                                representative = str(row[3] or '').replace('\n', ' ').strip() if len(row) > 3 else ''
                                
                                new_rows.append([
                                    today.strftime('%Y-%m-%d'),
                                    filed,
                                    mc,
                                    applicant[:250],
                                    representative,
                                    "",
                                    ""
                                ])
                                print(f"Found new MC: {mc} | Applicant: {applicant[:100]}... | Rep: {representative[:100]}...")
                                found_count += 1
                    
                    print(f"DEBUG {d}: {found_count} new MCs added from grant tables")
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