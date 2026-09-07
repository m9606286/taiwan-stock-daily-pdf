import os
import requests

# 呼叫 LINE Messaging API 廣播 PDF 檔
def send_line_broadcast(pdf_url):
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
                "text": "【台股報報】這是一條 GitHub Actions 自動化系統測試訊息！"
            },
            {
                "type": "file",
                "originalContentUrl": pdf_url,  # 測試用的公開 PDF 網址
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
    
    # 使用一個範例測試 PDF 網址直接測試 LINE 廣播功能
    test_pdf_url = "https://www.w3.org/W3C/DesignIssues/diagrams/pdf.pdf"
    
    send_line_broadcast(test_pdf_url)
