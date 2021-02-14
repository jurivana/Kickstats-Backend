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
    response['last_updated'] = timezone.localtime(meta.last_updated).strftime('%d.%m.%y %H:%M')
    response['curr_gd'] = meta.curr_gd - 1

    return JsonResponse(response)

def get_users(request):
    response = {
        'users': []
    }
    users = User.objects.order_by('name')
    for user in users:
        response['users'].append(user.name)

    return JsonResponse(response)

def get_table(request, username):
    response = {
        'user': {
            'total': [],
            'home': [],
            'away': []
        },
        'real': {
            'total': [],
            'home': [],
            'away': []
        }
    }
    user = User.objects.get(name=username)
    for type in Stats.TYPE_CHOICES:
        real_stats = Stats.objects.filter(type=type[0], user=None).order_by('-points', -(F('goals') - F('goals_against')), '-goals')
        real_ranks = {}
        for idx, stat in enumerate(real_stats):
            rank = idx + 1
            real_ranks[stat.team.name] = rank
            response['real'][type[1]].append(__create_table_json(rank, stat))

        user_stats = Stats.objects.filter(type=type[0], user=user).order_by('-points', -(F('goals') - F('goals_against')), '-goals')
        for user_idx, user_stat in enumerate(user_stats):
            user_rank = user_idx + 1
            rank_diff = real_ranks[user_stat.team.name] - user_rank
            response['user'][type[1]].append(__create_table_json(user_rank, user_stat, rank_diff))

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

def get_highlights(request):
    highlights_user = {}
    highlights_user_cats = ['most_overrated', 'most_underrated', 'goals_per_game', 'most_four_points', 'most_points', 'fewest_points']
    for hl in highlights_user_cats:
        highlights_user[hl] = []
    for user in User.objects.all():
        hls = __get_highlights_user_json(user)
        for hl in highlights_user_cats:
            for entry in hls[hl]:
                highlights_user[hl].append([user.name] + [entry])
    for hl in highlights_user_cats:
        highlights_user[hl] = sorted(highlights_user[hl], key=lambda x: hasattr(x[1], '__getitem__') and x[1][1] or x[1], reverse=True)

    points_total = []
    for team in Team.objects.all():
        stats = Stats.objects.filter(team=team, type=Stats.TOTAL)
        points_total.append([team.name, sum([stat.user_points for stat in stats])])
    points_total = sorted(points_total, key=lambda x: x[1])

    return JsonResponse({
        'most_four_points': highlights_user['most_four_points'][:3],
        'most_points': highlights_user['most_points'][:3],
        'fewest_points': sorted(highlights_user['fewest_points'][-3:], key=lambda x: x[1][1]),
        'most_overrated': highlights_user['most_overrated'][:3],
        'most_underrated': highlights_user['most_underrated'][:3],
        'most_goals': highlights_user['goals_per_game'][:3],
        'fewest_goals': sorted(highlights_user['goals_per_game'][-3:], key=lambda x: x[1]),
        'most_points_total': [[None, data] for data in points_total[-3:][::-1]],
        'fewest_points_total': [[None, data] for data in points_total[:3]]
    })

def get_highlights_user(request, username):
    user = User.objects.get(name=username)
    return JsonResponse(__get_highlights_user_json(user))

def __get_highlights_user_json(user):
    stats = Stats.objects.filter(user=user, type=Stats.TOTAL)

    table = Stats.objects.filter(user=None, type=Stats.TOTAL)
    point_diff = [[real_stat.team.name, real_stat.points - user_stat.points] for (real_stat, user_stat) in zip(list(table.order_by('team')), list(stats.order_by('team')))]
    return {
        'most_four_points': [[stat.team.name, stat.four_points] for stat in list(stats.order_by('-four_points')[:3])],
        'most_points': [[stat.team.name, stat.user_points] for stat in list(stats.order_by('-user_points')[:3])],
        'fewest_points': [[stat.team.name, stat.user_points] for stat in list(stats.order_by('user_points')[:3])],
        'most_overrated': [[x[0], -x[1]] for x in sorted(point_diff, key=lambda x: x[1])[:3]],
        'most_underrated': sorted(point_diff, key=lambda x: -x[1])[:3],
        'goals_per_game': [[None, user.goals / user.preds]]
    }

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
        extract_ranking(curr_gd, soup.find(id='ranking'), True)
        for gd in range(meta.curr_gd, curr_gd):
            print(gd)
            resp = requests.get(url_gd.format(gd=gd))
            soup = BeautifulSoup(resp.text, 'html.parser')
            extract_ranking(gd, soup.find(id='ranking'))
        meta.curr_gd = curr_gd
        meta.save()

    meta.last_updated = timezone.now()
    meta.save()

    return HttpResponse(status=204)

def extract_ranking(gd, ranking, checkFinished=False):
    games = ranking.find_all('th', class_='ereignis')
    if checkFinished and games[8].find('span', class_='kicktipp-heim').string == '-':  # TODO check if finished
        return

    game_objects = []
    for game in games:
        home = game.find('div', class_='headerbox')
        away = home.find_next()
        home_team = Team.objects.get(abbr=home.string)
        away_team = Team.objects.get(abbr=away.string)
        try:
            score_home = int(game.find('span', class_='kicktipp-heim').string)
            score_away = int(game.find('span', class_='kicktipp-gast').string)
        except ValueError:
            continue

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
            except (TypeError, ValueError):
                continue
            user_obj = User.objects.get(name=name)
            game = game_objects[game_idx]

            Prediction.objects.create(
                user=user_obj,
                game=game,
                score_home=score_home,
                score_away=score_away,
                points=points
            )

            user_obj.preds += 1
            user_obj.goals += score_home + score_away
            user_obj.save()

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

    if user is not None:
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

def __create_table_json(rank, stat, rank_diff=None):
    rank_diff_icon = ''
    if (rank_diff is not None):
        if (rank_diff < 0):
            rank_diff_icon = 'arrow_drop_down'
            rank_diff = -rank_diff
        elif (rank_diff > 0):
            rank_diff_icon = 'arrow_drop_up'
        else:
            rank_diff_icon = 'arrow_right'
    return {
        'rank': rank,
        'rank_diff': rank_diff,
        'rank_diff_icon': rank_diff_icon,
        'team': stat.team.name,
        'games': stat.wins + stat.draws + stat.losses,
        'wins': stat.wins,
        'draws': stat.draws,
        'losses': stat.losses,
        'goals': stat.goals,
        'goals_against': stat.goals_against,
        'diff': stat.goals - stat.goals_against,
        'points': stat.points
    }
