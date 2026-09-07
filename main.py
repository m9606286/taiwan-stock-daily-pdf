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
    # 限定來源為 money.udn.com (經濟日報)，時間限定 when:7h
    rss_url = "https://news.google.com/rss/search?q=site:money.udn.com+台股+when:7h&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    news_titles = []
    for entry in feed.entries[:10]:  # 擷取最多 10 則即時新聞
        news_titles.append(entry.title)
    
    # 備援機制：若清晨 7 小時內新聞較少，稍微放寬至 12 小時內的經濟日報
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

請扮演一位資深的台股首席策略分析師與產業研究員，請不要只是條列新聞，而是將上述新聞進行 cross-reference（交叉比對與綜合歸納），進行非常精闢且有洞察力的深度分析。

請務必包含以下四大區塊：
一、【大盤總經與籌碼動向精闢解讀】
分析整體市場氣氛、資金流向與大盤關鍵支撐/壓力位階預判。

二、【熱門產業族群與關鍵個股深度剖析】
針對新聞提及的重點個股或產業（如半導體、AI、傳產、電子零組件等），分析其基本面催化劑與短中線動能。

三、【市場潛在風險與觀望指標】
提煉目前市場未顯現或需警惕的風險點（如國際市場連動、匯率、總經數據發布等）。

四、【今日操作策略與關鍵應對思維】
給予投資人明確、具體的資產配置或進出場操作建議。

【注意事項】：
1. 分析必須精闢、具商業洞察，絕不能只是重述新聞標題。
2. 完全不要使用 --- 分隔線、*、** 或 #### 符號。
3. 嚴格基於上述提供的新聞內容進行分析，全部使用繁體中文呈現。
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
    """助手函數：徹底清除文字中殘留的 ---, *, **, #### 等 Markdown 符號"""
    text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE) 
    text = re.sub(r'#{1,6}\s*', '', text)                     
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)             
    text = re.sub(r'\*(.*?)\*', r'\1', text)                 
    text = re.sub(r'^\s*[\*\-]\s+', '', text, flags=re.MULTILINE) 
    return text.strip()

def format_analysis_html(raw_text):
    """將分析內文的大標題自動轉換為『藍色立體方框（白字）』風格的 HTML"""
    cleaned = clean_markdown_text(raw_text)
    lines = cleaned.split("\n")
    formatted_lines = []
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if re.match(r'^[一二三四五六七八九十]、\s*【.*】', line_str) or re.match(r'^【.*】', line_str):
            formatted_lines.append(f'<div class="blue-title-box">{line_str}</div>')
        else:
            formatted_lines.append(f'<p class="content-p">{line_str}</p>')
            
    return "".join(formatted_lines)

def create_pdf(news_titles, ai_analysis):
    """3. 生成大字體與藍色立體方框設計的 PDF 報告"""
    today_str = datetime.date.today().strftime("%Y/%m/%d")
    
    cleaned_news = [clean_markdown_text(title) for title in news_titles]
    news_li_html = "".join([f"<div class='news-blue-box'>{title}</div>" for title in cleaned_news])
    formatted_analysis_html = format_analysis_html(ai_analysis)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 10mm;
                background-color: #f8fafc;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                font-family: "Noto Sans CJK TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
                margin: 0;
                padding: 0;
                color: #0f172a;
                font-size: 13pt;
                line-height: 1.8;
            }}
            
            .header {{
                background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
                color: #ffffff;
                padding: 24px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 8px 18px rgba(30, 58, 138, 0.3);
            }}
            .header h1 {{
                margin: 0;
                font-size: 22pt;
                font-weight: 800;
                letter-spacing: 1px;
                text-shadow: 0 2px 4px rgba(0,0,0,0.25);
            }}
            .header .subtitle-badge {{
                display: inline-block;
                background: rgba(255, 255, 255, 0.25);
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 11pt;
                color: #ffffff;
                margin-top: 10px;
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}

            .section {{
                background: #ffffff;
                border-radius: 12px;
                padding: 22px;
                margin-bottom: 20px;
                box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
                border: 1px solid #e2e8f0;
            }}
            
            .section-main-title {{
                font-size: 16pt;
                font-weight: 800;
                color: #1e3a8a;
                margin-top: 0;
                margin-bottom: 16px;
                padding-left: 14px;
                border-left: 6px solid #2563eb;
            }}
            
            .news-blue-box {{
                background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
                color: #ffffff;
                padding: 12px 18px;
                margin-bottom: 10px;
                border-radius: 8px;
                font-size: 12.5pt;
                font-weight: 600;
                box-shadow: 0 4px 8px rgba(37, 99, 235, 0.25);
                border-bottom: 3px solid #1e40af;
            }}
            
            .blue-title-box {{
                background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
                color: #ffffff;
                padding: 12px 18px;
                margin-top: 22px;
                margin-bottom: 14px;
                border-radius: 8px;
                font-size: 14pt;
                font-weight: 800;
                box-shadow: 0 4px 10px rgba(30, 64, 175, 0.3);
                letter-spacing: 0.5px;
            }}

            .content-p {{
                margin: 0 0 12px 0;
                color: #334155;
                font-size: 13pt;
                line-height: 1.8;
            }}

            .footer {{
                margin-top: 25px;
                font-size: 10.5pt;
                color: #64748b;
                text-align: center;
                padding-top: 14px;
                border-top: 1px solid #cbd5e1;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>每日台股焦點與趨勢晨報</h1>
            <div class="subtitle-badge">📊 經濟日報即時源｜日期：{today_str}</div>
        </div>

        <div class="section">
            <div class="section-main-title">經濟日報 7小時內即時新聞頭條</div>
            {news_li_html}
        </div>

        <div class="section">
            <div class="section-main-title">Gemini 首席策略分析</div>
            {formatted_analysis_html}
        </div>

        <div class="footer">
            本報告由 GitHub Actions 自動抓取經濟日報即時新聞並經 Gemini AI 深度彙整｜僅供參考，不構成投資建議
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
    
    # 格式化為 M/D (例如: 9/7)
    today_short = datetime.datetime.now().strftime("%-m/%-d") if hasattr(datetime.datetime.now(), 'strftime') else datetime.datetime.now().strftime("%m/%d").lstrip('0').replace('/0', '/')
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
