import csv
import re
import sys
import requests
import dateutil.parser as parser
from argparse import ArgumentParser
from utils import check_response, convert_pubdate, get_credentials, backup
"""
Adds validitywindow to assets.  
The priority of dates are searched in these fields:
1. tags
2. dcterms_valid
3. dcterms
4. publish start and end date

After finding the start and end dates, dates are applied to both the validitywindow custom 
fields and publish and start date.

Usage: python add_validitywindow.py -p <PROPERTY ID> -s <V2 API SECRET>
"""

aparser = ArgumentParser()
aparser = get_credentials(aparser)
args = aparser.parse_args()
SECRET = args.secret
PROP_ID = args.propertyid

# ADD LIST OF REPORT FIELDS HERE
LIST_OF_FIELDS = ["providerId", "mediaid", "title", "hosting_type", "status", "productionType", "validitywindow", 
                    "dcterms_valid", "pubDate", "publish_start_date", "publish_end_date", "seriesId", "import_guid",
                    "episodic_landscape_url", "poster_landscape_url", "poster_portrait_url"]

HEADERS = {"Accept": "application/json", "Authorization": SECRET}

def get_isoformat(text):
    date = parser.parse(text)
    return date.isoformat()

def check_validitywindow(t):
    date_start = ""
    date_end = ""
    s = re.search(r"(?<=start=)[0-9-T:.+A-Z]+(?=;)", t)
    if s: 
        s = s.group()
        date_start = get_isoformat(s)


    e = re.search(r"(?<=end=)[0-9-T:.+A-Z]+(?=;)", t)
    if e:
        e = e.group()
        date_end = get_isoformat(e)
    
    return date_start, date_end

def get_pub_dates(asset):
    date_start = ""
    date_end = ""
    meta = asset['metadata']
    custom = meta['custom_params']
    tags = meta['tags']

    # check validitywindow tag
    for t in tags:
        if "validitywindow" in t:
            s,e = check_validitywindow(t)
            if s or e:
                date_start = s
                date_end = e
                break
        if "start=" in t and "end=" in t:
            s,e = check_validitywindow(t)
            if s or e:
                date_start = s
                date_end = e
                break

    if date_start and date_end:
        return date_start, date_end

    # check dcterms_valid
    if "dcterms_valid" in custom:
        t = custom['dcterms_valid']
        s,e = check_validitywindow(t)
        if s or e:
            date_start = s
            date_end = e

    if "dcterms" in custom:
        t = custom['dcterms']
        s,e = check_validitywindow(t)
        if s or e:
            date_start = s
            date_end = e

    # check publish dates
    s = meta['publish_start_date']
    e = meta['publish_end_date']

    if s: date_start = s
    if e: date_end = e

    return date_start, date_end

def update_asset(asset, start, end, retry=0):
    if retry > 5: 
        print(f'too many attempts... skipping {asset["id"]}')
        return

    dcterms_valid = f"start={start};end={end};scheme=W3C-DTF"
    meta = asset['metadata']
    cust = meta['custom_params']
    
    cust['validitywindow'] = dcterms_valid

    media_id = asset['id']

    payload = {
        "metadata":{
            "publish_start_date":start,
            "publish_end_date":end,
            "custom_params": cust
        }
    }

    url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{media_id}/"

    res = requests.patch(url, json=payload, headers=HEADERS)

    if check_response(res) == False:
        retry += 1
        update_asset(asset, start, end, retry)

def get_publishdate(asset):
    meta = asset['metadata']
    cust = meta['custom_params']

    if "publish_start_date" in meta:
        psd = meta["publish_start_date"]
        return convert_pubdate(psd)

def update_pub_dates(assets):
    count = 1
    confirm = "c"
    for a in assets:
        pub_date = ""
        #skip series cards
        if "series_card" in a['metadata']['tags']: continue

        meta = a['metadata']
        cust = meta['custom_params']

        # this probably already has a valid validitywindow
        if "validitywindow" in cust and ";scheme=W3C-DTF" in cust['validitywindow'] \
            and meta['publish_end_date'] and meta['publish_start_date']: continue

        start, end = get_pub_dates(a)

        if start == "" or end == "": continue

        print(a['id'], start, end)
        if "pubDate" not in a['metadata']['custom_params']:
            pub_date, year = get_publishdate(a)
            a['metadata']['custom_params']['pubDate'] = pub_date

        if confirm == "c":
            confirm = input(f"Confirm the above. \nType in an option:\n\tContinue (c)\n\tExit (x)\n\tProcess All (a)\n(c,x,a):").lower()

            if confirm not in ["c","x","a"]: confirm == "x"

        if confirm in ["c","a"]: update_asset(a, start, end)

        if confirm == "x": sys.exit("Exiting...")

all_assets, fn_backup = backup(PROP_ID, SECRET)
update_pub_dates(all_assets)