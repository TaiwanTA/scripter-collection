# AMS 串流管理工具

這是一個用於管理 Ant Media Server (AMS) 串流的命令行工具。提供串流的創建、啟動和停止功能。

## 功能特點

- 支持多個服務器配置（sms1-4, \_7ms1-4）
- 批量串流管理
- 互動式命令行界面
- 自動生成唯一串流 ID
- 美觀的命令行輸出

## 安裝需求

```bash
uv run ams.py --help
```

## 使用方法

### 1. 創建串流 (create-streams)

從 CSV 文件批量創建串流。系統會：

- 讀取指定 profile 的 CSV 文件
- 為每個串流生成唯一 ID
- 檢查串流是否已存在
- 創建新的串流

```bash
uv run ams.py create-streams
```

### 2. 啟動所有串流 (start-all-streams)

當 AMS 沒有自動開啟拉流時，可以使用此命令啟動所有串流。

```bash
uv run ams.py start-all-streams
```

### 3. 停止所有串流 (stop-all-streams)

停止指定 profile 下的所有串流。

```bash
uv run ams.py stop-all-streams
```

### 4. 刪除所有串流 (delete-all-streams)

刪除指定 profile 下的所有串流。

```bash
uv run ams.py delete-all-streams
```

## 服務器配置

工具支持以下服務器配置：

### SMS 服務器

- sms1: 220.130.51.197
- sms2: 61.222.163.125
- sms3: 61.222.163.102
- sms4: 61.222.163.104

### 7MS 服務器

- \_7ms1: 220.130.51.248
- \_7ms2: 61.222.163.86
- \_7ms3: 61.222.163.110
- \_7ms4: 61.220.197.203

## CSV 文件格式

每個服務器配置對應一個 CSV 文件，包含以下欄位：

- code: 串流代碼
- stream_ip: 串流 IP 地址
- stream_username: 串流用戶名（可選）
- stream_password: 串流密碼（可選）
- description: 串流描述（可選）
- originAdress: 原始地址（可選）
- metaData: 元數據（可選）

## 注意事項

1. 使用前請確保 CSV 文件格式正確
2. 串流 ID 會自動生成，格式為：`{name}_{hmac_md5}`
3. 執行命令時會要求確認服務器配置
4. 建議在執行批量操作前先備份現有配置
5. 使用 \_7ms 開頭的配置時，請注意輸入完整名稱（包含底線）
