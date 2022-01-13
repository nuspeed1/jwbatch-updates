import re
import time
import csv
import json
import requests
from argparse import ArgumentParser
from datetime import datetime

"""
https://poc.jwplayer.com/app/Z5ycOQVw/
"""

def get_credentials(parser):
    # parser = ArgumentParser()
    parser.add_argument("-p", dest="propertyid", default="", help="Property ID")
    parser.add_argument("-s", dest="secret", default="", help="Secret key")
    # args = parser.parse_args()
    # secret = args.secret
    # prop = args.propertyid
    
    return parser

def get_file_ext(filename):
    print(filename)
    m = re.search(r"(?<=.)[a-z]+(?=$)", filename)
    ext = m.group()
    return ext

def load_local_backup(filename):
    ext = get_file_ext(filename)
    if ext == "csv":
        f = open(filename, newline="")
        return csv.DictReader(f)
        
    elif ext == "json":
        f = open(filename, "r")
        data = json.load(f)
        f.close()
        return data

def save_file(filename, data):
    ext = get_file_ext(filename)
    if ext == "csv":
        pass
    elif ext == "json":
        f = open(filename, "w+")
        f.write(json.dumps(data))
        f.close()

def backup(SITE_ID, SECRET):
    """
    Creates a json backup and of all assets and 
    places it in the ./files subdirectory
    """
    HEADERS = {"Accept": "application/json", "Authorization": SECRET}

    url = f"https://api.jwplayer.com/v2/sites/{SITE_ID}/media/"
    querystring = {"page":"3","page_length":"500","sort":"created:dsc"}
    page = 1
    pages = 10 #gets set from while loop.

    assets = []
    while page <= pages:
        querystring["page"] = page
        querystring['page_length'] = 500
        response = requests.request("GET", url, headers=HEADERS, params=querystring)
        res = response.json()
        page_length = res['page_length']
        page = res['page']
        total = res['total']
        pages = round(total/page_length)+1
        assets += res['media']
        page += 1


    now = datetime.now()
    timestamp = now.strftime("%d-%b-%Y_%H+%M+%S")
    filename= f"./files/backup{timestamp}.json"

    save_file(filename, assets)

    return assets, filename

def get_medias_from_playlist(url, medias=[]):
    """
    Return all media items from a playlist
    :param str url: Playlist url
    :param list medias: Media list.  Defaults to empty
    :return: list of media items
    """
    res = requests.get(url)
    data = res.json()
    medias += data['playlist']
    if "next" in data['links']:
        url = data['links']['next']
        medias = get_medias_from_playlist(url, medias)
    
    return medias

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

def convert_pubdate(str):
    """
    Returns: 'Friday, 01 September 2017'
    """
    d = datetime.fromisoformat(str)
    pubDate = d.strftime("%A, %d %B %Y")
    year = d.strftime("%Y")
    return pubDate, year