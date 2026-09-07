import os
import requests
import anthropic
from weasyprint import HTML

def generate_pdf():
    # 下午 1 點取得 Claude API 專屬 Key 後啟用
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    # 叫 Claude 生成排版 HTML 的 Prompt
    prompt = "請整理今日台股重點新聞，並輸出為帶有 CSS 樣式的完整 HTML 碼..."
    
    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    html_content = response.content[0].text
    HTML(string=html_content).write_pdf("daily_report.pdf")
    print("PDF 生成成功！")

if __name__ == "__main__":
    print("GitHub Actions 開始執行任務...")
    # generate_pdf() # 等下午 1 點貼上 API Key 後把前方的 # 拿掉
