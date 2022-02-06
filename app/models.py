from django.db import models
from django.utils import timezone


class Team(models.Model):
    name = models.CharField(max_length=32, unique=True)
    abbr = models.CharField(max_length=8)


class User(models.Model):
    name = models.CharField(max_length=32, unique=True)
    preds = models.IntegerField(default=0)
    goals = models.IntegerField(default=0)


class Game(models.Model):
    home = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_game_set')
    away = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_game_set')
    gameday = models.IntegerField()
    score_home = models.IntegerField()
    score_away = models.IntegerField()


class Prediction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    score_home = models.IntegerField(null=True)
    score_away = models.IntegerField(null=True)
    points = models.IntegerField()


class Stats(models.Model):
    TOTAL = 't'
    HOME = 'h'
    AWAY = 'a'
    TYPE_CHOICES = [
        (TOTAL, 'total'),
        (HOME, 'home'),
        (AWAY, 'away')
    ]
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TOTAL)
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    wins = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    goals = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    user_points = models.IntegerField(default=0)
    four_points = models.IntegerField(default=0)
    three_points = models.IntegerField(default=0)
    two_points = models.IntegerField(default=0)
    zero_points = models.IntegerField(default=0)


class Meta(models.Model):
    version = models.IntegerField(default=0)
    curr_gd = models.IntegerField(default=1)
    last_updated = models.DateTimeField(default=timezone.now)
    last_started = models.DateTimeField(default=timezone.now)
