#!/usr/bin/env python3
"""
AMS 管理工具 - 使用 httpx 庫與 Ant Media Server 進行 API 互動
"""

import httpx
import csv
import hashlib
import hmac
import sys
from typing import List, Dict, Any, Optional


def generate_stream_id(name: str, secret_key: str = "ams") -> str:
    name_lower = name.lower()  # 將名稱轉為小寫
    h = hmac.new(secret_key.encode(), name.encode(), hashlib.md5)
    return f"{name_lower}{h.hexdigest()}"  # 去掉底線


def generate_hash_from_name(name: str, secret_key: str = "ams") -> str:
    h = hmac.new(secret_key.encode(), name.encode(), hashlib.md5)
    return h.hexdigest()


def ip_location(subnet: int, id: int) -> int:
    """計算 IP 地址中的最後一個數字"""
    if subnet == 11:
        return id
    elif subnet == 12:
        return id - 200
    elif subnet in (14, 15):
        return id - 300
    elif subnet == 13:
        if id > 400:
            return id - 400
        elif id > 300:
            return id - 300
        else:
            return id
    else:
        raise ValueError(f"不支援的子網段: {subnet}")


def fetch_all_broadcasts(
    media_server_ip: str, media_server_port: int
) -> List[Dict[str, Any]]:
    """獲取所有攝影機串流資訊"""
    all_data = []
    offset = 0
    batch_size = 1000

    while True:
        url = f"http://{media_server_ip}:{media_server_port}/WebRTCAppEE/rest/v2/broadcasts/list/{offset}/{batch_size}"
        r = httpx.get(url, timeout=20)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < batch_size:
            break  # 最後一批
        offset += batch_size
    return all_data


def do_create(
    media_server_ip: str,
    media_server_port: int,
    username: str,
    password: str,
    zone: str,
    subnet: int,
    start_id: int,
    end_id: int,
) -> None:
    """批量建立攝影機串流"""
    results = []
    fail_count = 0
    url = f"http://{media_server_ip}:{media_server_port}/WebRTCAppEE/rest/v2/broadcasts/create?autoStart=true"

    print("這批攝影機是否為備源？輸入 yes 則會自動加 -1：")
    is_backup_input = input().strip().lower()
    is_backup_batch = is_backup_input == "yes"

    for id in range(start_id, end_id + 1):
        suffix = ip_location(subnet, id)
        ip_addr = f"192.168.{subnet}.{suffix}"

        base_name = f"{zone}{id if id > 100 else f'0{id}'}"
        name = f"{base_name}-1" if is_backup_batch else base_name
        stream_id = f"{name}{generate_hash_from_name(base_name)}"

        data = {
            "streamId": stream_id,
            "hlsViewerCount": 0,
            "dashViewerCount": 0,
            "webRTCViewerCount": 0,
            "rtmpViewerCount": 0,
            "mp4Enabled": 0,
            "playlistLoopEnabled": True,
            "autoStartStopEnabled": False,
            "plannedStartDate": 0,
            "playListItemList": [],
            "ipAddr": ip_addr,
            "name": name,
            "username": username,
            "password": password,
            "type": "ipCamera",
        }
        print(data)

        response = httpx.post(url, json=data, timeout=10)

        if response.status_code == 200:
            results.append({"id": id, "name": name})
        else:
            fail_count += 1
            print(f"❌ {name} 建立失敗:HTTP {response.status_code} → {response.text}")

    success_count = len(results)
    total_count = end_id - start_id + 1
    print(f"建立完畢: 共{total_count}，成功 {success_count} 筆，失敗{fail_count}筆。")

    # 建立成功後寫入 CSV
    with open("created_streams.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["Name", "Stream ID"])
        for r in results:
            base_name = r["name"]
            stream_id = f"{base_name.lower()}{generate_hash_from_name(base_name.replace('-1',''))}"
            writer.writerow([base_name, stream_id])

    print("✅ 已匯出 created_streams.csv")


def do_export(media_server_ip: str, media_server_port: int) -> None:
    """匯出串流列表"""
    data = fetch_all_broadcasts(media_server_ip, media_server_port)

    print("請輸入要匯出的區域（如 A/B/C）：")
    zone_prefix = input().strip().upper()

    # 篩選條件：名稱以指定字母開頭，且不是備源（不以 -1 結尾）
    filtered = [
        i
        for i in data
        if i["name"].startswith(zone_prefix) and not i["name"].endswith("-1")
    ]

    def name_sort_key(x):
        name = x["name"]
        digits = "".join(filter(str.isdigit, name[1:]))
        return int(digits) if digits.isdigit() else float("inf")

    filtered.sort(key=name_sort_key)

    with open("stream_id_sheet.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["Name", "Stream ID", "Camera IP"])
        for i in filtered:
            writer.writerow([i["name"], i["streamId"], i.get("ipAddr", "")])

    print(
        f"✅ 區域 {zone_prefix} 主源匯出完成，共 {len(filtered)} 筆 → stream_id_sheet.csv"
    )


def do_delete(media_server_ip: str, media_server_port: int) -> None:
    """刪除指定區域的攝影機"""
    list_url = (
        f"http://{media_server_ip}:{media_server_port}"
        "/WebRTCAppEE/rest/v2/broadcasts/list/0/1000"
        "?sort_by=name&order_by=asc"
    )
    r = httpx.get(list_url, timeout=10)
    r.raise_for_status()
    data = r.json()

    print("請輸入所要刪除的機台區域 (e.g. A/B/C/D):")
    prefix = input().strip().upper()
    delete = [i["streamId"] for i in data if i["name"].startswith(prefix)]
    if not delete:
        print(f"⚠️ 沒有找到任何以「{prefix}」開頭的機台。")
        return

    print(f"\n 你選擇刪除區域：{prefix} 區，共 {len(delete)} 台機台：")
    for id in delete:
        print("", id)

    print("\n確認要刪除以上所有機台嗎？輸入 yes 執行，其它任意鍵取消：")
    confirm = input().strip().lower()
    if confirm != "yes":
        print("❌ 已取消刪除操作。")
        return

    for id in delete:
        url_del = f"{list_url.rsplit('/list',1)[0]}/{id}"  # v2 broadcasts/id
        rd = httpx.delete(url_del, timeout=10)
        if rd.status_code in (200, 204):
            print("刪除成功")
        else:
            print(f"❌ 刪除失敗：{id} → HTTP {rd.status_code}, {rd.text}")

    print(f"\n🔚 完成，共刪除 {len(delete)} 支「{prefix}」開頭的機台。")


def get_rtsp_urls(media_server_ip: str, media_server_port: int) -> None:
    """獲取所有攝影機的 RTSP URL"""
    data = fetch_all_broadcasts(media_server_ip, media_server_port)

    print(f"找到 {len(data)} 個串流:")
    print("-" * 50)

    for stream in data:
        stream_id = stream.get("streamId", "N/A")
        name = stream.get("name", "N/A")
        rtsp_url = stream.get("streamUrl", "N/A")  # RTSP URL 在 streamUrl 欄位
        status = stream.get("status", "N/A")

        print(f"名稱: {name}")
        print(f"狀態: {status}")
        print(f"ID: {stream_id}")
        print(f"RTSP URL: {rtsp_url}")
        print("-" * 50)


def main() -> None:
    """主函數"""
    print("請輸入Ant Media Server IP (e.g. 61.222.163.86):")
    media_server_ip = input().strip()

    print("請輸入 Port (預設 5080):")
    port_input = input().strip()
    media_server_port = int(port_input) if port_input else 5080

    print("請選擇功能：")
    print("1) 建立攝影機")
    print("2) 匯出串流列表")
    print("3) 刪除攝影機")
    print("4) 獲取 RTSP URL")

    choice = input("輸入 1/2/3/4：").strip()

    if choice == "1":
        print("請輸入username (e.g. admin):")
        username = input().strip()
        print("請輸入password(e.g. password):")
        password = input().strip()
        print("請輸入機台區域 (e.g. A/B/C/D):")
        zone = input().strip().upper()
        print("請輸入網段(e.g. 11/12/13/14):")
        subnet = int(input().strip())
        print("請輸入起始 ID (包含):")
        start_id = int(input().strip())
        print("請輸入結束 ID (包含):")
        end_id = int(input().strip())

        do_create(
            media_server_ip,
            media_server_port,
            username,
            password,
            zone,
            subnet,
            start_id,
            end_id,
        )
    elif choice == "2":
        do_export(media_server_ip, media_server_port)
    elif choice == "3":
        do_delete(media_server_ip, media_server_port)
    elif choice == "4":
        get_rtsp_urls(media_server_ip, media_server_port)
    else:
        print("無效選項，請重新執行程式。")


if __name__ == "__main__":
    main()
