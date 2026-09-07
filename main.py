import os
import requests
import anthropic
from weasyprint import HTML

# 1. 呼叫 LINE Messaging API 廣播 PDF 檔
def send_line_broadcast(pdf_url):
    line_token = os.environ.get("Y3z+Uhm2bvWVjQh+ykAR4hUUnMMbh156BmFNjj3ZgGwNtNWeEXwMYUfOCKjaky2unS4Yxfgq7gvXltbhQ6dDv058wlfnAfvKjJZiEQCTz43Cmo8PDOc6XY/lAN5dGoKwdWsk8hAjrZa0AstHAVZHxgdB04t89/1O/w1cDnyilFU=")
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
                "originalContentUrl": pdf_url,  # 必須是公開的 HTTPS 網址
                "fileName": "台股每日新聞報報.pdf"
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE Broadcast 群發成功！")
    else:
        print(f"LINE 發送失敗，狀態碼：{response.status_code}，回應：{response.text}")

# 2. 呼叫 Claude API 整理新聞並生成 PDF
#def generate_pdf():
 #   client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
  #  prompt = "請整理今日台股重點新聞，並輸出為帶有簡潔美觀 CSS 樣式的完整 HTML 碼..."
    
   # response = client.messages.create(
    #    model="claude-3-7-sonnet-20250219",
     #   max_tokens=3000,
      #  messages=[{"role": "user", "content": prompt}]
    #)
    
    html_content = response.content[0].text
    HTML(string=html_content).write_pdf("daily_report.pdf")
    print("PDF 生成成功！")

# 3. 主執行流程
if __name__ == "__main__":
    print("GitHub Actions 開始執行任務...")
    
    # 下午 1 點補上 ANTHROPIC_API_KEY 後，把下方兩行的 # 拿掉即可啟用：
    # generate_pdf()
    # pdf_url = upload_to_cloud("daily_report.pdf") # 將 PDF 上傳至雲端取得 HTTPS 網址
    # send_line_broadcast(pdf_url)
