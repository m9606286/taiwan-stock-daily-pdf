import os
import requests

def send_line_broadcast(pdf_url):
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    
    # 🔍 偵錯印出：檢查 GitHub 到底有沒有成功讀到 Secrets
    print(f"DEBUG: 讀到的 Token 是否存在: {line_token is not None}")
    if line_token:
        print(f"DEBUG: Token 長度為: {len(line_token)}")
        print(f"DEBUG: Token 開頭為: {line_token[:5]}... 結尾為: ...{line_token[-5:]}")

    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
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
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE Broadcast 測試群發成功！")
    else:
        print(f"LINE 發送失敗，狀態碼：{response.status_code}，回應：{response.text}")

if __name__ == "__main__":
    print("GitHub Actions 開始執行測試任務...")
    test_pdf_url = "https://www.w3.org/W3C/DesignIssues/diagrams/pdf.pdf"
    send_line_broadcast(test_pdf_url)
