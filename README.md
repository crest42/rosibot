# Configuration 

## Create Env file
For this bot to run we need an .env file with three parameter:

```
PHONE_NUMBER=+49123456789 # The linked Phone number that should be used for the bot
SIGNAL_SERVICE=127.0.0.1:8080 # singal-cli-rest-apis endpoint
SIGNAL_GROUP_ID="group.FOOBAR=" # The unique Signal group id to interact with
```

## Install Dependencies

> python -mvenv .venv
> source .venv/bin/activate
> pip install -r requirements.txt

# Run

> source .venv/bin/activate
> python main.py