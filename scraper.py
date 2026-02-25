import requests
import pdfplumber
import re
import pandas as pd
import os
import json
from datetime import date, timedelta
from google.oauth2.service_account import Credentials
import gspread

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def scrape_fmcsa_actives():
    SHEET_ID = os.environ['SHEET_ID']
    creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).worksheet("Sheet1")  # or rename tab to "Leads"
    
    # Load existing MCs for dedup
    existing_data = sheet.get_all_records()
    existing_mcs = {row['mc_number'] for row in existing_data if 'mc_number' in row}
    
    today = date.today()
    new_rows = []
    
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    for i in range(2):
        d = today - timedelta(days=i)
        url = f"https://li.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                break
        except:
            resp = None
        if resp and resp.status_code == 200:
            break
    else:
        print("Could not download any PDF")
        return
    
    with pdfplumber.open(resp.content) as pdf:
        full_text = "".join(page.extract_text() or "" for page in pdf.pages)
    
    # ACTIVE ones only
    cpl_section = re.search(r"CERTIFICATE, PERMIT, LICENSE:(.*?)(?=\n[A-Z ]+[: ]|$)", 
                          full_text, re.DOTALL | re.IGNORECASE)
    if not cpl_section:
        print("No CPL section found")
        return
        
    entries = re.findall(r"(MC-\d{6,7})\s+([\d/]+)\s+(.+?)(?=\nMC-|\n[A-Z ]+:|$)", 
                       cpl_section.group(1), re.DOTALL)
    
    for mc, idate, raw in entries:
        if mc in existing_mcs:
            continue
        company = re.sub(r'\s+', ' ', raw.strip()[:250])
        new_rows.append([
            today.strftime('%Y-%m-%d'),
            idate,
            mc,
            company,
            raw.strip()[:500],
            "",  # called_status
            ""   # notes
        ])
    
    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")
        print(f"Added {len(new_rows)} new active MCs to Google Sheet.")
    else:
        print("No new actives today.")

if __name__ == "__main__":
    scrape_fmcsa_actives()