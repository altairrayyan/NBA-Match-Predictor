import os
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import time
load_dotenv(override=True)
API_KEY = os.getenv("BALLDONTLIE_API_KEY", "").strip()

def get_season():
    now = datetime.now()
    if now.month < 10:
        return now.year -1
    else:
        return now.year

seasonsneeded = [get_season() - x for x in reversed(range(6))]

def fetch_all_games(seasons):
    url = "https://api.balldontlie.io/v1/games"
    headers = {"Authorization": API_KEY}
    params = {"seasons[]": seasons, "per_page": 100}

    all_games = []
    while True:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 60))
            print(f"Rate limit, tunggu {wait} detik...")
            time.sleep(wait)
            continue

        if response.status_code != 200:
            print("Oops:", response.status_code, response.text)
            raise SystemExit

        payload = response.json()
        all_games.extend(payload["data"])
        print(f"{len(all_games)} games terambil")

        next_cursor = payload.get("meta", {}).get("next_cursor")
        if next_cursor is None:
            break
        params["cursor"] = next_cursor

    return all_games
def fetch_season(season):
    path = f"games_{season}.csv"
    if os.path.exists(path) and season != get_season():
        print(f"Season {season}: pakai cache")
        return pd.read_csv(path)
    print(f"Season {season}: fetch dari API...")
    games = fetch_all_games([season])
    if not games:
        return pd.DataFrame()
    df_season = pd.json_normalize(games)
    df_season.to_csv(path, index=False)
    return df_season

frames = [fetch_season(s) for s in seasonsneeded]
Dataframe = pd.concat([f for f in frames if not f.empty], ignore_index=True)

df = Dataframe.drop(columns=['home_q1', 'home_q2', 'home_q3', 'home_q4','home_ot1',
       'home_ot2', 'home_ot3','visitor_q1', 'visitor_q2', 'visitor_q3', 'visitor_q4', 'visitor_ot1',
       'visitor_ot2', 'visitor_ot3','visitor_timeouts_remaining',
       'visitor_in_bonus','home_timeouts_remaining', 'home_in_bonus'], errors='ignore')
print(df.columns)
df['date'] = pd.to_datetime(df['date'], format="mixed")
df = df[df['status'] == 'Final']
df = df.loc[(df.season >= 2019) & (df.season.isin(seasonsneeded))].copy()
df = df.sort_values('date', ascending=True).reset_index(drop=True)
df1 = df.copy()
def baselineelo(df1, elobase = 1500, homeadvantage = 60, kval = 20):
    games = df1.to_dict('records')
    elodictionary = {}
    current_season = None
    home_elobefore = []
    visitor_elobefore = []
    for game in games:
        if current_season is not None and game['season'] != current_season:
            for team in elodictionary:
                elodictionary[team] = (0.75 * elodictionary[team]) + (0.25 * elobase)
        current_season = game['season']
        hometeam = game['home_team.id']
        visitorteam = game['visitor_team.id']
        hometeamelo = elodictionary.get(hometeam, elobase)
        visitorteamelo = elodictionary.get(visitorteam, elobase)
        home_elobefore.append(hometeamelo)
        visitor_elobefore.append(visitorteamelo)
        prob_home = 1 / (1 + 10 ** ((visitorteamelo - (hometeamelo + homeadvantage)) / 400))
        actual_home = 1.0 if game['home_team_score'] > game['visitor_team_score'] else 0.0
        change = kval * (actual_home - prob_home)
        elodictionary[hometeam] = hometeamelo + change
        elodictionary[visitorteam] = visitorteamelo - change
    df1['home_elo_before'] = home_elobefore
    df1['visitor_elo_before'] = visitor_elobefore
    return df1, elodictionary
df_elo_result, latest_elo = baselineelo(df1)
print(df_elo_result.head())





