import csv
import requests
from pprint import pprint
from argparse import ArgumentParser
from utils import get_credentials, backup
"""
Create a csv report of all assets.  
Declare report fields listed under LIST_OF_FIELDS.

Usage: python create_report.py
"""

aparser = ArgumentParser()
aparser = get_credentials(aparser)
args = aparser.parse_args()
SECRET = args.secret
PROP_ID = args.propertyid

# add list of fields here
LIST_OF_FIELDS = ["title", "status", "episodic_landscape_url", "hosting_type"]


limits = {"result_limit": 14, "result_offset": 0}
HEADERS = {"Accept": "application/json", "Authorization": SECRET}

def get_all_media(url, medias):
    res = requests.get(url)
    data = res.json()
    medias += data['playlist']
    if "next" in data['links']:
        url = data['links']['next']
        medias = get_all_media(url, medias)
    
    return medias

def create_csv(assets):
    f = open('./media-list.csv', "w")
    writer = csv.writer(f)
    header = LIST_OF_FIELDS
    header.insert(0,"mediaid")
    writer.writerow(header)

    for a in assets:
        row = []
        
        meta = a['metadata']
        params = meta["custom_params"]
        meta.update(params)
        a.update(meta)
        a['mediaid'] = a['id']
        
        for h in LIST_OF_FIELDS:
            if h in a:
                row.append(a[h])
            else:
                row.append("")
        writer.writerow(row)

all_assets, fn_backup = backup(PROP_ID, SECRET)
create_csv(all_assets)


