import os
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import time
from zoneinfo import ZoneInfo


today_us = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
load_dotenv(override=True)
API_KEY = os.getenv("BALLDONTLIE_API_KEY", "").strip()
def get_season():
    now = datetime.now()
    if now.month < 10:
        return now.year -1
    else:
        return now.year

seasonsneeded = [get_season() - x for x in reversed(range(6))]
def fetch_all_games(seasons, start_date = None, end_date = None):
    url = "https://api.balldontlie.io/v1/games"
    headers = {"Authorization": API_KEY}
    params = {"seasons[]": seasons, "per_page": 100}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
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
    is_current = (season == get_season())
    if os.path.exists(path) and not is_current:
        print(f"Season {season}: pakai cache")
        return pd.read_csv(path)
    end_date = datetime.now().strftime("%Y-%m-%d") if is_current else None
    print(f"Season {season}: fetch dari API (end_date={end_date})...")
    games = fetch_all_games([season], end_date=end_date)
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
df1 = df1.sort_values(["season", "date"]).reset_index(drop=True)
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

games = fetch_all_games([get_season()], start_date=today_us, end_date=today_us)
matchmendatang = pd.json_normalize(games)
matchmendatang = matchmendatang.loc[matchmendatang['status_state'] == 'scheduled']

dframe = df_elo_result.copy()
dframe["home_res"] = (dframe["home_team_score"] > dframe["visitor_team_score"]).astype(int)
dframe["elo_diff"] = (dframe["home_elo_before"] - dframe["visitor_elo_before"])
print(dframe[["home_res", "elo_diff"]].head())
print(dframe["home_res"].value_counts())


if matchmendatang.empty:
    print("No game today huhu")
else:
    probs = []
    for game in matchmendatang.to_dict('records'):
        home_elo = latest_elo.get(game['home_team.id'], 1500)
        visitor_elo = latest_elo.get(game['visitor_team.id'], 1500)
        prob_home = 1/(1+10**((visitor_elo - (home_elo + 60)) / 400))
        probs.append(prob_home)
    matchmendatang['prob_home_win'] = probs
# Tampilkan Elo terbaru setiap tim
teams = (
    df_elo_result[
        ["home_team.id", "home_team.full_name"]
    ]
    .rename(columns={
        "home_team.id": "team_id",
        "home_team.full_name": "team_name"
    })
    .drop_duplicates("team_id")
)

teams["elo"] = teams["team_id"].map(latest_elo)

teams = teams.sort_values("elo", ascending=False)

print("\n=== LATEST NBA ELO RATINGS ===")
print(teams[["team_name", "elo"]].to_string(index=False))


