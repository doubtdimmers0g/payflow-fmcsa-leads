import requests
import pdfplumber
import re
import pandas as pd
from datetime import date, timedelta
import os

def scrape_fmcsa_actives():
    leads_file = 'active_leads.csv'
    today = date.today()
    new_leads = []
    
    for i in range(2):  # yesterday + today (covers weekends)
        d = today - timedelta(days=i)
        url = f"https://li.fmcsa.dot.gov/lihtml/rptspdf/LI_REGISTER{d.strftime('%Y%m%d')}.PDF"
        
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            continue
            
        with pdfplumber.open(resp.content) as pdf:
            full_text = "".join(page.extract_text() or "" for page in pdf.pages)
        
        # ACTIVE ones only - Certificate, Permit, License section
        cpl_section = re.search(r"CERTIFICATE, PERMIT, LICENSE:(.*?)(?=\n[A-Z ]+[: ]|$)", 
                              full_text, re.DOTALL | re.IGNORECASE)
        if not cpl_section:
            continue
            
        entries = re.findall(r"(MC-\d{6,7})\s+([\d/]+)\s+(.+?)(?=\nMC-|\n[A-Z ]+:|$)", 
                           cpl_section.group(1), re.DOTALL)
        
        for mc, idate, raw in entries:
            company = re.sub(r'\s+', ' ', raw.strip()[:250])
            new_leads.append({
                'scrape_date': today.strftime('%Y-%m-%d'),
                'grant_issue_date': idate,
                'mc_number': mc,
                'company': company,
                'raw_text': raw.strip()[:500]
            })
    
    if new_leads:
        df_new = pd.DataFrame(new_leads)
        
        if os.path.exists(leads_file):
            df_existing = pd.read_csv(leads_file)
            df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['mc_number'])
        else:
            df_combined = df_new
            
        df_combined.to_csv(leads_file, index=False)
        print(f"Added {len(new_leads)} new active MCs. Total now: {len(df_combined)}")
    else:
        print("No new actives today.")

if __name__ == "__main__":
    scrape_fmcsa_actives()
