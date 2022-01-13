import json
import requests
import dateutil.parser as parser
from pprint import pprint
from argparse import ArgumentParser

from utils import check_response, get_credentials, backup
"""
Delete a list of custom fields from each asset and/or rename custom fields
"""



# add list of fields here
LIST_OF_FIELDS = ["providerId", "mediaid", "title", "hosting_type", "status", "productionType","validitywindow", "dcterms_valid", "pubDate", 
                    "publish_start_date", "publish_end_date", "seriesId", "import_guid","episodic_landscape_url", "poster_landscape_url", 
                    "poster_portrait_url"]

parser = ArgumentParser()
parser.add_argument("-d", dest="delete", default="", required=False, help="List of custom fields to delete: field,field2")
parser.add_argument("-r", dest="rename", default="", required=False, help="List of keyname pairs to rename. <old name>=<new name>, e.g. field=field2,guid=import_guid")
SECRET, PROP_ID = get_credentials(parser)
args = parser.parse_args()

deletes = args.delete
renames = args.rename

HEADERS = {"Accept": "application/json", "Authorization": SECRET}

def update_asset(media_id, payload, retry=0):
    if retry > 5: 
        print(f'too many attempts... skipping {media_id}')
        return

    url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{media_id}/"

    res = requests.patch(url, json=payload, headers=HEADERS)

    if check_response(res) == False:
        retry += 1
        update_asset(media_id, payload, retry)


def remove_fields(assets, deletes=None, renames=None):
    count = 0
    for a in assets:
        
        count += 1
        #skip series cards
        if "series_card" in a['metadata']['tags']: continue
        
        has_updates = False

        cust_params = a['metadata']['custom_params']


        if deletes:
            for f in deletes:
                if f in cust_params: 
                    del cust_params[f]
                    has_updates = True

        if renames:
            keys = renames.keys()
            for k in keys:
                if k in cust_params:
                    val = cust_params[k]
                    cust_params[renames[k]] = val
                    del cust_params[k]
                    has_updates = True
        
        if has_updates == False: continue

        payload = {"metadata":{"custom_params": cust_params}}

        print(f"{count}/~{len(assets)} - Updating media id: {a['id']}")

        update_asset(a['id'], payload)


removals = []
relabel = {}
if deletes:
    fs = deletes.split(",")
    ffs = []
    for f in fs: ffs.append(f.strip())
    removals = [i.strip() for i in ffs]

    print(f"Removing custom fields: {removals}")

if renames:
    fl = renames.split(",")
    for f in fl:
        fs = f.split("=")
        p = [i.strip() for i in fs]
        relabel[p[0]] = p[1]

all_assets, fn_backup = backup(PROP_ID, SECRET)

if input(f"Proceed with deleting {removals or 'n/a'} and/or renaming {relabel or 'n/a'} custom fields? (y/n)").lower() == "y":
    remove_fields(all_assets, removals, relabel)