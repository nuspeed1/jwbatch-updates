import json

from pprint import pprint
from argparse import ArgumentParser

f = open('media-list.json', 'r')
md = json.load(f)

series = []
for m in md['media']:
    cust_params = m['metadata']['custom_params']
    tags = m['metadata']['tags']

    seriesId = ""
    for t in tags:
        if "seriesId" in t:
            seriesId = t

    if seriesId: series.append(seriesId)


pprint(list(set(series)))
print(len(series))