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
    """1. 自動抓取「經濟日報」過去 7 小時內的即時台股焦點新聞"""
    rss_url = "https://news.google.com/rss/search?q=site:money.udn.com+台股+when:7h&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    news_titles = []
    for entry in feed.entries[:10]:
        news_titles.append(entry.title)
    
    if len(news_titles) < 3:
        backup_url = "https://news.google.com/rss/search?q=site:money.udn.com+台股+when:12h&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        feed = feedparser.parse(backup_url)
        news_titles = [entry.title for entry in feed.entries[:10]]

    return news_titles

def generate_report_content(news_titles):
    """2. 將經濟日報新聞餵給 Gemini 進行深度精闢分析"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    today_str = datetime.date.today().strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
今天是 {today_str}。
以下是從《經濟日報》抓取的近 7 小時內最新台股即時新聞標題：
{news_text}

請扮演一位資深的台股首席策略分析師與產業研究員，將上述新聞進行 cross-reference（交叉比對與綜合歸納），進行非常精闢且有洞察力的深度分析。

請務必包含以下四大區塊：
一、【大盤總經與籌碼動向精闢解讀】
二、【熱門產業族群與關鍵個股深度剖析】
三、【市場潛在風險與觀望指標】
四、【今日操作策略與關鍵應對思維】

【注意事項】：
1. 嚴格禁止使用任何破折號、橫線（如 ---）、* 號、# 號或任何 markdown 格式化標記。
2. 內文段落標題請直接寫成 一、【大盤總經...】 形式即可。
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
    """助手函數：徹底濾除 ---, ***, *, # 等所有雜亂符號"""
    text = re.sub(r'^[-\*_]{2,}\s*$', '', text, flags=re.MULTILINE) # 清除 ---, *** 等橫線
    text = re.sub(r'#{1,6}\s*', '', text)                        # 清除 # 標題符號
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)                # 清除粗體 **
    text = re.sub(r'\*(.*?)\*', r'\1', text)                    # 清除斜體 *
    text = re.sub(r'^\s*[\*\-\•]\s+', '', text, flags=re.MULTILINE) # 清除條列符號
    return text.strip()

def format_analysis_html(raw_text):
    """將分析內文標題自動加上高級立體 3D 方框"""
    cleaned = clean_markdown_text(raw_text)
    lines = cleaned.split("\n")
    formatted_lines = []
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        # 匹配 一、【...】、二、【...】 或類似的大段落標題
        if re.match(r'^[一二三四五六七八九十]、\s*【.*】', line_str) or re.match(r'^【.*】', line_str):
            formatted_lines.append(f'''
            <div class="3d-header-card">
                <div class="3d-badge">✦</div>
                <div class="3d-header-title">{line_str}</div>
            </div>
            ''')
        else:
            formatted_lines.append(f'<p class="content-p">{line_str}</p>')
            
    return "".join(formatted_lines)

def create_pdf(news_titles, ai_analysis):
    """3. 生成美觀立體、大字體的 PDF 晨報"""
    today_str = datetime.date.today().strftime("%Y/%m/%d")
    
    cleaned_news = [clean_markdown_text(title) for title in news_titles]
    
    # 焦點新聞改為高級立體藍色卡片，附帶立體標示圖案
    news_li_html = "".join([f'''
    <div class="news-card">
        <div class="news-icon">🔷</div>
        <div class="news-text">{title}</div>
    </div>
    ''' for title in cleaned_news])
    
    formatted_analysis_html = format_analysis_html(ai_analysis)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 8mm;
                background-color: #f1f5f9;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                font-family: "Noto Sans CJK TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
                margin: 0;
                padding: 0;
                color: #0f172a;
                /* 大幅放大字體以優化手機閱讀 */
                font-size: 14pt;
                line-height: 1.85;
            }}
            
            /* 頂部雙層 3D 大 Banner */
            .header {{
                background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #2563eb 100%);
                color: #ffffff;
                padding: 26px 28px;
                border-radius: 16px;
                margin-bottom: 22px;
                box-shadow: 0 10px 25px rgba(30, 58, 138, 0.35);
                border-bottom: 4px solid #1d4ed8;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24pt;
                font-weight: 900;
                letter-spacing: 1.5px;
                text-shadow: 0 3px 6px rgba(0,0,0,0.4);
            }}
            .header .subtitle-badge {{
                display: inline-block;
                background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 11.5pt;
                font-weight: bold;
                color: #ffffff;
                margin-top: 12px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }}

            /* 白底立體卡片容器 */
            .section {{
                background: #ffffff;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 22px;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
                border: 1px solid #e2e8f0;
            }}
            
            /* 區塊主標題 */
            .section-main-title {{
                font-size: 18pt;
                font-weight: 900;
                color: #1e3a8a;
                margin-top: 0;
                margin-bottom: 18px;
                padding-left: 14px;
                border-left: 7px solid #2563eb;
            }}
            
            /* 新聞列表 3D 卡片 */
            .news-card {{
                display: flex;
                align-items: center;
                background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
                color: #ffffff;
                padding: 14px 18px;
                margin-bottom: 12px;
                border-radius: 10px;
                box-shadow: 0 5px 12px rgba(37, 99, 235, 0.28);
                border-bottom: 3px solid #1d4ed8;
            }}
            .news-icon {{
                font-size: 14pt;
                margin-right: 12px;
            }}
            .news-text {{
                font-size: 13.5pt;
                font-weight: 700;
                line-height: 1.5;
            }}
            
            /* 內文 3D 藍色立體標題方框（白字） */
            .3d-header-card {{
                background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
                color: #ffffff;
                padding: 14px 20px;
                margin-top: 26px;
                margin-bottom: 16px;
                border-radius: 10px;
                box-shadow: 0 6px 14px rgba(30, 58, 138, 0.35);
                border-left: 6px solid #60a5fa;
                border-bottom: 3px solid #1d4ed8;
            }}
            .3d-badge {{
                display: inline-block;
                color: #93c5fd;
                margin-right: 8px;
                font-size: 12pt;
            }}
            .3d-header-title {{
                display: inline;
                font-size: 15.5pt;
                font-weight: 900;
                letter-spacing: 0.5px;
            }}

            /* 段落內文大字體 */
            .content-p {{
                margin: 0 0 14px 0;
                color: #334155;
                font-size: 14pt;
                line-height: 1.85;
            }}

            /* 頁尾 */
            .footer {{
                margin-top: 30px;
                font-size: 11pt;
                color: #64748b;
                text-align: center;
                padding-top: 16px;
                border-top: 2px dashed #cbd5e1;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>每日台股焦點與趨勢晨報</h1>
            <div class="subtitle-badge">📊 經濟日報即時源｜日期：{today_str}</div>
        </div>

        <div class="section">
            <div class="section-main-title">經濟日報即時新聞頭條</div>
            {news_li_html}
        </div>

        <div class="section">
            <div class="section-main-title">Gemini 首席策略深度分析</div>
            {formatted_analysis_html}
        </div>

        <div class="footer">
            本報告由 GitHub Actions 自動抓取經濟日報即時新聞並經 Gemini AI 彙整生成｜僅供參考，不構成投資建議
        </div>
    </body>
    </html>
    """
    pdf_path = "taiwan_stock_daily.pdf"
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path

def send_line_broadcast(text_content):
    """4. 透過 LINE 發送精簡訊息與 PDF 連結"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    today_short = datetime.datetime.now().strftime("%m/%d").lstrip('0').replace('/0', '/')
    pdf_url = "https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/taiwan_stock_daily.pdf"
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": f"📈 {today_short} 台股報報\n\n📄 點擊連結查看今日 AI 精闢分析 PDF 報告：\n{pdf_url}"
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
    print(f"已抓取經濟日報即時新聞（共 {len(news_list)} 則）。")
    
    analysis = generate_report_content(news_list)
    print("Gemini 精闢分析完畢。")
    
    pdf_file = create_pdf(news_list, analysis)
    print(f"PDF 晨報產出成功：{pdf_file}")
    
    send_line_broadcast(analysis)
