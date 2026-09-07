import os
import requests
import anthropic
from weasyprint import HTML

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
                "text": "【台股報報】每日財經新聞報報已出爐，請點擊下方檔案查看完整 PDF！"
            },
            {
                "type": "file",
                "originalContentUrl": pdf_url,
                "fileName": "台股每日新聞報報.pdf"
            }
        ]
    }
    
    requests.post(url, headers=headers, json=payload)

#def generate_pdf():
 #   client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
  #  prompt = "請整理今日台股重點新聞，並輸出為帶有 CSS 樣式的完整 HTML 碼..."
    
   # response = client.messages.create(
    #    model="claude-3-7-sonnet-20250219",
     #   max_tokens=3000,
      #  messages=[{"role": "user", "content": prompt}]
    #)
    
    html_content = response.content[0].text
    HTML(string=html_content).write_pdf("daily_report.pdf")
    return "daily_report.pdf"

if __name__ == "__main__":
    pdf_file = generate_pdf()
    # 自動上傳至雲端取得 https 網址後傳送
    # send_line_broadcast(pdf_url)
