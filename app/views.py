import json
import requests
from bs4 import BeautifulSoup

from django.http import JsonResponse, HttpResponse
from django.db.models import F
from django.utils import timezone

from .models import Team, Stats, User, Game, Prediction, Meta


def get_meta(request):
    response = {}
    meta = Meta.objects.get_or_create()[0]
    response['last_updated'] = meta.last_updated
    response['curr_gd'] = meta.curr_gd

    return JsonResponse(response)

def get_users(request):
    response = {
        'users': []
    }
    users = User.objects.order_by('name')
    for user in users:
        response['users'].append(user.name)

    return JsonResponse(response)

def get_table(request, username=None):
    response = {
        'total': [],
        'home': [],
        'away': [],
        'user': username
    }
    user = User.objects.get(name=username) if username else None
    for type in Stats.TYPE_CHOICES:
        stats = Stats.objects.filter(type=type[0], user=user).order_by('-points', -(F('goals') - F('goals_against')), '-goals')
        print(f'\n\n # Name                  G  S  U  N  T GT  TD  P')
        for idx, stat in enumerate(stats):
            rank = idx + 1
            print(
                f'{rank:2} {stat.team.name:20} {stat.wins + stat.draws + stat.losses:2} {stat.wins:2} {stat.draws:2} {stat.losses:2} {stat.goals:2} {stat.goals_against:2} {stat.goals-stat.goals_against:3} {stat.points:2}'
            )
            response[type[1]].append({
                'rank': rank,
                'team': stat.team.name,
                'games': stat.wins + stat.draws + stat.losses,
                'wins': stat.wins,
                'draws': stat.draws,
                'losses': stat.losses,
                'goals': stat.goals,
                'goals_against': stat.goals_against,
                'diff': stat.goals - stat.goals_against,
                'points': stat.points
            })
    return JsonResponse(response)

def get_points(request, username):
    response = {
        'total': [],
        'home': [],
        'away': [],
        'user': username
    }
    user = User.objects.get(name=username)
    for type in Stats.TYPE_CHOICES:
        stats = Stats.objects.filter(type=type[0], user=user).order_by('-user_points')

        for idx, stat in enumerate(stats):
            rank = idx + 1
            response[type[1]].append({
                'rank': rank,
                'team': stat.team.name,
                'points': stat.user_points,
                'four_points': stat.four_points,
                'three_points': stat.three_points,
                'two_points': stat.two_points,
                'zero_points': stat.zero_points
            })

    return JsonResponse(response)

def get_last_updated(request):
    return JsonResponse({
        'last_updated': Meta.objects.first().last_updated or 'never'
    })

def update_db(request):
    url = 'https://www.kicktipp.de/ezpzplus/tippuebersicht'
    url_gd = 'https://www.kicktipp.de/ezpzplus/tippuebersicht?&spieltagIndex={gd}'
    
    meta = Meta.objects.get_or_create()[0]
    
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

    meta.last_updated = (timezone.now())
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
        __update_stats(home_team, away_team, score_home, score_away)
        
    
    users = ranking.find_all('tr', class_='teilnehmer')
    for user in users:
        name = user.find('div', class_='mg_name').string
        preds = user.find_all('td', class_='ereignis')
        for game_idx, pred in enumerate(preds):
            if pred.sub:
                score = pred.sub.previous_sibling.string.split(':')
                points = int(pred.sub.string)
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
                __update_stats(game.home, game.away, score_home, score_away, user_obj, points)

def __update_stats(home_team, away_team, score_home, score_away, user=None, user_points=None):
    home_stats_total = Stats.objects.get_or_create(team=home_team, user=user, type=Stats.TOTAL)[0]
    home_stats_home = Stats.objects.get_or_create(team=home_team, user=user, type=Stats.HOME)[0]
    away_stats_total = Stats.objects.get_or_create(team=away_team, user=user, type=Stats.TOTAL)[0]
    away_stats_away = Stats.objects.get_or_create(team=away_team, user=user, type=Stats.AWAY)[0]

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

    if user_points:
        home_stats_total.user_points += user_points
        home_stats_home.user_points += user_points
        away_stats_total.user_points += user_points
        away_stats_away.user_points += user_points
        
        if user_points == 4:
            home_stats_total.four_points += 1
            home_stats_home.four_points += 1
            away_stats_total.four_points += 1
            away_stats_away.four_points += 1
        elif user_points == 3:
            home_stats_total.three_points += 1
            home_stats_home.three_points += 1
            away_stats_total.three_points += 1
            away_stats_away.three_points += 1
        elif user_points == 2:
            home_stats_total.two_points += 1
            home_stats_home.two_points += 1
            away_stats_total.two_points += 1
            away_stats_away.two_points += 1
        elif user_points == 0:
            home_stats_total.zero_points += 1
            home_stats_home.zero_points += 1
            away_stats_total.zero_points += 1
            away_stats_away.zero_points += 1

    home_stats_total.save()
    home_stats_home.save() 
    away_stats_total.save()
    away_stats_away.save()