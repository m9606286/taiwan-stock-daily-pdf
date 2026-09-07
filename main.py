```python
import os
import requests


def send_line_broadcast(pdf_url):
    # ==========================================
    # 1. 從 GitHub Actions 環境變數讀取 LINE Token
    # ==========================================
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

    # 安全檢查：不印出 Token 本身
    if not line_token:
        print("❌ ERROR：找不到 LINE_CHANNEL_ACCESS_TOKEN")
        print("請確認 GitHub Settings → Secrets and variables → Actions")
        print("是否有設定 LINE_CHANNEL_ACCESS_TOKEN")
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN 未設定")

    print("✅ LINE Token 已成功從 GitHub Secrets 讀取")
    print(f"DEBUG：Token 長度 = {len(line_token)}")

    # ==========================================
    # 2. LINE Broadcast API
    # ==========================================
    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }

    # ==========================================
    # 3. 測試訊息
    # ==========================================
    payload = {
        "messages": [
            {
                "type": "text",
                "text": "【台股報報】這是一條 GitHub Actions 自動化系統測試訊息！"
            },
            {
                "type": "file",
                "originalContentUrl": pdf_url,
                "fileName": "測試報報.pdf"
            }
        ]
    }

    # ==========================================
    # 4. 發送
    # ==========================================
    print("📡 正在發送 LINE Broadcast...")

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    # ==========================================
    # 5. 判斷結果
    # ==========================================
    if response.status_code == 200:
        print("✅ LINE Broadcast 測試群發成功！")
    else:
        print(f"❌ LINE 發送失敗")
        print(f"HTTP 狀態碼：{response.status_code}")
        print(f"LINE 回應：{response.text}")

        if response.status_code == 401:
            print("")
            print("⚠️ 401 = LINE 不接受目前使用的 Channel Access Token")
            print("請到 LINE Developers 重新確認 / Issue Channel Access Token")


if __name__ == "__main__":
    print("======================================")
    print("GitHub Actions 開始執行測試任務...")
    print("======================================")

    # 測試 PDF
    test_pdf_url = "https://www.w3.org/W3C/DesignIssues/diagrams/pdf.pdf"

    send_line_broadcast(test_pdf_url)
```
