import csv
import time
import requests
from pprint import pprint
from argparse import ArgumentParser
from utils import backup, get_credentials

"""

Generate a report and then pass it as the -d argument.  Ensure columns mediaid and import_guid are present
in the csv file.  This script will look for duplicate import_guids and remove one.

Usage:
    python delete_duplicates.py -d PATH_TO_REPORT.csv
"""
SECRET, SITE_ID = get_credentials()

HEADERS = {"Accept": "application/json", "Authorization": SECRET}
MEDIA_FILE = 'media-list.json'

parser = ArgumentParser()
parser.add_argument("-d", dest="delete", default="", help="CSV file with files to delete")

args = parser.parse_args()
media_list = args.delete

def has_dups(assets, guid):
    count = 0
    for a in assets:
        meta = a['metadata']
        cust = meta['custom_params']
        if "import_guid" not in cust: continue

        if cust['import_guid'] == guid: count+=1
    
    if count >= 2:
        return True
    else:
        return False

def check_response(res):
    if res.status_code >= 400:
        data = res.json()
        for e in data['errors']:
            if e['code'] == "rate_limit_exceeded": 
                print(f"Rate limit exceeded.  Cooling down for 1min before retrying")
                time.sleep(60)
                return False
    
    print("ok")
    return True

def delete(media_id, retry=0):
    url = f"https://api.jwplayer.com/v2/sites/{SITE_ID}/media/{media_id}/"

    res = requests.delete(url, headers=HEADERS)
    
    if check_response(res) == False:
        if retry > 5: return

        delete(media_id, retry+1)


def start(csv_file):
    print(csv_file)
    assets, fn_backup = backup(SITE_ID, SECRET)
    f = open(csv_file, newline="")

    for row in csv.DictReader(f):
        guid = row['import_guid']
        mid = row['mediaid']

        if has_dups(assets, guid):
            #delete
            print(guid, mid)
            delete(mid)

start(media_list)