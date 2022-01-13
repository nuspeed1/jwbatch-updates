import re
from os.path import exists
import csv
import requests
from utils import backup, check_response, get_credentials
from argparse import ArgumentParser

"""
Replace captions found in CSV file.  CSV requires the following columns:
SUBTITLE_FILENAME - local path to subtitle
GUID - unique id which identifies asset
TITLE - movie title

New caption files should exist in the ./captions folder of this directory.

1. Backup all assets
2. Loops through rows in CSV
3. Looks up media in JW with GUID and TITLE
4. Unpublish all captions in a media asset
5. Upload new caption

Usage: python add_captions.py -p <PROPERTY ID> -s <V2 API SECRET> -f <PATH TO CSV>
"""

parser = ArgumentParser()
parser.add_argument("-f", dest="file", default="", help="CSV file with captions")
args = parser.parse_args()
file_path = args.file

SECRET, PROP_ID = get_credentials()
HEADERS = {"Accept": "application/json", "Authorization": SECRET}

MIME_TYPES = {"srt": "text/vtt","vtt": "text/vtt"}

def get_asset(assets, mid, media_title):
    for a in assets:
        meta = a['metadata']
        cust = meta['custom_params']
        if "import_guid" not in cust: continue

        if cust['import_guid'].strip() == mid.strip() and meta['title'].lower() == media_title:
            return a

def upload_track(url, cap_path, ext):
    try:
        headers = {"Content-Type": MIME_TYPES[ext]}

        with open(cap_path, 'rb') as f:
            track_data = f.read()
            requests.put(url, headers=headers, data=track_data)
            return True
    except Exception as e:
        print(e)


def update_track(cap_path, media_id, retry=0):
    try:
        if retry > 5: 
            print(f'too many attempts... skipping {media_id} : {cap_path}')
            return

        url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{media_id}/text_tracks/" 

        m = re.search(r"(?<=.)[a-z]+(?=$)", cap_path)
        ext = m.group()

        payload = {
            "upload": {
                "file_format": ext,
                "auto_publish": True,
                "method": "direct",
                "mime_type": MIME_TYPES[ext]
            },
            "metadata":{
                "label": "English",
                "track_kind": "captions"
            }
        }

        res = requests.post(url, json=payload, headers=HEADERS)

        if check_response(res) == False:
            retry += 1
            update_track(cap_path, media_id, retry)

        response = res.json()
        
        upload_url = response['upload_link']

        upload_track(upload_url, cap_path, ext)


    except Exception as e:
        print(e)

def unpublish_captions(media_id, track_id, retry=0):
        if retry > 5: 
            print(f'too many attempts... skipping {media_id}')
            return    

        url_unpub = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{media_id}/text_tracks/{track_id}/unpublish/"

        res = requests.put(url_unpub, headers=HEADERS)

        if check_response(res) == False:
            retry += 1
            unpublish_captions(media_id, track_id, retry)

def get_captions(media_id, retry=0):
    if retry > 5: 
        print(f'too many attempts... skipping {media_id}')
        return

    url_list = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{media_id}/text_tracks/"

    res = requests.get(url_list, headers=HEADERS)

    if check_response(res) == False:
        retry += 1
        get_captions(media_id, retry)

    data = res.json()

    for t in data['text_tracks']:
        if t['type'] != "text_track": continue
        track_id = t['id']
        unpublish_captions(media_id, track_id)


def start(csv_file):
    assets, fn_backup = backup(PROP_ID, SECRET)

    f = open(csv_file, newline="")

    for row in csv.DictReader(f):
        cap_file = row["SUBTITLE_FILENAME"].lower()

        guid = row["GUID"]

        m = get_asset(assets, guid, row["TITLE"])
        
        if m == None: continue

        print(m['metadata']['title'])
        m['caption_file'] = cap_file
        
        # Unpublish existing captions
        get_captions(m['id'])

        # Add new captions
        if exists(f"./captions/{cap_file}"):
            print(f'updating.... {m["id"]} : {cap_file}')

            update_track(f"./captions/{cap_file}", m['id'])
            
        else:
            print(f"Subtitle doesn't exist: {guid}  :  {cap_file}")

    print(len(assets))

start(file_path)
