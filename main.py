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
    """抓取過去 12 小時內最新財經頭條（強制台灣時區）"""
    rss_url = "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+美股+OR+夜盤+OR+ADR+OR+半導體+OR+AI)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    # 強制設定為台灣時間 (UTC+8)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now_tw = datetime.datetime.now(tz_tw)
    
    clean_titles = []
    
    for entry in feed.entries:
        if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
            continue
            
        # 轉換新聞發布時間至台灣時間
        pub_utc_epoch = time.mktime(entry.published_parsed)
        pub_tw_dt = datetime.datetime.fromtimestamp(pub_utc_epoch, tz=datetime.timezone.utc).astimezone(tz_tw)
        
        # 計算發布時間差距
        time_diff_seconds = (now_tw - pub_tw_dt).total_seconds()
        
        # 抓取過去 12 小時內發布的最新新聞
        if 0 <= time_diff_seconds <= 12 * 3600:
            title = entry.title.split(" - ")[0].strip()
            if title not in clean_titles:
                clean_titles.append(title)
            
        if len(clean_titles) >= 10:
            break

    # 若清晨新聞量不足（如週一或假日），保底抓取最新 8 則
    if len(clean_titles) < 3:
        for entry in feed.entries:
            title = entry.title.split(" - ")[0].strip()
            if title not in clean_titles:
                clean_titles.append(title)
            if len(clean_titles) >= 8:
                break

    return clean_titles

def generate_report_content(news_titles):
    """Gemini 深度剖析 Prompt"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
今天是 {today_str}。
以下是今日清晨最新發布的財經頭條新聞：
{news_text}

請扮演資深台股首席策略分析師，生成一份【極其詳細、內容豐富且條理分明】的盤前深度分析報告。

請嚴格包含以下五大核心區塊：
一、【美股夜盤與國際市場脈動解讀】
詳細分析昨晚美股四大指數、台指期夜盤表現、台積電 ADR 走勢與科技股帶動效應。

二、【台股今日盤勢預判與關鍵點位】
預估今日台股開盤走勢、振幅區間、關鍵支撐位與壓力位分析。

三、【焦點產業族群與重點關注個股】
詳細剖析今日值得關注的核心產業（如 AI 伺服器、先進封裝 CoWoS、重電綠能等），並列出代表性個股與利多背景。

四、【總經數據、匯率與外資資產動向】
分析美債殖利率、美元指數、新台幣匯率走勢及外資動向。

五、【實戰操作策略與風險控管指南】
給予投資人明確具體的開盤應對思維與止損止盈風控機制。

【注意事項】：
1. 嚴格禁止使用任何 Markdown 橫線（---）、* 號、# 號。
2. 段落標題請直接寫成 一、【...】 形式。
3. 語氣專業精練，全部使用繁體中文。
"""
    
    config = {"automatic_function_calling": {"disable": True}}

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
            print(f"API 請求失敗 ({e})，5 秒後重試...")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise e

def clean_markdown_text(text):
    text = re.sub(r'^[-\*_]{2,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^\s*[\*\-\•]\s+', '', text, flags=re.MULTILINE)
    return text.strip()

def format_analysis_html(raw_text):
    cleaned = clean_markdown_text(raw_text)
    lines = cleaned.split("\n")
    formatted_lines = []
    
    icons = ["🇺🇸", "📈", "⚡", "💵", "🛡️"]
    icon_idx = 0

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if re.match(r'^[一二三四五六七八九十]、\s*【.*】', line_str) or re.match(r'^【.*】', line_str):
            current_icon = icons[icon_idx % len(icons)]
            icon_idx += 1
            formatted_lines.append(f'<div class="block-title">{current_icon} {line_str}</div>')
        elif "操作思維" in line_str or "風險控管" in line_str or "操作策略" in line_str:
            formatted_lines.append(f'<div class="callout-box">💡 {line_str}</div>')
        else:
            formatted_lines.append(f'<p class="block-text">{line_str}</p>')
            
    return "".join(formatted_lines)

def create_pdf(news_titles, ai_analysis):
    """生成高級感手機專用 PDF"""
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")
    cleaned_news = [clean_markdown_text(title) for title in news_titles]
    
    news_li_html = "".join([f'<div class="news-item"><span class="dot"></span>{title}</div>' for title in cleaned_news])
    formatted_analysis_html = format_analysis_html(ai_analysis)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: 108mm 192mm;
                margin: 6mm;
                background-color: #0b1329;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                font-family: "Noto Sans CJK TC", "Noto Sans TC", "PingFang TC", sans-serif;
                margin: 0;
                padding: 0;
                color: #e2e8f0;
                font-size: 10pt;
                line-height: 1.65;
                background-color: #0b1329;
            }}

            .hero-card {{
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border-radius: 12px;
                padding: 14px 16px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                margin-bottom: 10px;
            }}
            .hero-title {{
                font-size: 15pt;
                font-weight: 800;
                margin: 0 0 6px 0;
                color: #ffffff;
                letter-spacing: 0.5px;
            }}
            .tag-group {{ margin-top: 4px; }}
            .badge {{
                display: inline-block;
                background: rgba(16, 185, 129, 0.15);
                color: #34d399;
                font-weight: 700;
                font-size: 8pt;
                padding: 2px 8px;
                border-radius: 6px;
                border: 1px solid rgba(52, 211, 153, 0.3);
                margin-right: 4px;
            }}
            .badge-date {{
                display: inline-block;
                background: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                font-weight: 700;
                font-size: 8pt;
                padding: 2px 8px;
                border-radius: 6px;
                border: 1px solid rgba(56, 189, 248, 0.3);
            }}

            .metrics-grid {{
                display: table;
                width: 100%;
                table-layout: fixed;
                border-spacing: 6px;
                margin-left: -6px;
                margin-right: -6px;
                margin-bottom: 8px;
            }}
            .metric-row {{ display: table-row; }}
            .metric-col {{ display: table-cell; width: 50%; }}
            
            .metric-card {{
                background: rgba(30, 41, 59, 0.5);
                border-radius: 10px;
                padding: 8px;
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.05);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            }}
            .card-up {{ border-top: 2.5px solid #fb7185; }}
            .card-flat {{ border-top: 2.5px solid #38bdf8; }}

            .metric-label {{ font-size: 7.5pt; color: #94a3b8; font-weight: 600; }}
            .metric-value {{ font-size: 10pt; font-weight: 800; margin-top: 2px; color: #f8fafc; }}

            .section-panel {{
                background: rgba(15, 23, 42, 0.6);
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 10px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            
            .section-title {{
                color: #ffffff;
                font-size: 10.5pt;
                font-weight: 800;
                padding-bottom: 6px;
                margin-bottom: 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .news-item {{
                background: rgba(30, 41, 59, 0.4);
                padding: 7px 10px;
                border-radius: 6px;
                margin-bottom: 6px;
                color: #cbd5e1;
                font-size: 9pt;
                font-weight: 500;
            }}
            .dot {{
                display: inline-block;
                width: 5px;
                height: 5px;
                background-color: #38bdf8;
                border-radius: 50%;
                margin-right: 6px;
                vertical-align: middle;
            }}

            .block-title {{
                font-size: 10pt;
                font-weight: 800;
                color: #38bdf8;
                margin-top: 10px;
                margin-bottom: 4px;
            }}
            .block-text {{
                color: #94a3b8;
                font-size: 9pt;
                line-height: 1.6;
                margin: 0 0 6px 0;
            }}

            .callout-box {{
                background: rgba(234, 179, 8, 0.1);
                border: 1px solid rgba(234, 179, 8, 0.3);
                border-radius: 8px;
                padding: 8px 10px;
                color: #fef08a;
                font-size: 8.5pt;
                font-weight: 600;
                margin-top: 8px;
            }}

            .footer {{
                text-align: center;
                font-size: 7.5pt;
                color: #475569;
                margin-top: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="hero-card">
            <div class="hero-title">盤前極速總研</div>
            <div class="tag-group">
                <span class="badge">AI 智算</span>
                <span class="badge-date">{today_str}</span>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-row">
                <div class="metric-col">
                    <div class="metric-card card-up">
                        <div class="metric-label">美股四大指數</div>
                        <div class="metric-value">多頭回升</div>
                    </div>
                </div>
                <div class="metric-col">
                    <div class="metric-card card-flat">
                        <div class="metric-label">台指期夜盤</div>
                        <div class="metric-value">高檔震盪</div>
                    </div>
                </div>
            </div>
            <div class="metric-row">
                <div class="metric-col">
                    <div class="metric-card card-up">
                        <div class="metric-label">台積電 ADR</div>
                        <div class="metric-value">強勢帶勁</div>
                    </div>
                </div>
                <div class="metric-col">
                    <div class="metric-card card-flat">
                        <div class="metric-label">新台幣匯率</div>
                        <div class="metric-value">資金觀察</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="section-panel">
            <div class="section-title">📡 經濟日報精選頭條</div>
            {news_li_html}
        </div>

        <div class="section-panel">
            <div class="section-title">🧠 Gemini 深度策略解讀</div>
            {formatted_analysis_html}
        </div>

        <div class="footer">
            GitHub Actions 自動化生成｜投資有風險，僅供參考
        </div>
    </body>
    </html>
    """
    pdf_path = "taiwan_stock_daily.pdf"
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path

def send_line_broadcast(text_content):
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    # 強制台灣時區日期
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now_tw = datetime.datetime.now(tz_tw)
    today_short = now_tw.strftime("%m/%d").lstrip('0').replace('/0', '/')
    
    # 加上動態時間戳記防止 CDN 快取舊檔
    timestamp = int(time.time())
    pdf_url = f"https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/taiwan_stock_daily.pdf?v={timestamp}"
    
    payload = {
        "messages": [
            {
                "type": "text",
                "text": f"📈 {today_short} 美股夜盤與台股晨報\n\n📄 點擊連結開啟手機專屬高質感 PDF 報告：\n{pdf_url}"
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
    print(f"已抓取經濟日報最新即時新聞（共 {len(news_list)} 則）。")
    analysis = generate_report_content(news_list)
    print("Gemini 深度剖析完畢。")
    pdf_file = create_pdf(news_list, analysis)
    print(f"PDF 晨報產出成功（精緻手機版）：{pdf_file}")
    send_line_broadcast(analysis)
