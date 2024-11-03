import os

import requests
from celery import shared_task
from dotenv import load_dotenv

load_dotenv()

API = "https://api.telegram.org"
CHAT_ID = os.environ.get("CHAT_ID")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
METHOD = "sendMessage"


@shared_task
def send_notification(text):
    response = requests.post(
        url=f"{API}/bot{BOT_TOKEN}/{METHOD}",
        data={"chat_id": CHAT_ID, "text": text},
    )
    return response.status_code
