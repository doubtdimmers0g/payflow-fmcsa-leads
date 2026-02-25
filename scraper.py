import requests
import re
import os
import json
from datetime import date, timedelta
from google.oauth2.service_account import Credentials
import gspread
from bs4 import BeautifulSoup
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
    
    # Get selection page to find recent dates
    selection_url = "https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list"
    resp = session.get(selection_url, timeout=30)
    soup = BeautifulSoup(resp.text, 'html.parser')
    print("Selection page snippet:", resp.text[:2000])
    print("Selection page loaded")
    
    detail_links = [a['href'] for a in soup.find_all('a', href=True) if 'pd_date' in a['href'] or 'reg_detail' in a['href']]
    for a in soup.find_all('a', href=True):
        if 'prc_reg_detail' in a['href']:
            detail_links.append(a['href'])
    print("Found", len(detail_links), "detail links")
   
    # Scrape the latest 7 detail pages
    for link in detail_links[:7]:
        if not link.startswith('http'):
            link = 'https://li-public.fmcsa.dot.gov/LIVIEW/' + link
        print("Processing link:", link)
        try:
            detail_resp = session.get(link, timeout=30)
            soup = BeautifulSoup(detail_resp.text, 'html.parser')
            print("Detail page loaded, text length:", len(str(soup)))
            
            # GRANT DECISION NOTICES
            grant_heading = soup.find(string=re.compile('GRANT DECISION NOTICES', re.I))
            print("Grant heading found:", bool(grant_heading))
            if grant_heading:
                grant_div = grant_heading.find_parent('div') or grant_heading.find_parent('table') or grant_heading.find_parent('p')
                if grant_div:
                    grant_text = str(grant_div)
                    print("Grant text snippet:", grant_text[:500])
                    entries = re.findall(r"(MC-\d{6,7})\s+([\d/]+)\s+(.+?)(?=\nMC-|\n[A-Z ]+:|$)", grant_text, re.DOTALL | re.IGNORECASE)
                    print("Grant entries found:", len(entries))
                    for mc, idate, raw in entries:
                        print("Found MC:", mc)
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
        except Exception as e:
            print("Error processing link:", str(e))
            continue
    
    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")
        print(f"Added {len(new_rows)} new grant MCs to Google Sheet.")
    else:
        print("No new grant decisions today.")

if __name__ == "__main__":
    scrape_fmcsa_actives()