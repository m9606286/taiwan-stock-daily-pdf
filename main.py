def send_line_broadcast(pdf_url):
    # 測試階段：直接貼上記得複製完整的長 Token（記得開頭結尾要有雙引號）
    line_token = "Y3z+Uhm2bvWVjQh+ykAR4hUUnMMbh156BmFNjj3ZgGwNtNWeEXwMYUfOCKjaky2unS4Yxfgq7gvXltbhQ6dDv058wlfnAfvKjJZiEQCTz43Cmo8PDOc6XY/lAN5dGoKwdWsk8hAjrZa0AstHAVZHxgdB04t89/1O/w1cDnyilFU="
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": "【台股報報】main.py 本機直接測試發送！"
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    print(f"狀態碼：{response.status_code}")
    print(f"回應內容：{response.text}")

if __name__ == "__main__":
    print("正在執行 main.py 測試...")
    send_line_broadcast("https://www.w3.org/W3C/DesignIssues/diagrams/pdf.pdf")
