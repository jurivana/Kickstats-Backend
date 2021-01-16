import json
import requests
from bs4 import BeautifulSoup

from django.http import JsonResponse, HttpResponse
from django.db.models import F

from .models import Team, TeamStats, User, Game, Prediction, Meta


def get_table(request, username=None):
    response = {
        'total': [],
        'home': [],
        'away': [],
        'user': username
    }
    user = User.objects.get(name=username) if username else None
    for type in TeamStats.TYPE_CHOICES:
        teams = TeamStats.objects.filter(type=type[0], user=user).order_by('-points', -(F('goals') - F('goals_against')), '-goals')
        print(f'\n\n # Name                  G  S  U  N  T GT  TD  P')
        for idx, team in enumerate(teams):
            rank = idx + 1
            print(
                f'{rank:2} {team.team.name:20} {team.wins + team.draws + team.losses:2} {team.wins:2} {team.draws:2} {team.losses:2} {team.goals:2} {team.goals_against:2} {team.goals-team.goals_against:3} {team.points:2}'
            )
            response[type[1]].append({
                'rank': rank,
                'name': team.team.name,
                'games': team.wins + team.draws + team.losses,
                'wins': team.wins,
                'draws': team.draws,
                'losses': team.losses,
                'goals': team.goals,
                'goals_against': team.goals_against,
                'diff': team.goals - team.goals_against,
                'points': team.points
            })
    return JsonResponse(response)

def update_db(request):
    url = 'https://www.kicktipp.de/ezpzplus/tippuebersicht'
    url_gd = 'https://www.kicktipp.de/ezpzplus/tippuebersicht?&spieltagIndex={gd}'
    
    meta = Meta.objects.get_or_create()[0]
    if not meta:
        meta = Meta.objects.create(version=0)
    
    # create teams
    with open('app/teams.json', encoding='utf-8') as teams_file:
        teams = json.load(teams_file)
        if (teams['version'] > meta.version):
            Team.objects.all().delete()
            for team in teams['teams']:
                Team.objects.create(name=team['name'], abbr=team['abbr'])
            meta.version = teams['version']
            meta.save()

    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # create users
    users = soup.findAll('div', class_='mg_name')
    if len(users) > User.objects.count():
        User.objects.all().delete()
        for user in users:
            User.objects.create(name=user.string)
    
    # add all new games and predictions
    curr_gd = int(soup.find('div', class_='prevnextTitle').a.string.split('.')[0])
    if curr_gd > meta.curr_gd:
        extract_ranking(curr_gd, soup.find(id='ranking'))
        for gd in range(meta.curr_gd, curr_gd):
            print(gd)
            resp = requests.get(url_gd.format(gd=gd))
            soup = BeautifulSoup(resp.text, 'html.parser')
            extract_ranking(gd, soup.find(id='ranking'))
        meta.curr_gd = curr_gd
        meta.save()

    return HttpResponse(status=204)

def extract_ranking(gd, ranking):
    games = ranking.find_all('th', class_='ereignis')
    if games[8].find('span', class_='kicktipp-heim').string == '-':  # TODO check if finished
        return

    game_objects = []
    for game in games:
        home = game.find('div', class_='headerbox')
        away = home.find_next()
        home_team = Team.objects.get(abbr=home.string)
        away_team = Team.objects.get(abbr=away.string)
        score_home = int(game.find('span', class_='kicktipp-heim').string)
        score_away = int(game.find('span', class_='kicktipp-gast').string)

        game_objects.append(Game.objects.create(
            home=home_team, 
            away=away_team,
            score_home=score_home,
            score_away=score_away,
            gameday=gd
        ))
        create_tables(home_team, away_team, score_home, score_away)
        
    
    users = ranking.find_all('tr', class_='teilnehmer')
    for user in users:
        name = user.find('div', class_='mg_name').string
        preds = user.find_all('td', class_='ereignis')
        for game_idx, pred in enumerate(preds):
            if pred.sub:
                score = pred.sub.previous_sibling.string.split(':')
                points = pred.sub.string
            else:
                score = pred.string.split(':') if pred.string else (None, None)
                points = 0
            
            try:
                score_home = int(score[0])
                score_away = int(score[1])
            except TypeError:
                score_home = score_away = None
            user_obj = User.objects.get(name=name)
            game = game_objects[game_idx]

            Prediction.objects.create(
                user=user_obj,
                game=game,
                score_home=score_home,
                score_away=score_away,
                points=points
            )
            if score_home is not None:
                create_tables(game.home, game.away, score_home, score_away, user_obj)

def create_tables(home_team, away_team, score_home, score_away, user=None):
    home_stats_total = TeamStats.objects.get_or_create(team=home_team, user=user, type=TeamStats.TOTAL)[0]
    home_stats_home = TeamStats.objects.get_or_create(team=home_team, user=user, type=TeamStats.HOME)[0]
    away_stats_total = TeamStats.objects.get_or_create(team=away_team, user=user, type=TeamStats.TOTAL)[0]
    away_stats_away = TeamStats.objects.get_or_create(team=away_team, user=user, type=TeamStats.AWAY)[0]

    home_stats_total.goals += score_home
    home_stats_total.goals_against += score_away
    home_stats_home.goals += score_home
    home_stats_home.goals_against += score_away
    away_stats_total.goals += score_away
    away_stats_total.goals_against += score_home
    away_stats_away.goals += score_away
    away_stats_away.goals_against += score_home

    if score_home > score_away:
        home_stats_total.wins += 1
        home_stats_home.wins += 1
        away_stats_total.losses += 1
        away_stats_away.losses += 1
        home_stats_total.points += 3
        home_stats_home.points += 3
    elif score_home == score_away:
        home_stats_total.draws += 1
        home_stats_home.draws += 1
        away_stats_total.draws += 1
        away_stats_away.draws += 1
        home_stats_total.points += 1
        home_stats_home.points += 1
        away_stats_total.points += 1
        away_stats_away.points += 1
    else:
        home_stats_total.losses += 1
        home_stats_home.losses += 1
        away_stats_total.wins += 1
        away_stats_away.wins += 1
        away_stats_total.points += 3
        away_stats_away.points += 3

    home_stats_total.save()
    home_stats_home.save() 
    away_stats_total.save()
    away_stats_away.save() 