from os.path import exists
import sys
import requests
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from utils import check_response, get_credentials, backup
from argparse import ArgumentParser


"""
This reads an MRSS feed, finds the asset in JWDashboard and populates it with
additional thumbnails (landscape and portrait) and converts tags into custom fields. 

TODO: because some MRSS feeds have TTL tokens attached to assets, this downloads thumbnails
into the thumbnails folder and uploads it to JWPlayer from there.  

1. Open the file and search for the custom namespace at the top of the file.  If you are xyzcompany, copy the namespace "xyzcompany".
example:  Copy http://www.xyzcompany.com/rss/ from the top
<rss xmlns:media="http://search.yahoo.com/mrss/"
    xmlns:xyzcompany="http://www.xyzcompany.com/rss/"
    xmlns:dcterms="http://purl.org/dc/terms/" version="2.0">
2. From terminal run the following command:
USAGE:
    python mrss_post_update.py -s <SECRET> -p <PROPERTY ID> -n "<NAMESPACE>" -f <URL TO MRSS FEED>
    
RENDERED:
    python mrss_post_update.py -s SXY2818... -p HMXieu7 -n "xyzcompany" -f "https://PATH_TO_MY_MRSS_FEED.xml"
"""
parser = ArgumentParser()
parser = get_credentials(parser)
parser.add_argument("-n", dest="namespace", default="", help="Publisher namespace")
parser.add_argument("-f", dest="mrss_file", default="", help="MRSS xml file")
args = parser.parse_args()
SECRET = args.secret
PROP_ID = args.propertyid

ns = args.namespace
mrss_file = args.mrss_file



HEADERS = {"Accept": "application/json", "Authorization": SECRET}

def create_payload(elem:ET.Element, keyart):
    md = {}

    thumbnails = elem.findall('.//{http://search.yahoo.com/mrss/}thumbnail/[@url]')
    guid = elem.find('guid')
    for thumb in thumbnails:
        height = int(thumb.get('height'))
        width = int(thumb.get('width'))

        if round(width/height,2) == 0.67: 
            # md['poster_portrait'] = thumb.get('url')
            md['poster_portrait'] = f"./thumbnails/{guid.text}_portrait.jpg"

        if round(width/height,2) == 1.78: 
            # md['poster_landscape'] = thumb.get('url')
            md['poster_landscape'] = f"./thumbnails/{guid.text}_landscape.jpg"

    for e in elem:
        try:
            if "cuePoints" in e.tag and e.text:
                cues = e.text.split(",")
                cuepoints = [f"{i.split(':')[-1]}" for i in cues]
                
                md['cuepoints'] = ",".join(cuepoints)

            if "cuepoints" in e.tag and e.text:
                cues = e.text.split(",")
                cuepoints = [f"{i.split(':')[-1]}" for i in cues]
                
                md['cuepoints'] = ",".join(cuepoints)
            
            if "guid" in e.tag and e.text:
                md['guid'] = e.text

            if "title" in e.tag and e.text:
                md['title'] = e.text

            if "pubDate" in e.tag and e.text:
                md['pubDate'] = e.text

            if "productionType" in e.tag and e.text:
                cf = e.text.split(",")
                vals = [i.split(":")[-1] for i in cf]
                md['productionType'] = {
                    'tags':e.text.split(","),
                    "value":",".join(vals)
                }

            if "seriesId" in e.tag and e.text:
                id = e.text
                md['seriesId'] = id
                sid = id.split(":")[-1]
                if sid in keyart:
                    md['poster_portrait'] = keyart[sid]['portrait']
                    md['poster_landscape'] = keyart[sid]['landscape']


            if "rating" in e.tag and e.text:
                ratings = e.text.split(",")
                tags = [f"{i}" for i in ratings]
                md['rating'] = {
                    'tags':tags,
                    "value":e.text.split(":")[1]
                }

            if "restriction" in e.tag and e.text:
                res = e.text.split(",")
                md['restrictions'] = {}
                for r in res:
                    s = r.split(":")
                    md['restrictions'][s[0]] = s[1]

            if "genre" in e.tag and e.text:
                c = e.text.split(",")
                tags = [f"{i.strip()}" for i in c]
                tags2 = [f"{i.strip()}" for i in c]
                tags += tags2
                tags = list(set(tags))
                md['category'] = {
                    'tags':tags,
                    "value":e.text.split(":")[-1]
                }
                md['genre'] = {
                    'tags':tags2,
                    "value":e.text.split(":")[-1]
                }

            if "seasonNumber" in e.tag and e.text:
                md['seasonNumber'] = e.text.split(":")[-1]

            if "episodeNumber" in e.tag and e.text:
                md['episodeNumber'] = e.text.split(":")[-1]

            if "credit" in e.tag and e.text:
                if e.get('role') in md:
                    md[e.get('role')] = f"{md[e.get('role')]}, {e.text}"
                else:
                    md[e.get('role')] = e.text

            if "validitywindow" in e.tag and e.text:
                md['validitywindow'] = e.text.split("validitywindow:")[1]
        except Exception as e:
            continue

    return md

def find_asset_from_backup(guid, title, assets):
    res = False
    for m in assets:
        meta = m['metadata']
        params = meta["custom_params"]
        if "import_guid" in params and params["import_guid"] == guid and \
            title == meta['title']:
            res = m
            break

    if res == False:
        return False
    else:
        return {"media":[res]}

def find_asset(guid):

    query= f"q=(status:+NOT+created)+AND+(custom_params:(name:'import_guid'+AND+value:'{guid}'))&sort=publish_start_date:dsc"

    url = f'https://api.jwplayer.com/v2/sites/{PROP_ID}/media/?page=1&page_length=10&{query}'
            
    try:
        res = requests.get(url, headers={"Authorization": SECRET})
        return res.json()
    except Exception as e:
        print(str(e))
        return False

def update_asset(new_md, media_md, retries=0):
    try:
        mid = media_md['id']
        custom_params = media_md['metadata']['custom_params']
        tags = media_md['metadata']['tags']

        tags = [t.strip() for t in tags]
        
        for t in tags:
            if "providerid" in t.lower():
                custom_params['providerId'] = t.split(":")[1]

        url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/media/{mid}/"

        has_payload = False
        
        if "poster_landscape_url" in new_md:
            custom_params['poster_landscape_url'] = new_md['poster_landscape_url']
            has_payload = True

        if "poster_portrait_url" in new_md:
            custom_params['poster_portrait_url'] = new_md['poster_portrait_url']
            has_payload = True

        if "cuepoints" in new_md:
            custom_params['cuepoints'] = new_md['cuepoints']
            has_payload = True

        if "productionType" in new_md:
            pt = new_md["productionType"]
            tags += pt['tags']
            custom_params['productionType'] = pt['value']
            has_payload = True

        if "seriesId" in new_md:
            custom_params['seriesId'] = new_md['seriesId'].split(":")[-1]
            has_payload = True

        if "seasonNumber" in new_md:
            custom_params['seasonNumber'] = new_md['seasonNumber']
            has_payload = True

        if "episodeNumber" in new_md:
            custom_params['episodeNumber'] = new_md['episodeNumber']
            has_payload = True

        if "genre" in new_md:
            tags += new_md['genre']['tags']
            custom_params['genre'] = new_md['genre']['value']
            has_payload = True

        if "restrictions" in new_md:
            for r in new_md['restrictions']:
                custom_params[r] = new_md['restrictions'][r]
            has_payload = True

        if "rating" in new_md:
            tags += new_md['rating']['tags']
            custom_params['rating'] = new_md['rating']['value']
            has_payload = True

        if "validitywindow" in new_md:
            custom_params['validitywindow'] = new_md['validitywindow']
            has_payload = True

        if "actor" in new_md:
            custom_params['actor'] = new_md['actor']
            has_payload = True

        if "director" in new_md:
            custom_params['director'] = new_md['director']
            has_payload = True

        if "pubDate" in new_md:
            custom_params['pubDate'] = new_md['pubDate']
            has_payload = True

        custom_params['coppa'] = "0"
        custom_params['lmt'] = "0"
        custom_params['ifa_type'] = "vida"
        custom_params['adScheduleId'] = "PppWf7L9"
        has_payload = True

        if "actor" not in new_md:
            custom_params['actor'] = "Unavailable"
        
        if "director" not in new_md:
            custom_params['director'] = "Unavailable"
        
        if "cuepoints" not in custom_params:
            custom_params['cuepoints'] = ""

        payload = {
            "metadata": {
                "custom_params": custom_params, "tags": list(set(tags))}}
        
        
        if has_payload:
            res = requests.patch(url, headers={"Authorization": SECRET}, json=payload)
            
            if retries > 5: return

            if check_response(res) == False:
                retries += 1
                update_asset(new_md, media_md, retries)
            
            print(res.status_code)
            return res

    except Exception as e:
        print(f"update error.....{e}")
        print(e)
        return False

def download_image(url, filename):
    try:
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(f"./thumbnails/{filename}", 'wb') as out_file:
                out_file.write(r.content)
            return f"./thumbnails/{filename}"
        else:
            print(r)
            print(f"Unable to create {filename} with path: {url}")
    except Exception as e:
        print(str(e))
        return False

def create_keyarts(media_id, thumb_path, retries=0):
    try:
        if retries > 5: return

        url = f"https://api.jwplayer.com/v2/sites/{PROP_ID}/thumbnails/"
        print('creating thumbnail')
        payload = {
            "relationships": {"media": [{"id": f"{media_id}"}]},
            "upload": {
                "source_type": "custom_upload",
                "method": "direct",
                "thumbnail_type": "static"
            }
        }

        res = requests.request("POST", url, json=payload, headers=HEADERS)

        if check_response(res) == False:
            retries += 1
            create_keyarts(media_id, thumb_path, retries)

        data = res.json()
        upload_link = data['upload_link']
        id = data['id']
        
        result = requests.put(upload_link, data=open(thumb_path, 'rb').read())
        print(result)
        return f"https://cdn.jwplayer.com/v2/media/{media_id}/thumbnails/{id}.jpg?width=1920"


    except Exception as e:
        print(e)
        pass


def get_series_keyart(items):
    images = {}
    for i in items:
        try:
            guid = i.find("guid")
            id = guid.text
            
            thumbnails = i.findall('.//{http://search.yahoo.com/mrss/}thumbnail/[@url]')
            images[id] = {}
            for thumb in thumbnails:
                
                height = int(thumb.get('height'))
                width = int(thumb.get('width'))
                
                if round(width/height,2) == 0.67:
                    name = f"{guid.text}_portrait.jpg"
                    # images[id]["portrait"] = f"./thumbnails/{name}" #load local
                    # load remote
                    f_path = download_image(thumb.get('url'), name)
                    images[id]["portrait"] = f_path #f"./thumbnails/{name}"
                    
                    

                if round(width/height,2) == 1.78:
                    name = f"{guid.text}_landscape.jpg"
                    # images[id]["landscape"] = f"./thumbnails/{name}" #load local
                    # load remote
                    f_path = download_image(thumb.get('url'), name)
                    images[id]["landscape"] = f_path

        except Exception as e:
            print(e)
            continue
    return images

def parse_and_get_ns(data):
    file = './tmp_rss.xml'
    f = open('./tmp_rss.xml', 'w')
    f.write(data)
    f.close()
    events = "start", "start-ns"
    root = None
    ns = {}
    for event, elem in ET.iterparse(file, events):
        if event == "start-ns":
            if elem[0] in ns and ns[elem[0]] != elem[1]:
                # NOTE: It is perfectly valid to have the same prefix refer
                #     to different URI namespaces in different parts of the
                #     document. This exception serves as a reminder that this
                #     solution is not robust.    Use at your own peril.
                raise KeyError("Duplicate prefix with different URI found.")
            ns[elem[0]] = "%s" % elem[1]
        elif event == "start":
            if root is None:
                root = elem
    return ns

def load_xml(f_path):
    data = requests.get(f_path)
    
    f_txt = data.text

    ns = parse_and_get_ns(f_txt)
    ## CLEAN UP FEED
    
    f_txt = f_txt.replace("&ampamp;", "&amp;")
    f_txt = f_txt.replace("&amamp;", "&amp;")
    f_txt = f_txt.replace("<item></item>", "")

    tree = ET.ElementTree(ET.fromstring(f_txt))
    root = tree.getroot()
    
    items = root.findall("./channel/item")
    return items, ns


def validate_mrss_data(data):
    keys = data.keys()

    valid_fields = ['actor','director', 'episodeNumber','genre','guid',
    'poster_landscape','poster_portrait','productionType','pubDate',
    'seasonNumber','seriesId','validitywindow']

    diff = []
    if "seriesId" not in keys:
        valid_fields.remove("seriesId")
        valid_fields.remove("seasonNumber")
        valid_fields.remove("episodeNumber")
    
    diff = list(set(valid_fields) - set(list(keys)))
    
    if len(diff) == 0: 
        return True
    else:
        print(f'MRSS element GUID "{data["guid"]}" is missing the following fields:\n{diff}\nSkipping...')
        return False

def start(f_path):
    items, xml_namespaces = load_xml(f_path)

    namespace = ""
    if ns in xml_namespaces:
        namespace = xml_namespaces[ns]
    else:
        sys.exit(f"Namespace in MRSS feed not found. : {f_path}")

    NAMESPACE = "{"+namespace+"}"
    
    # errors = open('errors.txt', "w+")
    count = 1
    
    series_keyart = get_series_keyart(items)

    BACKUP, fn_backup = backup(PROP_ID, SECRET)
    for item in items:
        #check for valid content url
        
        ptype = item.find(f'.//{NAMESPACE}productionType')
        
        if "series" in ptype.text:continue

        media_id = ""
        feed_id = ""

        try:
            print(f"----------ITEM----------{count}")
            
            mrss_md = create_payload(item, series_keyart)

            if len(mrss_md) == 0: continue

            #VALIDATE MRSS FIELDS
            if validate_mrss_data(mrss_md) == False: continue

            feed_id = mrss_md["guid"]
            
            print(f'\tprocessing.... GUID:{feed_id}')

            backup_file = find_asset_from_backup(mrss_md['guid'], mrss_md['title'], BACKUP)

            if backup_file == False: continue

            media = backup_file['media'][0]

            media_id = media['id']
            meta = media['metadata']
            params = meta['custom_params']

            if media['status'] != "ready":
                print(f'Media {media_id} not in ready state.  skippinig.... ')
                continue

            print(f'\tprocessing.... JW Media ID:{media_id}')

            if exists(mrss_md['poster_landscape']) == False or exists(mrss_md['poster_portrait']) == False:
                print(f"Missing landscape or portrait image. Test URLs in MRSS feed for guid '{mrss_md}'\nSkipping...")


            if "poster_landscape" in mrss_md and "poster_landscape_url" not in params:
                fpath = mrss_md['poster_landscape']
                image_url = create_keyarts(media['id'],fpath)
                mrss_md[f'poster_landscape_url'] = image_url
            
            if "poster_portrait" in mrss_md and "poster_portrait_url" not in params:
                fpath = mrss_md['poster_portrait']
                image_url = create_keyarts(media['id'],fpath)
                mrss_md[f'poster_portrait_url'] = image_url
            
            update_asset(mrss_md, media)

            
        except Exception as e:
            print(e)
            print(f"\n-------------------------------------------------\n")
            print(f"mediaId: {media_id}   -    feedId: {feed_id}\n")
            print(str(e))
            print("###ELEMENT ERROR###")
            print(str(e))

        count+=1

    # errors.close()

start(mrss_file)
