"""
執行命令 `uv run ams.py --help`
"""

import csv
from dataclasses import dataclass
from collections import Counter
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
    return f"{name}{h.hexdigest()}"


def print_result(success: bool, msg: str = ""):
    """印出成功或失敗訊息"""
    if success:
        print(typer.style("success", fg=typer.colors.GREEN, bold=True))
    else:
        print(typer.style(f"failed: {msg}", fg=typer.colors.RED, bold=True))


def check_result_response(resp: httpx.Response) -> tuple[bool, str]:
    """檢查返回 Result 物件的 API 回應"""
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    data = resp.json()
    if data.get("success"):
        return True, ""
    return False, data.get("message", "Unknown error")


def check_broadcast_response(resp: httpx.Response) -> tuple[bool, str]:
    """檢查返回 Broadcast 物件的 API 回應"""
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    data = resp.json()
    if data.get("streamId"):
        return True, ""
    return False, data.get("message", "Unknown error")


def select_profile() -> Profile:
    rprint("Profiles:", list(profiles.keys()))
    while True:
        selected = typer.prompt("使用profile").strip()
        if profile := profiles.get(selected):
            break
        print(f"Profile '{selected}' not found.")

    print(f"--- profile: {selected} ---")
    rprint(profile.__dict__)
    print("---")
    typer.confirm("請確認以上資料正確無誤, 確認執行?", abort=True)
    return profile


def get_client_and_streams(profile: Profile) -> tuple[httpx.Client, list[dict]]:
    """取得 HTTP client 和所有串流列表 (支援分頁)"""
    client = httpx.Client(base_url=profile.api_url, timeout=60)
    try:
        all_streams: list[dict] = []
        offset = 0
        size = 1000  # 每次獲取 1000 筆
        while True:
            resp = client.get(f"/broadcasts/list/{offset}/{size}")
            resp.raise_for_status()  # 針對 4xx/5xx 回應拋出例外
            batch = resp.json()
            if not batch:
                break
            all_streams.extend(batch)
            if len(batch) < size:
                break
            offset += size
        return client, all_streams
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        print(typer.style(f"無法獲取串流列表: {e}", fg=typer.colors.RED, bold=True))
        raise typer.Exit(1)


@app.command()
def create_streams(
    stream_type: str = typer.Option(
        "ipcam", "--type",
        help="串流類型: 'ipcam' (IP Camera) 或 'source' (RTSP 串流源)"
    )
):
    """建立流 (ipcam: IP Camera 模式, source: RTSP 串流源模式)"""
    if stream_type not in ["ipcam", "source"]:
        raise typer.Exit(f"錯誤: --type 必須是 'ipcam' 或 'source'")

    profile = select_profile()
    client, streams = get_client_and_streams(profile)
    existing_ids = {s["streamId"] for s in streams}

    with open(profile.streams_csv, newline="") as csvfile:
        for row in csv.DictReader(csvfile):
            stream_id = generate_stream_id(row["code"])

            if stream_id in existing_ids:
                print(f"streamId {stream_id} already exists, skipping...")
                continue

            # 建立 payload
            payload = {
                "streamId": stream_id,
                "name": row["code"],
                "description": row.get("description", ""),
                "originAdress": row.get("originAdress", profile.origin_ip),
                "webRTCViewerLimit": 10,
                "metaData": row.get("metaData", ""),
            }

            if stream_type == "ipcam":
                payload.update({
                    "type": "ipCamera",
                    "ipAddr": row["stream_ip"],
                    "username": row.get("stream_username", ""),
                    "password": row.get("stream_password", ""),
                })
            else:
                if row["stream_ip"].lower().startswith("rtsp://"):
                    stream_url = row["stream_ip"]
                else:
                    stream_url = (
                        f"rtsp://{row.get('stream_username', '')}:{row.get('stream_password', '')}"
                        f"@{row['stream_ip']}/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"
                    )
                payload.update({"type": "streamSource", "streamUrl": stream_url})

            print(f"streamId {stream_id} (type={payload['type']}) creating...", end="")
            resp = client.post("/broadcasts/create?autoStart=true", json=payload)
            success, msg = check_broadcast_response(resp)
            print_result(success, msg)


@app.command()
def start_all_streams():
    """啟動所有串流"""
    profile = select_profile()
    client, streams = get_client_and_streams(profile)

    for stream in streams:
        stream_id = stream["streamId"]
        print(f"streamId {stream_id} starting...", end="")
        resp = client.post(f"/broadcasts/{stream_id}/start")
        success, msg = check_result_response(resp)
        print_result(success, msg)


@app.command()
def stop_all_streams():
    """停止所有串流"""
    profile = select_profile()
    client, streams = get_client_and_streams(profile)

    for stream in streams:
        stream_id = stream["streamId"]
        print(f"streamId {stream_id} stopping...", end="")
        resp = client.post(f"/broadcasts/{stream_id}/stop")
        success, msg = check_result_response(resp)
        print_result(success, msg)


@app.command()
def delete_all_streams():
    """刪除所有串流"""
    profile = select_profile()
    client, streams = get_client_and_streams(profile)

    for stream in streams:
        stream_id = stream["streamId"]
        print(f"streamId {stream_id} deleting...", end="")
        resp = client.delete(f"/broadcasts/{stream_id}")
        success, msg = check_broadcast_response(resp)
        print_result(success, msg)


@app.command()
def query():
    """查詢伺服器上的串流狀態"""
    profile = select_profile()
    client, streams = get_client_and_streams(profile)

    try:
        # 伺服器資訊
        resp = client.get("/version")
        if resp.status_code == 200:
            v = resp.json()
            print(f"\n版本: {v.get('versionName')} ({v.get('versionType')}) Build: {v.get('buildNumber')}")

        # 統計
        resp = client.get("/broadcasts/active-live-stream-count")
        if resp.status_code == 200:
            print(f"活躍直播: {resp.json().get('number', 0)} / 總計: {len(streams)}")
    except httpx.RequestError as e:
        print(typer.style(f"獲取伺服器資訊失敗: {e}", fg=typer.colors.YELLOW))

    if not streams:
        print("目前沒有任何串流")
        return

    # 狀態統計
    print(f"狀態: {dict(Counter(s.get('status', 'unknown') for s in streams))}")
    print(f"類型: {dict(Counter(s.get('type', 'unknown') for s in streams))}")

    # 串流列表
    print(f"\n{'streamId':<50} {'name':<20} {'type':<15} {'status':<15}")
    print("-" * 100)
    status_colors = {
        "broadcasting": typer.colors.GREEN,
        "created": typer.colors.YELLOW,
        "finished": typer.colors.RED,
        "failed": typer.colors.RED,
        "error": typer.colors.RED,
    }
    for s in streams:
        status = s.get("status", "N/A")
        color = status_colors.get(status)
        status_display = typer.style(status, fg=color) if color else status
        print(f"{s.get('streamId', 'N/A'):<50} {s.get('name', 'N/A'):<20} {s.get('type', 'N/A'):<15} {status_display:<15}")


@app.command()
def query_stream(stream_id: str = typer.Argument(..., help="要查詢的串流 ID")):
    """查詢單一串流的詳細資訊"""
    profile = select_profile()
    client = httpx.Client(base_url=profile.api_url, timeout=60)

    try:
        resp = client.get(f"/broadcasts/{stream_id}")
        if resp.status_code == 404:
            print(f"串流 {stream_id} 不存在")
            return
        if resp.status_code != 200:
            print(f"查詢失敗: HTTP {resp.status_code}")
            return

        stream = resp.json()
        rprint("\n--- 串流詳細資訊 ---", stream)

        # 觀看統計
        stats_resp = client.get(f"/broadcasts/{stream_id}/broadcast-statistics")
        if stats_resp.status_code == 200:
            stats = stats_resp.json()
            print(f"\n觀眾: HLS={stats.get('totalHLSWatchersCount', 0)} WebRTC={stats.get('totalWebRTCWatchersCount', 0)} "
                  f"RTMP={stats.get('totalRTMPWatchersCount', 0)} DASH={stats.get('totalDASHWatchersCount', 0)}")

        # IP Camera 錯誤檢查
        if stream.get("type") in ["ipCamera", "streamSource"]:
            err_resp = client.get(f"/broadcasts/{stream_id}/ip-camera-error")
            if err_resp.status_code == 200:
                err = err_resp.json()
                # 注意: /ip-camera-error API 的回應中, 'success' 為 true 表示「成功獲取到錯誤訊息」,
                # 亦即串流本身有錯誤。這與其他 API 的 'success' 欄位含義相反。
                if err.get("success"):
                    print(typer.style(f"錯誤: {err.get('message', 'N/A')}", fg=typer.colors.RED))
                else:
                    print(typer.style("無錯誤", fg=typer.colors.GREEN))
    except httpx.RequestError as e:
        print(typer.style(f"網路請求失敗: {e}", fg=typer.colors.RED, bold=True))


if __name__ == "__main__":
    app()
