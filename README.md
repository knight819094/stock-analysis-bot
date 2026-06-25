# StockBot — 台股收盤自動分析推播

每天收盤後自動分析台股並推播到 Telegram。
- 技術面：均線 MA5/10/20/60/200、KD、近20日壓力支撐
- 籌碼面：今量 vs 20日均量、放量/量縮
- 基本面：本益比/殖利率/淨值比 ＋ **預估合理股價**（本益比河流法：當前 EPS × 近數月本益比區間）
- 進出場：研判方向、進場區、目標、停損
- 🤖 **AI 盤後綜合研判**：報告末尾由 Gemini 整合大盤＋個股做一段盤後總結（明日方向、焦點、風險）

> 指數類（加權、金融）不含基本面與合理價；ETF（如 0050）無本益比，合理價不適用。
> AI 解讀詳見下方「AI 解讀」段；可用 config 的 `ai_commentary` 總開關關閉。

## 🚀 安裝與設定

1. 複製設定範本並填入你自己的金鑰：
   ```bash
   cp config.example.json config.json
   ```
2. 編輯 `config.json`，填入：
   - `telegram_bot_token`：跟 [@BotFather](https://t.me/BotFather) 申請。
   - `telegram_chat_id`：對 bot 傳訊息後，用 `getUpdates` 取得。
   - `finnhub_api_key`：[finnhub.io](https://finnhub.io/register) 免費註冊。
   - `gemini_api_key`：[Google AI Studio](https://aistudio.google.com/apikey) 免費取得。
3. 需使用含 `certifi` 的 Python（macOS 上 python.org 版需此）：
   `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`
4. 純標準庫，無需 `pip install`（`certifi` 通常已隨 Python 附帶）。

> ⚠️ `config.json` 含金鑰，已被 `.gitignore` 排除，**請勿** commit。

## 架構（分層模組）

依賴方向：`core` ← `sources` / `ai` / `notify` ← `analysis` ← `daily_push` / `bot`（無循環）。

| 檔案 | 層 | 說明 |
|------|----|------|
| `core.py` | 核心 | 設定載入、SSL/HTTP（含退避重試）、數值/日期、技術指標(MA/KD) |
| `sources.py` | 資料源 | 抓資料：TWSE（盤後/即時）、Finnhub、Yahoo |
| `analysis.py` | 分析 | 組裝報告：台股/美股/指數 + 盤中盤後價格 |
| `ai.py` | AI | Gemini 解讀（單檔 / 盤後綜合） |
| `archive.py` | 歸檔 | 將分析與 AI 報告存入 `archive/*.jsonl`，供未來回測與優化使用 |
| `notify.py` | 通知 | Telegram 發送 |
| `daily_push.py` | 進入點① | 每日收盤推播（launchd 14:00） |
| `bot.py` | 進入點② | 互動查詢 bot（常駐長輪詢） |
| `config.json` | 設定 | token/key、追蹤標的、均線/KD/AI 參數 |
| `run.log` / `bot.log` | 記錄 | launchd 執行 log |

> 重構前是扁平的 `tw_report.py`／`us_report.py`／`ai_analyst.py`／`tw_bot.py`，已拆成上述分層模組。

## 互動查詢 bot（bot.py）

在 Telegram 直接傳訊息給 `@sean_notify_bot`：

| 你傳 | 回傳 |
|------|------|
| `2330` 或 `台積電` 或 `台積` | 台股完整分析（技術/籌碼/基本面/合理價/進出場） |
| `AAPL`／`NVDA`／`TSLA` | 美股分析（技術 MA/KD/壓撐 + 基本面 + 分析師評等 + 進出場） |
| `加權` | 加權指數分析 |
| `金融` | 金融指數分析 |
| `說明` / `/help` | 使用說明 |

- 盤中查詢（台股平日 09:00–13:30）顯示「現價＋查詢時間（盤中）」**；盤後顯示「收盤」。
  - 即時價來自 TWSE MIS API（個股 `tse_<代號>.tw`、加權 `tse_t00.tw`、金融 `tse_t17.tw`）。
  - 技術指標 MA/KD 仍以日線（昨日為止的完整交易日）計算，盤中價只影響「現價」那一行。
- 台股名稱支援模糊比對（多檔符合時會列出代號讓你選）。
- 純英文字母 1-5 碼自動視為美股代號（可含 `.B`，如 `BRK.B`）。
- 僅回應 `config.json` 內的本人 `chat_id`（他人傳訊不理會）。
- 台股對照來自 TWSE 全上市清單（1366 檔），每 12 小時更新。
- **⚡ 多執行緒非同步處理**：查詢指令由獨立執行緒（Thread）背景處理，可同時平行查詢多檔股票，即使 AI 生成時間較長也不會造成機器人卡死或延遲。

### 美股資料來源（analysis.analyze_us_stock / sources.py）

| 面向 | 來源 |
|------|------|
| 報價、基本面(PE/PB/EPS/殖利率/52週/市值)、分析師評等 | Finnhub（需 `finnhub_api_key`） |
| 技術面 MA/KD/壓力支撐/量能 | Yahoo Finance chart API（免金鑰） |

> Finnhub 免費版無歷史 K 線權限，故技術指標改由 Yahoo chart API 計算。
> 美股盤別由 Finnhub `market-status` 判斷（含夏令時間/假日）：盤中顯示「現價＋ET 時間（盤中/盤前/盤後延長）」，收盤後顯示「收盤」。

### AI 解讀（ai.py，Gemini）

每次查詢報告後會附上「🤖 AI 綜合解讀」，由 Gemini 根據**程式算好的數據**做自然語言研判
（趨勢、技術/籌碼/基本面綜合、操作策略與風險）。

- 原則：**數據由程式計算（保證正確），AI 只解讀、不得捏造數字**。
- **邏輯防呆機制**：
  - **均線糾結防呆**：當短中期均線距離過近（<2.5%），程式會強制標記為「均線嚴重糾結」，防止 AI 產生「多頭排列」的幻覺。
  - **空頭防撞車**：若整體趨勢為偏空，進場區間會自動退守至下檔強力支撐區（左側低接），防止建議高檔接刀的矛盾策略。
- 模型：**`gemini-3-flash-preview`**（免費方案中推理最強，會開啟 thinking 深度分析）。
  - 註：`gemini-2.5-pro` / `gemini-3-pro-preview` 免費方案 quota=0 不可用，需付費。
- config 設定：
  - `gemini_api_key`：Google AI Studio 金鑰（https://aistudio.google.com/apikey）
  - `gemini_model`：預設 `gemini-3-flash-preview`；穩定可改 `gemini-2.5-flash`
  - `gemini_thinking_budget`：思考量，預設 `-1`（動態）；設 `0` 可關閉思考換取速度
  - `ai_commentary`：`true`/`false` 總開關（設 false 即停用 AI、只回規則式報告）
- AI 失敗或關閉時，報告照常回傳（不影響數據部分）。

### 歷史數據歸檔 (archive.py)

每次由 Bot 或每日推播產生的分析報告，都會在背景自動以 JSON Lines (`.jsonl`) 格式寫入 `archive/` 資料夾（按月份切分，如 `archive_2026_06.jsonl`）。
- **用途**：自動建立歷史分析資料庫，未來可用 Python (`pandas`) 讀取，結合真實股價走勢進行策略勝率回測。
- **Git**：`archive/` 預設已加入 `.gitignore`，歸檔資料不會被上傳，以保護硬碟容量與隱私。

### bot 常駐管理（launchd，KeepAlive 自動重啟）

```bash
PLIST=~/Library/LaunchAgents/com.sean.twstockbot.plist
launchctl load -w   "$PLIST"   # 啟動
launchctl unload    "$PLIST"   # 停止
launchctl list | grep twstockbot   # 狀態
tail -f "/Users/moony./Documents/Sean Program/StockBot/bot.log"  # 看即時 log
```

> bot 用長輪詢（getUpdates），同一時間只能有一個程序在收訊；若用 Telegram MCP 的 get-updates 工具會短暫衝突，平常不影響。

## 手動執行

```bash
cd "/Users/moony./Documents/Sean Program/StockBot"
python3 daily_push.py        # 實際推播
python3 daily_push.py --dry  # 只印出、不推播
python3 bot.py               # 手動跑互動 bot（平常由 launchd 常駐）
```

> 必須用含 certifi 的 Python：
> `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`

## 排程（macOS launchd）

- 設定檔：`~/Library/LaunchAgents/com.sean.twstockreport.plist`
- 時間：**週一～五 14:00**（收盤後 30 分）
- 非交易日（假日/補假）腳本會自動偵測並略過推播

### 改時間 / 標的

1. 改標的：編輯 `config.json` 的 `stocks` 與 `indices`
2. 改時間：編輯 plist 的 `StartCalendarInterval`，然後：
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.sean.twstockreport.plist
   launchctl load -w ~/Library/LaunchAgents/com.sean.twstockreport.plist
   ```

### 暫停 / 恢復 / 移除

```bash
# 暫停
launchctl unload ~/Library/LaunchAgents/com.sean.twstockreport.plist
# 恢復
launchctl load -w ~/Library/LaunchAgents/com.sean.twstockreport.plist
# 立即手動觸發一次（測試）
launchctl kickstart -k gui/$(id -u)/com.sean.twstockreport
# 確認是否註冊
launchctl list | grep twstockreport
# 完全移除
launchctl unload ~/Library/LaunchAgents/com.sean.twstockreport.plist
rm ~/Library/LaunchAgents/com.sean.twstockreport.plist
```

## 目前追蹤標的

- 2330 台積電（完整分析）
- 0050 元大台灣50（完整分析，ETF 無本益比）
- 加權指數（均線/KD/壓撐）
- 金融保險類指數（均線/趨勢；指數無逐日高低故無 KD）

## 注意

- 操作建議為**規則式計算**（KD 交叉、均線、近 20 日壓撐），僅供參考，非投資建議。
- Mac 需在排程時間處於開機/喚醒狀態才會執行（睡眠中錯過的不會補跑）。
- Telegram token 與 chat id 存在 `config.json`，請勿外流。
