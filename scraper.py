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
    SHEET_ID = os.environ['SHEET_ID']
    creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).worksheet("Sheet1")
    
    existing_data = sheet.get_all_records()
    existing_mcs = {row['mc_number'] for row in existing_data if 'mc_number' in row}
    
    today = date.today()
    new_rows = []
    
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # Get selection page to find recent dates
    selection_url = "https://li-public.fmcsa.dot.gov/LIVIEW/PKG_REGISTER.prc_reg_list"
    resp = session.get(selection_url, timeout=30)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    detail_links = []
    for a in soup.find_all('a', href=True):
        if 'prc_reg_detail' in a['href']:
            detail_links.append(a['href'])
    
    # Scrape the latest 7 detail pages
    for link in detail_links[:7]:
        if not link.startswith('http'):
            link = 'https://li-public.fmcsa.dot.gov/LIVIEW/' + link
        try:
            detail_resp = session.get(link, timeout=30)
            soup = BeautifulSoup(detail_resp.text, 'html.parser')
            print("Found detail page, full text length:", len(str(soup)))
            
            # GRANT DECISION NOTICES (your original ask)
            grant_section = soup.find('a', id='grant') or soup.find(string=re.compile('GRANT DECISION NOTICES', re.I))
            print("Grant section found, entries:", len(entries))
            if grant_section:
                grant_text = grant_section.find_parent('div') or grant_section.find_parent('table') or str(soup)
                entries = re.findall(r"(MC-\d{6,7})\s+([\d/]+)\s+(.+?)(?=\nMC-|\n[A-Z ]+:|$)", grant_text, re.DOTALL | re.IGNORECASE)
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
        except:
            continue
    
    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")
        print(f"Added {len(new_rows)} new grant MCs to Google Sheet.")
    else:
        print("No new grant decisions today.")

if __name__ == "__main__":
    scrape_fmcsa_actives()