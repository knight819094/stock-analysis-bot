#!/bin/bash

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
OLD_PATH="/Users/moony./Documents/Sean Program/SmartStockBot"
NEW_PATH="/Users/moony./Documents/Sean Program/Ai_StockBot"

echo "開始搜尋並更新 LaunchAgents 中的 plist 檔案..."

for plist in "$LAUNCH_AGENTS_DIR"/com.sean.*.plist; do
    if [ -f "$plist" ]; then
        echo "找到設定檔：$plist"
        launchctl unload "$plist" 2>/dev/null
        sed -i '' "s|$OLD_PATH|$NEW_PATH|g" "$plist"
        echo "已更新路徑：$plist"
        launchctl load -w "$plist" 2>/dev/null
        echo "已重新載入服務：$plist"
        echo "----------------------------------------"
    fi
done

echo "🎉 更新完成！"
