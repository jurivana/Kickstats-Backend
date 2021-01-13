from django.db import models

class Team(models.Model):
    name = models.CharField(max_length=32, primary_key=True)
    abbr = models.CharField(max_length=8)

class User(models.Model):
    name = models.CharField(max_length=32, primary_key=True)

class Game(models.Model):
    home = models.ForeignKey(Team, on_delete=models.DO_NOTHING, related_name='home_game_set')
    away = models.ForeignKey(Team, on_delete=models.DO_NOTHING, related_name='away_game_set')
    gameday = models.IntegerField()
    score_home = models.IntegerField()
    score_away = models.IntegerField()

class Prediction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    score_home = models.IntegerField()
    score_away = models.IntegerField()
    points = models.IntegerField()

class Meta(models.Model):
    version = models.IntegerField()
    