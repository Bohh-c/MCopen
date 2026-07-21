import requests
import time
import webbrowser
import json
import os
from pathlib import Path

CLIENT_ID = "暂时保密，暂未做加密部分"
TOKEN_FILE = Path("./refresh_token.json")

def load_refresh_token():
    try:
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
            return data.get("refresh_token")
    except:
        return None

def save_refresh_token(refresh_token):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"refresh_token": refresh_token}, f)
        os.chmod(TOKEN_FILE, 0o600)
    except:
        print("保存刷新令牌失败")
        return

def get_device_code():
    resp = requests.post(
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode",
        data={
            "client_id": CLIENT_ID,
            "scope": "XboxLive.signin offline_access"
        }
    )
    if resp.status_code != 200:
        print("获取设备码失败:", resp.text)
        return None
    return resp.json()

def poll_for_token(device_data):
    print("等待授权...")
    while True:
        time.sleep(5)
        resp = requests.post(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_data["device_code"]
            }
        )
        if resp.status_code == 200:
            print("获取OAuth令牌成功")
            return resp.json()
        elif resp.status_code == 400:
            error = resp.json().get("error")
            if error == "authorization_pending":
                print(".", end="", flush=True)
                continue
            elif error == "slow_down":
                time.sleep(10)
                continue
            else:
                print("轮询错误:", resp.text)
                return None
        else:
            print("请求令牌失败:", resp.text)
            return None

def xbox_live_auth(access_token):
    url = "https://user.auth.xboxlive.com/user/authenticate"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"d={access_token}"
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT"
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print("Xbox Live认证失败:", resp.text)
        return None
    data = resp.json()
    return {
        "token": data["Token"],
        "user_hash": data["DisplayClaims"]["xui"][0]["uhs"]
    }

def xsts_auth(xbox_token):
    url = "https://xsts.auth.xboxlive.com/xsts/authorize"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "Properties": {
            "SandboxId": "RETAIL",
            "UserTokens": [xbox_token]
        },
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT"
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print("XSTS认证失败:", resp.text)
        return None
    return resp.json()["Token"]

def minecraft_auth(xsts_token, user_hash):
    url = "https://api.minecraftservices.com/authentication/login_with_xbox"
    headers = {"Content-Type": "application/json"}
    payload = {
        "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print("Minecraft认证失败:", resp.text)
        return None
    data = resp.json()
    access_token = data["access_token"]
    profile_resp = requests.get(
        "https://api.minecraftservices.com/minecraft/profile",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if profile_resp.status_code != 200:
        print("获取玩家信息失败:", profile_resp.text)
        return None
    profile = profile_resp.json()
    return {
        "access_token": access_token,
        "uuid": profile["id"],
        "name": profile["name"],
        "refresh_token": data.get("refresh_token")
    }

def main():
    refresh_token = load_refresh_token()
    if refresh_token:
        print("尝试使用刷新令牌自动登录...")
        try:
            resp = requests.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": "XboxLive.signin offline_access"
                }
            )
            if resp.status_code == 200:
                token_data = resp.json()
                oauth_access_token = token_data["access_token"]
                new_refresh = token_data.get("refresh_token")
                if new_refresh:
                    save_refresh_token(new_refresh)
                xbox_result = xbox_live_auth(oauth_access_token)
                if xbox_result:
                    xsts = xsts_auth(xbox_result["token"])
                    if xsts:
                        mc_result = minecraft_auth(xsts, xbox_result["user_hash"])
                        if mc_result:
                            print(f"自动登录成功！玩家: {mc_result['name']}, UUID: {mc_result['uuid']}")
                            return
        except:
            pass
        print("刷新令牌无效，进行完整登录")

    device_data = get_device_code()
    if not device_data:
        return
    print(f"\n请访问 {device_data['verification_uri']} 并输入代码: {device_data['user_code']}")
    webbrowser.open(device_data['verification_uri'])
    oauth_data = poll_for_token(device_data)
    if not oauth_data:
        return
    oauth_access_token = oauth_data["access_token"]
    if "refresh_token" in oauth_data:
        save_refresh_token(oauth_data["refresh_token"])

    xbox_result = xbox_live_auth(oauth_access_token)
    if not xbox_result:
        return
    xsts = xsts_auth(xbox_result["token"])
    if not xsts:
        return
    mc_result = minecraft_auth(xsts, xbox_result["user_hash"])
    if mc_result:
        print(f"\n登录成功！")
        print(f"玩家名: {mc_result['name']}")
        print(f"UUID:   {mc_result['uuid']}")
        if mc_result.get("refresh_token"):
            save_refresh_token(mc_result["refresh_token"])
    else:
        print("登录失败，请检查应用是否已获得Minecraft API权限。")

if __name__ == "__main__":
    main()