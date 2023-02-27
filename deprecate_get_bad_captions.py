import requests
import re
import csv
from pprint import pprint
from utils import check_response, get_credentials, backup

"""
This will look through all assets and identify captions with a starting offset of 1hr.
A report file bad_captions.csv will be generated and placed in the files directory.

Usage: python get_back_captions.py -p <PROPERTY ID> -s <V2 API SECRET>
"""

SECRET, SITE_ID = get_credentials()
HEADERS = {"Accept": "application/json", "Authorization": SECRET}
assets, fn_backup = backup(SITE_ID, SECRET)

def list_tracks(media_id, retry=0):
    url = f"https://api.jwplayer.com/v2/sites/{SITE_ID}/media/{media_id}/text_tracks/"

    res = requests.get(url, headers=HEADERS)
    if check_response(res) == False:
        retry += 1
        return list_tracks(media_id, retry)

    return res.json()

no_captions = []

count = 0
f = open('./files/bad_captions.csv', "w")
writer = csv.writer(f)

writer.writerow(['mediaid', 'has caption', 'title', 'sample offset', 'caption url'])

for a in assets:
    count += 1

    mid = a['id']
    print(f'{count} : {mid}')

    tracks = list_tracks(mid)
    if "text_tracks" not in tracks: continue

    if len(tracks['text_tracks']) == 0: 
        writer.writerow([mid,"NO", a['metadata']['title'],"", ""])
        no_captions.append(mid)
        continue
    
    for t in tracks['text_tracks']:
        
        if "captions" != t['track_kind']: continue

        t_url = t['delivery_url']

        res = requests.get(t_url)

        matches = re.finditer(r"^([0-9]{2}:[0-9]{2}:[0-9]{2})", res.text, re.MULTILINE)
        try:
            for m in matches:
                if ":" not in m.group(0): continue

                text = m.group(0)

                hhmmss = text.split(":")
                if hhmmss[0] == "00": break

                if len(hhmmss) < 3: break

                h = hhmmss[0]
                print(hhmmss)
                if h in ["01", "02", "03", "04"]:
                    writer.writerow([mid,"YES", a['metadata']['title'], text, t_url])
                    break
        except Exception as e:
            pass
        
      






