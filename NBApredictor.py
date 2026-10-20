import os
import requests
import pandas as pd
from dotenv import load_dotenv
load_dotenv(override=True)
API_KEY = os.getenv("BALLDONTLIE_API_KEY", "").strip()

url = "https://api.balldontlie.io/v1/games"
headers = {"Authorization": API_KEY}

response = requests.get(url, headers=headers)

if response.status_code != 200:
    print("Oops:", response.status_code, response.text)
    raise SystemExit

dataURL = response.json()
print(type(dataURL))
Dataframe = pd.json_normalize(dataURL["data"])
