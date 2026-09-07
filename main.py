import os
import time
import re
import datetime
import requests
import feedparser
from google import genai
from google.genai import errors
from weasyprint import HTML

def fetch_latest_stock_news():
    """1. 自動抓取 Google News 過去 24 小時內的最新台股焦點新聞"""
    rss_url = "https://news.google.com/rss/search?q=台股+當日焦點+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    news_titles = []
    for entry in feed.entries[:8]:
        news_titles.append(entry.title)
    
    if not news_titles:
        backup_url = "https://news.google.com/rss/search?q=台股+焦點&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        feed = feedparser.parse(backup_url)
        for entry in feed.entries[:8]:
            news_titles.append(entry.title)

    return news_titles

def generate_report_content(news_titles):
    """2. 將新聞餵給 Gemini 生成深度分析內文"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    today_str = datetime.date.today().strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
今天是 {today_str}。
以下是今日剛發布的台股重點即時新聞標題：
{news_text}

請扮演專業的台股分析師，根據上述最新的新聞內容，幫我撰寫一份結構清晰、專業且易讀的「每日台股市場剖析」。
請務必包含以下三大區塊：
一、【大盤焦點與市場趨勢】
二、【熱門族群與重點個股動態】
三、【後續操作觀察與風險提示】

【注意事項】：
1. 輸出時請盡量使用純文字或清晰段落，避免使用過多的 * 或 #### 符號。
2. 必須嚴格基於上述提供的新聞內容進行分析，切勿混入過期的歷史行情。
3. 全部使用繁體中文呈現，用語精煉專業。
"""
    
    config = {
        "automatic_function_calling": {"disable": True}
    }

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            print(f"API 請求失敗 ({e})，5 秒後進行第 {attempt + 1}/{max_retries} 次重試...")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise e

def clean_markdown_text(text):
    """助手函數：清除文字中殘留的 *, **, #### 符號，轉換為乾淨純文字"""
    text = re.sub(r'#{1,6}\s*', '', text)  # 去除 #, ##, ### 等標題符號
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 去除粗體 **
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # 去除斜體/強調 *
    text = re.sub(r'^\s*[\*\-]\s+', '• ', text, flags=re.MULTILINE) # 統一清單符號為圓點
    return text.strip()

def create_pdf(news_titles, ai_analysis):
    """3. 高級立體視覺與配色設計 PDF 生成"""
    today_str = datetime.date.today().strftime("%Y/%m/%d")
    
    # 清理標題與分析內文的雜訊符號
    cleaned_news = [clean_markdown_text(title) for title in news_titles]
    cleaned_analysis = clean_markdown_text(ai_analysis)
    
    news_li_html = "".join([f"<li><span class='bullet-icon'>◆</span><span class='news-text'>{title}</span></li>" for title in cleaned_news])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 12mm;
                background-color: #f1f5f9;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                font-family: "Noto Sans CJK TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
                margin: 0;
                padding: 0;
                color: #1e293b;
                font-size: 10pt;
                line-height: 1.65;
            }}
            
            /* 頂部雙色立體 Banner */
            .header {{
                background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                color: #ffffff;
                padding: 22px 25px;
                border-radius: 12px;
                margin-bottom: 18px;
                box-shadow: 0 8px 16px rgba(30, 58, 138, 0.25);
                position: relative;
            }}
            .header h1 {{
                margin: 0;
                font-size: 20pt;
                font-weight: 700;
                letter-spacing: 1.5px;
                text-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            .header .subtitle-badge {{
                display: inline-block;
                background: rgba(255, 255, 255, 0.2);
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 9pt;
                color: #f8fafc;
                margin-top: 8px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }}

            /* 質感卡片區塊 */
            .section {{
                background: #ffffff;
                border-radius: 10px;
                padding: 18px 22px;
                margin-bottom: 16px;
                box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
                border: 1px solid #e2e8f0;
            }}
            
            /* 具備立體色塊指示條的標題 */
            .section-title {{
                font-size: 12pt;
                font-weight: 700;
                color: #0f172a;
                margin-top: 0;
                margin-bottom: 14px;
                padding-left: 12px;
                border-left: 5px solid #2563eb;
                display: flex;
                align-items: center;
            }}
            
            /* 新聞清單樣式 */
            ul.news-list {{
                list-style: none;
                margin: 0;
                padding: 0;
            }}
            ul.news-list li {{
                padding: 8px 12px;
                margin-bottom: 6px;
                background: #f8fafc;
                border-radius: 6px;
                border-left: 3px solid #cbd5e1;
                font-size: 9.5pt;
            }}
            ul.news-list li .bullet-icon {{
                color: #2563eb;
                font-size: 8pt;
                margin-right: 8px;
            }}
            
            /* AI 分析文樣式 */
            .content {{
                white-space: pre-wrap;
                color: #334155;
                font-size: 10pt;
                background: #fafafa;
                padding: 14px 16px;
                border-radius: 8px;
                border: 1px dashed #cbd5e1;
            }}

            /* 頁尾 */
            .footer {{
                margin-top: 20px;
                font-size: 8.5pt;
                color: #64748b;
                text-align: center;
                padding-top: 10px;
                border-top: 1px solid #e2e8f0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>每日台股焦點與趨勢晨報</h1>
            <div class="subtitle-badge">📊 自動化即時彙整｜日期：{today_str}</div>
        </div>

        <div class="section">
            <div class="section-title">即時焦點新聞摘要</div>
            <ul class="news-list">
                {news_li_html}
            </ul>
        </div>

        <div class="section">
            <div class="section-title">Gemini AI 市場深度剖析</div>
            <div class="content">{cleaned_analysis}</div>
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
    """4. 透過 LINE 發送精華摘要與 JSDelivr CDN PDF 連結"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    today_str = datetime.date.today().strftime("%Y/%m/%d")
    clean_preview = clean_markdown_text(text_content)
    
    pdf_url = "https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/taiwan_stock_daily.pdf"
    preview_text = clean_preview[:800] + "..." if len(clean_preview) > 800 else clean_preview
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": f"【台股每日晨報 - {today_str}】\n\n{preview_text}\n\n📄 點此下載完整排版 PDF：\n{pdf_url}"
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
    print(f"已抓取當日焦點新聞（共 {len(news_list)} 則）。")
    
    analysis = generate_report_content(news_list)
    print("Gemini 分析完畢。")
    
    pdf_file = create_pdf(news_list, analysis)
    print(f"PDF 晨報產出成功：{pdf_file}")
    
    send_line_broadcast(analysis)
