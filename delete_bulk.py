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
    python delete_duplicates.py -d PATH_TO_REPORT.csv -s SECRET -p PROPERTY_ID
"""
parser = ArgumentParser()
parser = get_credentials(parser)
parser.add_argument("-d", dest="delete", default="", help="CSV file with files to delete")
args = parser.parse_args()
SECRET = args.secret
SITE_ID = args.propertyid

HEADERS = {"Accept": "application/json", "Authorization": SECRET}
MEDIA_FILE = 'media-list.json'



media_list = args.delete

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
    f = open(csv_file, newline="")

    for row in csv.DictReader(f):
        mid = row['mediaid']
        delete(mid)

start(media_list)