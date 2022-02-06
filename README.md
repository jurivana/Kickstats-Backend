# Kickstats

## Deployment

### Containerize

```sh
gcloud builds submit --tag gcr.io/kickstats-backend/kickstats
gcloud run deploy --image gcr.io/kickstats-backend/kickstats
```

### Deploy
```sh
firebase init
firebase deploy
```

## Development

### Setup workspace
```sh
git clone 
cd Kickstats
```

### Install dependencies
```sh
py -m venv venv
venv/Scripts/activate
py -m pip install -r requirements.txt
```