py manage.py makemigrations
py manage.py migrate
py -m pip freeze > requirements.txt
gcloud builds submit --tag gcr.io/kickstats-backend/kickstats
gcloud run deploy --image gcr.io/kickstats-backend/kickstats