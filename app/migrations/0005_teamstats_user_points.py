# Generated by Django 3.1.5 on 2021-01-21 08:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_auto_20210119_1736'),
    ]

    operations = [
        migrations.AddField(
            model_name='teamstats',
            name='user_points',
            field=models.IntegerField(default=0),
        ),
    ]
