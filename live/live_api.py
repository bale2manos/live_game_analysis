import requests

def get_boxscore_api(game_id):
    url = f"https://livestats.api.feb.es/api/BoxScore?gamecode={game_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    data = get_boxscore_api("2487637")
    print(data)
