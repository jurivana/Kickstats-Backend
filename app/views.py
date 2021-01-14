from sys import version
import json
import requests
from bs4 import BeautifulSoup
import sqlite3

from django.shortcuts import render
from django.http import HttpResponse

from .models import Team, User, Game, Prediction, Meta


url = 'https://www.kicktipp.de/ezpzplus/tippuebersicht'
url_gd = 'https://www.kicktipp.de/ezpzplus/tippuebersicht?&spieltagIndex={gd}'

def index(request):
    meta = Meta.objects.first()
    if not meta:
        meta = Meta.objects.create(version=0)
    
    with open('app/teams.json', encoding='utf-8') as teams_file:
        teams = json.load(teams_file)
        if (teams['version'] > meta.version):
            for team in teams['teams']:
                Team.objects.create(name=team['name'], abbr=team['abbr'])
            meta.version = teams['version']
            meta.save()

    resp = requests.get(url)

    soup = BeautifulSoup(resp.text, 'html.parser')

    curr_gd = int(soup.find('div', {'class': 'prevnextTitle'}).find('a').string.split('.')[0])
    
    for user in soup.findAll('div', {'class': 'mg_name'}):
        try:
            User.objects.create(name=user.string)
        except Exception:
            pass

    return HttpResponse(resp.status_code)
