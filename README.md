# Ai_StockBot — 智慧股票分析與即時監控機器人

一個整合了**即時監控、每日自動推播、與互動式查詢**的 Telegram 股票分析機器人。

透過整合 `yfinance`、`Finnhub` 以及最新的 **Google Gemini AI** 模型，Ai_StockBot 不僅能提供台股與美股的技術面與基本面數據，還能生成 K 線圖並產出大師級的盤後/盤中分析報告。

## ✨ 核心功能

1. **🤖 互動式查詢 Bot (`src/bot.py`)**
   - 透過 Telegram 傳送代號（如 `2330`, `TSLA`）或名稱（如 `台積電`），即可取得完整分析與 AI 解讀。
   - 支援台股、美股、加權指數與金融指數。
   - 自動生成包含 MA 均線與成交量的 **K 線圖**。
2. **⏱️ 即時到價監控 (`src/monitor.py`)**
   - 設定監控標的與價格區間（如 TSLA 420-435）。
   - 盤中每分鐘即時抓取數據，計算當日 **VWAP（成交量加權平均價）**。
   - 價格突破或進入關鍵區間時，自動推播至 Telegram（支援 LINE 備用通知）。
3. **📅 每日收盤推播 (`src/daily_push.py`)**
   - 搭配 macOS `launchd` 或 crontab，在台股收盤後自動產生追蹤清單的總結報告並推播。
4. **🔒 安全的環境變數與分離的資料架構**
   - 所有金鑰與敏感資料統一存在 `.env`，避免上傳至公開儲存庫。
   - 核心邏輯、腳本、文件、自動日誌皆有獨立目錄，保持專案整潔。

## 🚀 安裝與設定

1. **複製設定檔範本：**
   ```bash
   cp config.example.json config.json
   ```
2. **編輯 `config.json`：**
   設定你的監控目標、均線參數與 AI 設定。
3. **建立 `.env` 檔案並填入金鑰：**
   在專案根目錄建立 `.env` 檔案，內容如下：
   ```env
   TELEGRAM_BOT_TOKEN=你的_Telegram_Bot_Token
   TELEGRAM_CHAT_ID=你的_Chat_ID
   FINNHUB_API_KEY=你的_Finnhub_API_Key
   GEMINI_API_KEY=你的_Gemini_API_Key
   # 下方為可選（備用通知）
   LINE_CHANNEL_ACCESS_TOKEN=
   LINE_USER_ID=
   ```
4. **安裝必要套件：**
   本專案依賴部分 Python 套件進行圖表生成、數據抓取與環境變數管理：
   ```bash
   pip install yfinance pandas matplotlib mplfinance python-dotenv requests
   ```

## 📂 架構模組

程式核心統一放置於 `src/` 目錄中，與設定、文件獨立分開：

| 檔案 | 說明 |
|------|------|
| `src/core.py` | 核心：載入設定檔與 `.env`，提供基礎工具與技術指標 (MA/KD) 運算 |
| `src/sources.py` | 數據源：串接 TWSE (盤後/即時)、Finnhub 與 Yahoo API |
| `src/analysis.py` | 分析：組裝報告 (技術面、基本面、合理價預估) |
| `src/chart.py` | 繪圖：依據歷史數據產出 K 線圖 (`.png`) |
| `src/ai.py` | AI 引擎：串接 Gemini 產出自然語言解讀報告 |
| `src/notify.py` | 通知：負責傳送文字與圖片至 Telegram（或 LINE） |
| `src/bot.py` | 進入點①：常駐執行的 Telegram 互動式機器人 |
| `src/monitor.py` | 進入點②：常駐執行的即時到價監控與 VWAP 計算 |
| `src/daily_push.py` | 進入點③：每日定時觸發的收盤推播程式 |
| `src/archive.py` | 歸檔：將分析與 AI 報告存入 `archive/` 供未來回測 |

**資料夾說明：**
- `scripts/`：放置如 macOS LaunchAgents 排程更新 (`update_plists.sh`) 的工具腳本。
- `Log/`：專門用來存放你手動紀錄的 Markdown (`.md`) 歷史與知識筆記。
- `system_logs/`：系統背景自動產出的運作記錄（`*.log`），已經從版控中排除。
- `tmp_charts/` 與 `archive/`：執行過程產生的暫存圖檔與歷史數據（不進版控）。

## 🕹️ 執行與使用方式

你可以同時在背景跑 `bot.py` 和 `monitor.py`：

**1. 啟動互動機器人：**
```bash
python3 src/bot.py
```
> 啟動後，你可以在 Telegram 對機器人說 `2330` 或 `TSLA`。

**2. 啟動即時監控：**
```bash
python3 src/monitor.py
# 若只想測試跑一次就退出，請加 --test 參數：
python3 src/monitor.py --test
```

**3. 手動測試每日推播：**
```bash
python3 src/daily_push.py
```

## ⚠️ 注意事項

- 操作建議為**規則式計算**（KD 交叉、均線、近 20 日壓撐），AI 解讀亦屬於實驗性質，**僅供參考，非投資建議**。
- `system_logs/`、`archive/` 與 `tmp_charts/` 皆已被 `.gitignore` 排除。
- `.env` 包含所有敏感金鑰，**絕對不可** commit 至 Git。
