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
    """1. 自動抓取「經濟日報」過去 8 小時內的美股、夜盤與台股即時新聞"""
    # 搜尋條件包含美股、夜盤、台股，限定經濟日報 source
    rss_url = "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+美股+OR+夜盤)+when:8h&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    news_titles = []
    for entry in feed.entries[:12]:
        news_titles.append(entry.title)
    
    # 備援機制：若清晨新聞較少，稍微放寬至 12 小時內
    if len(news_titles) < 4:
        backup_url = "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+美股+OR+夜盤)+when:12h&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        feed = feedparser.parse(backup_url)
        news_titles = [entry.title for entry in feed.entries[:12]]

    return news_titles

def generate_report_content(news_titles):
    """2. 將經濟日報新聞餵給 Gemini 進行含美股與台股夜盤的深度分析"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    today_str = datetime.date.today().strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
今天是 {today_str}。
以下是從《經濟日報》抓取的最新即時新聞頭條（包含昨晚美股、台股夜盤與最新總經消息）：
{news_text}

請扮演一位資深的台股首席策略分析師，針對上述新聞進行跨市場綜合解讀與深度精闢剖析。

請務必精闢包含以下四大區塊：
一、【昨晚美股三大指數與台股夜盤動向解讀】
重點分析昨晚美股三大指數（道瓊、那斯達克、標普500）以及台指期夜盤的表現、科技股/台積電ADR走勢與資金避險情緒。

二、【台股今日開盤盤勢預判與熱門族群】
根據昨晚外盤表現，評估今日台股開盤氣氛、關鍵支撐壓力區間，以及焦點族群（如半導體、AI概念股、重電傳產等）。

三、【關鍵總經數據與潛在觀望風險】
提煉當前國際匯率、油價、美債殖利率或即將公布的總經數據風險點。

四、【今日資產配置與具體操作思維】
給予投資人明確、具體的開盤進出場與風控應對建議。

【注意事項】：
1. 嚴格禁止使用任何橫線（如 ---）、* 號、# 號或任何 Markdown 符號。
2. 內文段落標題請直接寫成 一、【昨晚美股...】 形式。
3. 語氣精練專業，注重跨市場邏輯推演，全部使用繁體中文呈現。
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
    text = re.sub(r'^[-\*_]{2,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^\s*[\*\-\•]\s+', '', text, flags=re.MULTILINE)
    return text.strip()

def format_analysis_html(raw_text):
    """將分析內文標題自動轉換為帶有 3D 立體徽章與高質感漸層方框的 HTML"""
    cleaned = clean_markdown_text(raw_text)
    lines = cleaned.split("\n")
    formatted_lines = []
    
    # 不同的區塊自動配對專屬的立體圖案
    icons = ["🇺🇸 🌙", "📈 💎", "⚠️ 📊", "🎯 💡"]
    icon_idx = 0

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if re.match(r'^[一二三四五六七八九十]、\s*【.*】', line_str) or re.match(r'^【.*】', line_str):
            current_icon = icons[icon_idx % len(icons)]
            icon_idx += 1
            formatted_lines.append(f'''
            <div class="header-3d-box">
                <span class="box-icon-3d">{current_icon}</span>
                <span class="box-title-text">{line_str}</span>
            </div>
            ''')
        else:
            formatted_lines.append(f'<p class="content-p">{line_str}</p>')
            
    return "".join(formatted_lines)

def create_pdf(news_titles, ai_analysis):
    """3. 生成包含美股夜盤視覺卡片、多圖案與立體方框的高質感 PDF"""
    today_str = datetime.date.today().strftime("%Y/%m/%d")
    
    cleaned_news = [clean_markdown_text(title) for title in news_titles]
    
    # 新聞條目使用立體 3D 方框搭配藍光箭頭
    news_li_html = "".join([f'''
    <div class="news-3d-card">
        <div class="news-bullet">🔹</div>
        <div class="news-title">{title}</div>
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
                font-size: 14pt;
                line-height: 1.85;
            }}
            
            /* 頂部立體漸層 Header */
            .header {{
                background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #2563eb 100%);
                color: #ffffff;
                padding: 24px 28px;
                border-radius: 16px;
                margin-bottom: 20px;
                box-shadow: 0 10px 22px rgba(30, 58, 138, 0.35);
                border-bottom: 4px solid #1d4ed8;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24pt;
                font-weight: 900;
                letter-spacing: 1px;
                text-shadow: 0 3px 6px rgba(0,0,0,0.3);
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

            /* 快速觀察 - 3D 數據/指標卡片區 */
            .market-quick-cards {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 20px;
                gap: 10px;
            }}
            .metric-card {{
                flex: 1;
                background: linear-gradient(145deg, #ffffff, #f8fafc);
                border-radius: 12px;
                padding: 14px;
                text-align: center;
                box-shadow: 0 6px 14px rgba(15, 23, 42, 0.08);
                border: 1px solid #cbd5e1;
                border-top: 4px solid #2563eb;
            }}
            .metric-card .card-icon {{
                font-size: 18pt;
                margin-bottom: 4px;
            }}
            .metric-card .card-title {{
                font-size: 11pt;
                font-weight: 800;
                color: #475569;
            }}
            .metric-card .card-status {{
                font-size: 12.5pt;
                font-weight: 900;
                color: #1e3a8a;
                margin-top: 4px;
            }}

            /* 白底立體卡片容器 */
            .section {{
                background: #ffffff;
                border-radius: 16px;
                padding: 22px;
                margin-bottom: 20px;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
                border: 1px solid #e2e8f0;
            }}
            
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
            .news-3d-card {{
                display: flex;
                align-items: center;
                background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
                color: #ffffff;
                padding: 12px 18px;
                margin-bottom: 10px;
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
                border-bottom: 3px solid #1d4ed8;
            }}
            .news-bullet {{
                font-size: 12pt;
                margin-right: 10px;
            }}
            .news-title {{
                font-size: 13.5pt;
                font-weight: 700;
                line-height: 1.5;
            }}
            
            /* 內文藍色立體 3D 方框（白字） */
            .header-3d-box {{
                background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
                color: #ffffff;
                padding: 14px 20px;
                margin-top: 24px;
                margin-bottom: 16px;
                border-radius: 10px;
                box-shadow: 0 6px 14px rgba(30, 58, 138, 0.35);
                border-left: 6px solid #60a5fa;
                border-bottom: 3px solid #1d4ed8;
            }}
            .box-icon-3d {{
                font-size: 15pt;
                margin-right: 8px;
            }}
            .box-title-text {{
                font-size: 15.5pt;
                font-weight: 900;
                letter-spacing: 0.5px;
            }}

            /* 大字體段落 */
            .content-p {{
                margin: 0 0 14px 0;
                color: #334155;
                font-size: 14pt;
                line-height: 1.85;
            }}

            .footer {{
                margin-top: 25px;
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
            <h1>每日美股夜盤與台股趨勢晨報</h1>
            <div class="subtitle-badge">📊 經濟日報即時源｜日期：{today_str}</div>
        </div>

        <!-- 3D 視覺數據指標快速卡 -->
        <div class="market-quick-cards">
            <div class="metric-card">
                <div class="card-icon">🇺🇸</div>
                <div class="card-title">美股三大指數</div>
                <div class="card-status">夜盤連動解讀</div>
            </div>
            <div class="metric-card">
                <div class="card-icon">🌙</div>
                <div class="card-title">台指期夜盤</div>
                <div class="card-status">開盤情緒參考</div>
            </div>
            <div class="metric-card">
                <div class="card-icon">⚡</div>
                <div class="card-title">台積電 ADR</div>
                <div class="card-status">權值動能觀察</div>
            </div>
        </div>

        <div class="section">
            <div class="section-main-title">經濟日報即時頭條與外盤焦點</div>
            {news_li_html}
        </div>

        <div class="section">
            <div class="section-main-title">Gemini 跨市場深度剖析</div>
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
                "text": f"📈 {today_short} 美股夜盤與台股晨報\n\n📄 點擊連結查看今日 AI 精闢分析 PDF 報告：\n{pdf_url}"
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
