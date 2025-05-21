"""
執行命令 `uv run ams.py --help`
"""

import csv
from dataclasses import dataclass
import httpx
import typer
import hashlib
import hmac
from rich import print as rprint

app = typer.Typer()


@dataclass
class Profile:
    api_url: str
    streams_csv: str
    origin_ip: str


profiles = dict(
    sms1=Profile(
        api_url="http://220.130.51.197:5080/WebRTCAppEE/rest/v2",
        streams_csv="AMS/streams_sms1.csv",
        origin_ip="220.130.51.197",
    ),
    sms2=Profile(
        api_url="http://61.222.163.125:5080/WebRTCAppEE/rest/v2",
        origin_ip="61.222.163.125",
        streams_csv="AMS/streams_sms2.csv",
    ),
    sms3=Profile(
        api_url="http://61.222.163.102:5080/WebRTCAppEE/rest/v2",
        origin_ip="61.222.163.102",
        streams_csv="AMS/streams_sms3.csv",
    ),
    sms4=Profile(
        api_url="http://61.222.163.104:5080/WebRTCAppEE/rest/v2",
        origin_ip="61.222.163.104",
        streams_csv="AMS/streams_sms4.csv",
    ),
    _7ms1=Profile(
        api_url="http://220.130.51.248:5080/WebRTCAppEE/rest/v2",
        origin_ip="220.130.51.248",
        streams_csv="AMS/streams_7ms1.csv",
    ),
    _7ms2=Profile(
        api_url="http://61.222.163.86:5080/WebRTCAppEE/rest/v2",
        origin_ip="61.222.163.86",
        streams_csv="AMS/streams_7ms2.csv",
    ),
    _7ms3=Profile(
        api_url="http://61.222.163.110:5080/WebRTCAppEE/rest/v2",
        origin_ip="61.222.163.110",
        streams_csv="AMS/streams_7ms3.csv",
    ),
    _7ms4=Profile(
        api_url="http://61.220.197.203:5080/WebRTCAppEE/rest/v2",
        origin_ip="61.220.197.203",
        streams_csv="AMS/streams_7ms4.csv",
    ),
)


def generate_stream_id(name: str, secret_key: str = "ams") -> str:
    h = hmac.new(secret_key.encode(), name.encode(), hashlib.md5)
    return f"{name}_{h.hexdigest()}"


def select_profile() -> Profile:
    rprint("Profiles:", [key for key in profiles.keys()])
    profile = None
    while True:
        selected = str(typer.prompt("使用profile")).strip()
        profile = profiles.get(selected)
        if profile:
            break
        print(f"Profile '{selected}' not found.")

    print(f"--- profile: {selected} ---")
    rprint(profile.__dict__)
    print("---")
    typer.confirm(
        "請確認以上資料正確無誤, 確認執行?",
        abort=True,
    )
    return profile


@app.command()
def create_streams():
    """
    建立流
    """
    profile = select_profile()
    client = httpx.Client(base_url=profile.api_url, timeout=60)

    offset = 0
    size = 10000
    resp = client.get(f"/broadcasts/list/{offset}/{size}")
    streams = resp.json()
    stream_ids = {stream["streamId"] for stream in streams}

    with open(profile.streams_csv, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            stream_id = generate_stream_id(row["code"])
            stream_url = ""
            if row["stream_ip"].lower().startswith("rtsp://"):
                stream_url = row["stream_ip"]
            else:
                stream_username = row["stream_username"]
                stream_password = row["stream_password"]
                stream_url = f"rtsp://{stream_username}:{stream_password}@{row['stream_ip']}/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"

            payload = {
                "streamId": stream_id,
                "name": row["code"],
                "description": row.get("description", ""),
                "type": "streamSource",
                "streamUrl": stream_url,
                "originAdress": row.get("originAdress", profile.origin_ip),
                "webRTCViewerLimit": 20,
                "metaData": row.get("metaData", ""),
            }

            if stream_id in stream_ids:
                print(f"streamId {stream_id} already exists, skipping...")
                continue

            else:
                print(f"streamId {stream_id} does not exist, creating...", end="")
                resp = client.post("/broadcasts/create?autoStart=true", json=payload)

                result = typer.style("success", fg=typer.colors.GREEN, bold=True)
                print(result)


@app.command()
def start_all_streams():
    """
    某些情況下AMS可能會沒自動開啟拉流, 這可以一次全部啟動
    """
    profile = select_profile()
    client = httpx.Client(base_url=profile.api_url, timeout=60)

    offset = 0
    size = 10000
    resp = client.get(f"/broadcasts/list/{offset}/{size}")
    streams = resp.json()
    stream_ids = {stream["streamId"] for stream in streams}

    for stream_id in stream_ids:
        print(f"streamId {stream_id} starting...", end="")
        resp = client.post(f"/broadcasts/{stream_id}/start")
        result = typer.style("success", fg=typer.colors.GREEN, bold=True)
        print(result)


@app.command()
def stop_all_streams():
    """
    停止全部流
    """
    profile = select_profile()
    client = httpx.Client(base_url=profile.api_url, timeout=60)

    offset = 0
    size = 10000
    resp = client.get(f"/broadcasts/list/{offset}/{size}")
    streams = resp.json()
    stream_ids = {stream["streamId"] for stream in streams}

    for stream_id in stream_ids:
        print(f"streamId {stream_id} stopping...", end="")
        resp = client.post(f"/broadcasts/{stream_id}/stop")
        result = typer.style("success", fg=typer.colors.GREEN, bold=True)
        print(result)


@app.command()
def delete_all_streams():
    """
    刪除全部流
    """
    profile = select_profile()
    client = httpx.Client(base_url=profile.api_url, timeout=60)

    offset = 0
    size = 10000
    resp = client.get(f"/broadcasts/list/{offset}/{size}")
    streams = resp.json()
    stream_ids = {stream["streamId"] for stream in streams}

    for stream_id in stream_ids:
        print(f"streamId {stream_id} deleting...", end="")
        resp = client.delete(f"/broadcasts/{stream_id}")
        result = typer.style("success", fg=typer.colors.GREEN, bold=True)
        print(result)


if __name__ == "__main__":
    app()
