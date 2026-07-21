import msal
import requests
import json
import os

CLIENT_ID = "00000000402b5328"
SCOPE = ["email"]
TOKEN_CACHE_FILE = "token_cache.json"

def load_cache(app):
    try:
        if os.path.exists(TOKEN_CACHE_FILE):
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                app.token_cache.deserialize(cache_data)
    except Exception:
        pass

def save_cache(app):
    with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(app.token_cache.serialize(), f, ensure_ascii=False, indent=2)

def get_silent_ms_token():
    app = msal.PublicClientApplication(CLIENT_ID)
    load_cache(app)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPE, account=accounts[0])
        if result:
            save_cache(app)
            return result
    print("请先通过原版 Minecraft Windows 客户端完成正版账号登录一次")
    return None

def get_minecraft_token(ms_access_token):
    xbl_res = requests.post(
        "https://user.auth.xboxlive.com/user/authenticate",
        json={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={ms_access_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
    )
    xbl_json = xbl_res.json()
    xsts_res = requests.post(
        "https://xsts.auth.xboxlive.com/xsts.auth.xboxlive.com/authorize",
        json={
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbl_json["Token"]]
            },
            "RelyingParty": "https://api.minecraftservices.com",
            "TokenType": "JWT"
        }
    )
    xsts_json = xsts_res.json()
    mc_res = requests.post(
        "https://api.minecraftservices.com/authentication/login_with_xbox",
        json={
            "identityToken": f"XBL3.0 x={xbl_json['DisplayClaims']['xui'][0]['uhs']};{xsts_json['Token']}"
        }
    )
    return mc_res.json()

if __name__ == "__main__":
    ms_token = get_silent_ms_token()
    if ms_token:
        mc_data = get_minecraft_token(ms_token["access_token"])
        print("Minecraft正版访问令牌：")
        print(mc_data["access_token"])
    else:
        print("暂无有效正版缓存，请先原版MC登录一次")