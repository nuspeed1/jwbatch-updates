import sys
import requests
import json
from argparse import ArgumentParser
from pprint import pprint
from utils import backup, check_response, get_credentials

"""
Create episodic_landscape_url required by WatchFree+ app. 
This also triggers DRM.

Usage: python create_episodics.py -p <PROPERTY ID> -s <V2 API SECRET>
"""

aparser = ArgumentParser()
aparser = get_credentials(aparser)
args = aparser.parse_args()
SECRET = args.secret
PROP_ID = args.propertyid

HEADERS = {"Accept": "application/json", "Authorization": SECRET}

def update_asset(media_md, retry=0):
    if retry > 5: return
    try:
        mid = media_md['id']
        custom_params = media_md['metadata']['custom_params']

        payload = {"metadata": {"custom_params": custom_params}}
        
        url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{mid}/"

        res = requests.patch(url, headers={"Authorization": SECRET}, json=payload)
        print(res.status_code)
        if check_response(res) == False: 
            retry += 1
            update_asset(media_md, retry)


    except Exception as e:
        print(f"update error.....{e}")
        print(e)
        return False

def update_episodic_thumbail(media_id):
    url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/thumbnails/"
    payload = {
        "relationships": {"media": [{"id": media_id}]},
        "upload": {
            "source_type": "thumbstrip_image",
            "source_media_id": media_id,
            "thumbstrip_index": 7
            }
    }
    res = requests.request("POST", url, json=payload, headers=HEADERS)

    if check_response(res) == False: return update_episodic_thumbail(media_id)

    data = res.json()
    print(res.status_code)
    if res.status_code == 201:
        data = res.json()
        id = data['id']
        return f"https://cdn.jwplayer.com/v2/media/{media_id}/thumbnails/{id}.jpg?width=1920"
    else:
        return f"https://cdn.jwplayer.com/v2/media/{media_id}/poster.jpg?width=1920"


def start():
    assets, fn_backup = backup(PROP_ID, SECRET)
    
    count = 1

    medias = []
    print(len(assets))
    for m in assets:
        meta = m['metadata']
        params = meta['custom_params']

        if m['status'] != "ready": continue

        if "episodic_landscape_url" in params: continue

        #Unable to generate episodic images when they're external assets
        if m["hosting_type"] == "external": continue
            
        medias.append(m)

    
    print("##############################")
    for m in medias:
        meta = m['metadata']
        print(f"{m['id']} - {meta['title']}")
    pprint(f"Total assets to update : {len(medias)}")
    print("##############################")


    # if input(f"Continue? y/n: ").lower() == "y": 
        # confirm = "c"
    for item in medias:
        #check for valid content url
        media_id = ""

        try:
            print(f"----------ITEM----------{count}")

            media_id = item['id']
            
            print(f'  processing.... media guid:{media_id}')

            # select episode thumbnail
            episodic_url = update_episodic_thumbail(media_id)
            
            item['metadata']['custom_params']['episodic_landscape_url'] = episodic_url

            # if confirm == "c":
            #     confirm = input(f"Confirm the above update.\nType in an option to\n\tContinue (c)\n\tExit (x)\n\tProcess All (a)\n(c,x,a):").lower()

            #     if confirm not in ["c","x","a"]: confirm == "x"
                

            # if confirm in ["c","a"]: update_asset(item)

            # if confirm == "x": sys.exit("Exiting...")
            update_asset(item)

        except Exception as e:
            print(e)
            print(f"\n-------------------------------------------------\n")
            print(f"mediaId: {media_id}")
            print(str(e))
            print("###ELEMENT ERROR###")
            print(str(e))
            break

        count+=1

start()