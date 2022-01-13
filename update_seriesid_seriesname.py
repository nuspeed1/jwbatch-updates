import requests
import csv
import json
import time
import sys
from datetime import datetime
from pprint import pprint
from argparse import ArgumentParser
from utils import get_credentials

"""
After creating a backup, this will update each episode with their seriesCardId and seriesName
1. First run "python update_seriesid_seriesname.py -c" to create a csv file of espisodes that will be updated.
2. Review newly created episodes.csv file
3. Then run "python update_seriesid_seriesname.py -u" to update episodes from that file.
"""

parser = ArgumentParser()
parser.add_argument("-c", dest="create", action="store_true", help="Link series information")
parser.add_argument("-u", dest="update", action="store_true", help="Update episodes")

args = parser.parse_args()

series_id = args.create
is_update = args.update

SECRET, SITE_ID = get_credentials(parser)
HEADERS = {"Accept": "application/json", "Authorization": SECRET}

CSV_FILE = "./files/episodes.csv"

def check_response(res):
    if res.status_code >= 400:
        data = res.json()
        for e in data['errors']:
            if e['code'] == "rate_limit_exceeded": 
                print(f"Rate limit exceeded.  Cooling down for 1min before retrying")
                time.sleep(60)
                return False
    else:
        print("ok")
        return True

def create_md_backup():
    url = f"https://api.jwplayer.com/v2/sites/{SITE_ID}/media/"
    querystring = {"page":"3","page_length":"500","sort":"created:dsc"}
    page = 1
    pages = 10 #gets set in while loop.

    assets = []
    while page <= pages:
        querystring["page"] = page
        querystring['page_length'] = 500
        response = requests.request("GET", url, headers=HEADERS, params=querystring)
        
        if check_response(response) == False: create_md_backup()
        
        res = response.json()
        

        page_length = res['page_length']
        page = res['page']
        total = res['total']
        pages = round(total/page_length)+1
        assets += res['media']
        print(f'Retrieved media page {page} of {pages} : total {len(assets)} of {res["total"]} media items')
        page += 1
    
    print(f'Retrieved media page {page} of {pages} : {len(assets)} total media items')
    return assets

def convert_pubdate(str):
    """
    Returns: 'Friday, 01 September 2017'
    """
    d = datetime.fromisoformat(str)
    pubDate = d.strftime("%A, %d %B %Y")
    year = d.strftime("%Y")
    return (pubDate, year)


def create_series_file():
    assets = create_md_backup()

    series_cards = {}
    # genereate all series data
    for a in assets:
        meta = a['metadata']
        tags = meta['tags']
        cust = meta['custom_params']
        try:
            if "series_card" in tags:
                series_cards[cust['seriesId']] = {
                    "id": a['id'],
                    "title": meta['title']
                }
        except Exception as e:
            pprint(a)

    f_csv = open(CSV_FILE, "w")
    writer = csv.writer(f_csv)
        
    columns = ['MediaID', 'SeriesId', 'SeriesTitle', "EpisodeTitle",  "pubDate", "Provider ID", "SeasonNo", "EpisodeNo", "Data"]
    writer.writerow(columns)

    count = 1
    for a in assets:
        meta = a['metadata']
        cust = meta['custom_params']
        col = []

        #skip assets without an episode number
        if "episodeNumber" not in cust: continue 
        if "seriesName" in cust and "seriesCardId" in cust: continue 

        if "seriesId" in cust:
            id = cust['seriesId']

            if id not in series_cards: continue # series id not found

            card = series_cards[id]

            cust['seriesCardId'] = card["id"]
            cust['seriesName'] = card['title']

            pubDate = ""
            if "pubDate" in cust:
                pubDate = cust['pubDate']
            else:
                pub_date, year = convert_pubdate(meta["publish_start_date"])
                pubDate = pub_date
                cust['pubDate'] = pubDate
            
            provider_id = ""
            # correct providerId keynames
            if "providerId" in cust: provider_id = cust['providerId']

            if "providerID" in cust and "providerId" in cust:
                del cust['providerID']
                cust['providerId'] = provider_id

            if "providerID" in cust:
                provider_id = cust['providerID']
                del cust['providerID']
                cust['providerId'] = provider_id
            
            season_no = cust['seasonNumber'] if "seasonNumber" in cust else ""

            # in case of keyname corrections above
            a['metadata']['custom_params'] = cust

            col = [a['id'], card["id"], card['title'], meta['title'], pubDate, provider_id, season_no, cust['episodeNumber'], json.dumps(a)]
            
            writer.writerow(col)
            count += 1

        a['metadata']['custom_params'] = cust


    print("========Series Cards=========")
    pprint(series_cards)
    print(f"========Total Episodes======")
    print(f"{count} episodes to update")

def update_asset(id, payload, retries=0):
    try:
        url = f"https://api.jwplayer.com/v2/sites/{SITE_ID}/media/{id}"
        res = requests.patch(url, json=payload, headers=HEADERS)
        
        print(res.status_code)

        if retries > 5: return
        if check_response(res) == False:            
            retries += 1
            update_asset(id, payload, retries)

    except Exception as e:
        print(f"Error updating media id: {id}")
        print(e)

def load_csv():
    try:
        csvfile = open(CSV_FILE, newline="")
        # columns = ['MediaID', 'SeriesId', 'SeriesTitle', "EpisodeTitle",  "pubDate", "Provider ID", "SeasonNo", "EpisodeNo", "Data"]
        count = 1
        confirm = "c"
        for row in csv.DictReader(csvfile):

            m = json.loads(row['Data'])

            id = m['id']
            
            meta = m['metadata']
            
            cust = meta['custom_params']
            
            payload = {"metadata":{"custom_params": cust}}

            print(f"Updating asset : {id}")

            update_asset(id, payload)

            count += 1
            if count%100 == 0: print(f"=========={count} records updated==========")
            
            if confirm == "c":
                confirm = input(f"Continue?\nType in an option:\n\tContinue (c)\n\tExit (x)\n\tProcess All (a)\n\t(c,x,a):").lower()
                if confirm not in ["c","x","a"]: confirm == "x"

            if confirm == "x": sys.exit("Exiting")

    except Exception as e:
        print('ERROR - reading row')
        print(e)

if series_id: create_series_file()
if is_update: load_csv()


