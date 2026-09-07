import os
import requests

def send_line_broadcast():
    # 從 GitHub Secrets 取得 LINE Token
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": "【台股報報】GitHub Actions 全自動連線測試成功！"
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE Broadcast 測試成功！")
    else:
        print(f"LINE 發送失敗，狀態碼：{response.status_code}，回應：{response.text}")

if __name__ == "__main__":
    print("GitHub Actions 開始執行測試任務...")
    send_line_broadcast()
