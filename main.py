import os
import requests
import feedparser
from google import genai
from weasyprint import HTML

def fetch_latest_stock_news():
    """1. 自動上網抓取 Google News 最新台股焦點新聞"""
    rss_url = "https://news.google.com/rss/search?q=台股+當日焦點&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    news_list = []
    for entry in feed.entries[:10]:
        news_list.append(f"- {entry.title}")
    
    return "\n".join(news_list)

def generate_report_content():
    """2. 將新聞帶入 Prompt，改由 Gemini 2.5 Flash 生成晨報」"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    real_time_news = fetch_latest_stock_news()
    
    prompt = f"""
以下是今日剛發布的台股重點即時新聞：
{real_time_news}

請扮演專業的台股分析師，根據上述最新的新聞內容，幫我撰寫一份結構清晰、專業且易讀的「每日台股重點晨報」。
包含以下三大區塊：
1. 【大盤焦點與市場趨勢】
2. 【熱門族群與重點個股動態】
3. 【後續操作觀察與風險提示】

請全部使用繁體中文呈現，用語要精煉專業。
"""
    
    # 呼叫免費的 Gemini 2.5 Flash 模型
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def create_pdf(text_content):
    """3. 產出 PDF 檔案"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4; margin: 20mm; }}
            body {{ font-family: "PingFang TC", "Microsoft JhengHei", sans-serif; padding: 10px; line-height: 1.7; color: #2d3748; }}
            h1 {{ color: #1a365d; border-bottom: 3px solid #3182ce; padding-bottom: 8px; font-size: 24px; text-align: center; }}
            .content {{ white-space: pre-wrap; font-size: 13px; background: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; }}
            .footer {{ margin-top: 30px; font-size: 11px; color: #a0aec0; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>每日台股焦點與趨勢晨報</h1>
        <div class="content">{text_content}</div>
        <div class="footer">本報告由 GitHub Actions 自動抓取即時新聞並經 Gemini AI 彙整生成</div>
    </body>
    </html>
    """
    pdf_path = "taiwan_stock_daily.pdf"
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path

def send_line_broadcast(text_content):
    """4. 透過 LINE 發送推播訊息"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    preview_text = text_content[:900] + "...\n\n（完整分析 PDF 已自動產出並存檔）" if len(text_content) > 900 else text_content
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": f"【台股每日晨報】\n\n{preview_text}"
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 推播發送成功！")
    else:
        print(f"LINE 發送失敗，狀態碼：{response.status_code}，回應：{response.text}")

if __name__ == "__main__":
    print("開始執行每日台股晨報自動化流程 (Gemini 免費版)...")
    
    report = generate_report_content()
    pdf_file = create_pdf(report)
    print(f"PDF 已成功產出：{pdf_file}")
    send_line_broadcast(report)
