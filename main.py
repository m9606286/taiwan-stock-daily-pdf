import os
import requests
import anthropic
from weasyprint import HTML

def generate_report_content():
    """呼叫 Claude API 生成台股晨報文字」"""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    prompt = "請幫我撰寫一份今日台股重點晨報，包含大盤趨勢分析、熱門族群觀察與重點個股動態，請以條列式、結構清晰的方式呈現。"
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def create_pdf(text_content):
    """將文字轉為 HTML 並使用 WeasyPrint 產出 PDF 檔案"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: sans-serif; padding: 20px; line-height: 1.6; }}
            h1 {{ color: #1a365d; border-bottom: 2px solid #3182ce; padding-bottom: 8px; }}
            pre {{ white-space: pre-wrap; font-family: inherit; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h1>每日台股晨報</h1>
        <pre>{text_content}</pre>
    </body>
    </html>
    """
    pdf_path = "taiwan_stock_daily.pdf"
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path

def send_line_broadcast(text_content):
    """將報告內容經由 LINE Broadcast 發送」"""
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
                "text": f"【台股每日晨報】\n\n{text_content[:950]}...\n\n（完整 PDF 已同步生成）"
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 推播發送成功！")
    else:
        print(f"LINE 發送失敗，狀態碼：{response.status_code}，回應：{response.text}")

if __name__ == "__main__":
    print("開始執行每日台股晨報自動化流程...")
    
    # 1. 生成內容
    report = generate_report_content()
    
    # 2. 轉出 PDF
    pdf_file = create_pdf(report)
    print(f"PDF 已成功產出：{pdf_file}")
    
    # 3. 發送 LINE 推播
    send_line_broadcast(report)
