import sys
import csv
import json
import requests
from os.path import exists
from pprint import pprint
from argparse import ArgumentParser

from utils import check_response, get_credentials, backup
"""
Modifies media metadata found in CSV file. 
CSV column names must match metadata field names.  
This also reads the special column name "INVALID" with the values of "true" or "false".
When this value is false, it will remove the "invalid" tag from the media asset.
Usage:
    python update_metadata.py -s <SECRET> -p <PROPERTY ID> -f <CSV FILE>
"""


limits = {"result_limit": 14, "result_offset": 0}


parser = ArgumentParser()
parser.add_argument("-f", dest="file", default="", required=False, help="CSV source file.  Requires column for mediaid")
parser = get_credentials(parser)
args = parser.parse_args()
SECRET = args.secret
PROP_ID = args.propertyid

csv_file = args.file

HEADERS = {"Accept": "application/json", "Authorization": SECRET}

def get_all_media(url, medias):
    res = requests.get(url)
    data = res.json()
    medias += data['playlist']
    if "next" in data['links']:
        url = data['links']['next']
        medias = get_all_media(url, medias)
    
    return medias


def load_csv(f_path):
    if exists(f_path):
        f = open(f_path, newline="")

        assets = csv.DictReader(f)
        
        # get headerrows
        headers = assets.fieldnames
        
        return headers, assets
    else:
        sys.exit(f"{f_path} doesn't exist. Check file path and try again.")

def get_asset(mid, assets):
    """
    Get asset from backup
    """
    for a in assets:
        if a['id'] == mid: return a

def update_invalid_status(tags, status):
    if status.lower() == "false" and "invalid" in tags:
        tags.remove('invalid')

    if status.lower() == "false" and "Invalid" in tags:
        tags.remove('Invalid')

    if status.lower() == "true":
        tags.append("invalid")

    return tags

def update_metadata(src, target):
    meta = target['metadata']
    cust = meta['custom_params']
    tags = meta['tags']

    for s in src:
        if s == "": continue

        if s == 'INVALID': 
            tags = update_invalid_status(tags, src[s])
        else:
            if s in ['title', 'description', 'publish_end_date', 'publish_start_date']:
                meta[s] = src[s]
            else:
                cust[s] = src[s]
    target['metadata']['category'] = None
    return target

def push_update(media_id, payload, retry=0):
    print(f'updating media id: {media_id}')
    if retry > 5: 
        print(f'too many attempts... skipping {media_id}')
        return
    
    url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{media_id}/"

    res = requests.patch(url, json=payload, headers=HEADERS)
    print(res.status_code)
    if check_response(res) == False:
        retry += 1
        push_update(media_id, payload, retry)

headers, assets_csv = load_csv(csv_file)
print_headers = headers.copy()
print_headers.remove("mediaid")

if input(f"Replace values found in these columns? \n\t{(' | ').join(print_headers)}\n(y/n): ").lower() == "y":
    print(f'Backing up assets...')
    assets_all, fn_backup = backup(PROP_ID, SECRET)
    print(f'Backup in {fn_backup}')

    confirm = "c"
    for a in assets_csv:
        mid = a['mediaid']

        del a['mediaid']

        asset = get_asset(mid, assets_all)

        if asset == None: continue #make sure asset exists in JWPlayer

        meta = asset['metadata']
        cust = meta['custom_params']

        if confirm == "c": pprint(cust)

        data = update_metadata(a, asset)
        
        payload = {'metadata': {}}

        # metadata exceptions 
        if "title" in a: payload['metadata']['title'] = data['metadata']['title']
        if "description" in a: payload['metadata']['description'] = data['metadata']['description']
        if "publish_end_date" in a: payload['metadata']['publish_end_date'] = data['metadata']['publish_end_date']
        if "publish_start_date" in a: payload['metadata']['publish_start_date'] = data['metadata']['publish_start_date']

        payload['metadata']["custom_params"] = data['metadata']['custom_params']
        payload['metadata']["tags"] = data['metadata']['tags']

        # cust = updated_cust
        if confirm == "c":
            pprint("##############################################")
            pprint("############### OLD ^ ############  NEW ......")
            pprint("##############################################")
            pprint(pprint(payload))
            confirm = input(f"Confirm the above update.\nType in an option:\n\tContinue (c)\n\tExit (x)\n\tProcess All (a)\n(c,x,a):").lower()

            if confirm not in ["c","x","a"]: confirm == "x"
            

        if confirm in ["c","a"]: push_update(asset['id'], payload)

        if confirm == "x": sys.exit("Exiting...")
        
