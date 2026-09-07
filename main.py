import os
import time
import requests
import feedparser
from google import genai
from google.genai import errors
from weasyprint import HTML

def fetch_latest_stock_news():
    """1. 自動上網抓取 Google News 最新台股焦點新聞"""
    rss_url = "https://news.google.com/rss/search?q=台股+當日焦點&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    news_titles = []
    for entry in feed.entries[:8]:
        news_titles.append(entry.title)
    
    return news_titles

def generate_report_content(news_titles):
    """2. 將新聞餵給 Gemini 3.6 Flash 生成深度分析內文（含 503 重試機制）"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
以下是今日剛發布的台股重點即時新聞標題：
{news_text}

請扮演專業的台股分析師，根據上述最新的新聞內容，幫我撰寫一份結構清晰、專業且易讀的「每日台股市場剖析」。
請務必包含以下三大區塊：
一、【大盤焦點與市場趨勢】
二、【熱門族群與重點個股動態】
三、【後續操作觀察與風險提示】

請全部使用繁體中文呈現，用語精煉專業，重點明確。
"""
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            return response.text
        except errors.APIError as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Gemini API 繁忙 (503)，等待 5 秒後進行第 {attempt + 1} 次重試...")
                time.sleep(5)
            else:
                raise e
                
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    return response.text

def create_pdf(news_titles, ai_analysis):
    """3. 將「新聞清單」與「AI 分析」組合繪製成高級排版的 PDF 晨報"""
    news_li_html = "".join([f"<li>{title}</li>" for title in news_titles])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 15mm 12mm;
                background-color: #f8fafc;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                font-family: "Noto Sans CJK TC", "PingFang TC", "Microsoft JhengHei", sans-serif;
                margin: 0;
                padding: 0;
                color: #2d3748;
                font-size: 10.5pt;
                line-height: 1.6;
            }}
            .header {{
                background-color: #1a365d;
                color: #ffffff;
                padding: 20px 15mm;
                margin: -15mm -12mm 20px -12mm;
            }}
            .header h1 {{
                margin: 0;
                font-size: 18pt;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            .header .subtitle {{
                font-size: 10pt;
                color: #cbd5e0;
                margin-top: 5px;
            }}
            .section {{
                background: #ffffff;
                border-radius: 8px;
                padding: 18px 20px;
                margin-bottom: 18px;
                border: 1px solid #e2e8f0;
            }}
            .section-title {{
                font-size: 12pt;
                color: #2b6cb0;
                border-left: 4px solid #3182ce;
                padding-left: 10px;
                margin-top: 0;
                margin-bottom: 12px;
            }}
            ul {{
                margin: 0;
                padding-left: 20px;
            }}
            li {{
                margin-bottom: 6px;
            }}
            .content {{
                white-space: pre-wrap;
            }}
            .footer {{
                margin-top: 25px;
                font-size: 9pt;
                color: #a0aec0;
                text-align: center;
                border-top: 1px solid #e2e8f0;
                padding-top: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>每日台股焦點與趨勢晨報</h1>
            <div class="subtitle">自動化生成報告｜Gemini AI 彙整</div>
        </div>

        <div class="section">
            <h2 class="section-title">今日焦點新聞摘要</h2>
            <ul>
                {news_li_html}
            </ul>
        </div>

        <div class="section">
            <h2 class="section-title">AI 分析與市場深度剖析</h2>
            <div class="content">{ai_analysis}</div>
        </div>

        <div class="footer">
            本報告由 GitHub Actions 自動抓取即時新聞並經 Gemini AI 彙整生成｜僅供參考，不構成投資建議
        </div>
    </body>
    </html>
    """
    pdf_path = "taiwan_stock_daily.pdf"
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path

def send_line_broadcast(text_content):
    """4. 透過 LINE 發送精華摘要與 GitHub Raw PDF 下載連結"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    pdf_url = "https://raw.githubusercontent.com/m9606286/taiwan-stock-daily-pdf/main/taiwan_stock_daily.pdf"
    preview_text = text_content[:800] + "..." if len(text_content) > 800 else text_content
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": f"【台股每日晨報】\n\n{preview_text}\n\n📄 點此下載完整排版 PDF：\n{pdf_url}"
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
    
    news_list = fetch_latest_stock_news()
    print("已抓取當日焦點新聞。")
    
    analysis = generate_report_content(news_list)
    print("Gemini 分析完畢。")
    
    pdf_file = create_pdf(news_list, analysis)
    print(f"PDF 晨報產出成功：{pdf_file}")
    
    send_line_broadcast(analysis)
