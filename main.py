import os
import time
import datetime
import requests
import feedparser
from google import genai


def fetch_comprehensive_market_news():
    """多源頭廣抓今早最新全市場財經新聞"""
    rss_urls = [
        "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+半導體+OR+AI+OR+電子+OR+金融)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=site:ctee.com.tw+(台股+OR+產業+OR+營收+OR+概念股)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=site:cnyes.com+(台股+OR+美股+OR+夜盤+OR+ADR+OR+台積電)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=site:ettoday.net/news/focus/財經/+(台股+OR+AI)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ]

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now_tw = datetime.datetime.now(tz_tw)
    clean_titles = []

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.split(" - ")[0].strip()
                # 排除重複與長度過短標題
                if title and len(title) > 6 and title not in clean_titles:
                    clean_titles.append(title)
                if len(clean_titles) >= 30:
                    break
        except Exception as e:
            print(f"抓取 RSS 失敗 ({url}): {e}")

    print(f"總共抓取到 {len(clean_titles)} 則今早市場新聞。")
    return clean_titles[:25]


def generate_deep_text_report(news_titles):
    """由 Gemini AI 進行多產業歸類與深度極精闢盤勢剖析"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，無法呼叫 Gemini API。")

    client = genai.Client(api_key=api_key, vertexai=False)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")
    news_text = "\n".join([f"- {title}" for title in news_titles])

    prompt = f"""
今天是 {today_str}。以下是搜集到的最新今早市場焦點新聞：
{news_text}

請扮演華爾街/頂尖投顧的首席台股策略分析師，針對上述大量新聞進行【多產業精準歸納】與【深度精闢盤勢分析】。

請撰寫一份專供 LINE 手機閱讀的【台股全產業盤前 AI 智算晨報】。

格式與內容要求：
1. **標題與日期**：加上視覺 Icon 排版。
2. **多產業重點歸納（請歸納出至少 5-6 個不同產業別）**：
   例如：【半導體/先進封裝】、【AI伺服器/組裝/散熱】、【IC設計/矽智財】、【光通訊/CPO】、【記憶體/被動元件】、【金融/傳產/政策題材】等。
   - 每個產業別下，請根據新聞列出 2-3 個關鍵動向與供應鏈利多/利空摘要。
3. **AI 首席分析師深度精闢剖析（請分 3 個維度撰寫，內容要具體、有深度、不寫套話）**：
   - 💡 **【資金流向與夜盤/美股連動】**：剖析外資/主力資金動向、美股/ADR/夜盤對台股開盤之影響。
   - ⚡ **【關鍵族群與題材急單動向】**：深入解讀今日最有機會發動或需避險的族群（如 CoWoS 設備、浸沒散熱、水冷、CPO、伺服器急單等）。
   - 🎯 **【盤前具體操作與避險策略】**：給出明確的支撐壓力看法、開盤應對（如高開如何處理、逢低布局哪些績優股、停損停利點落何處）。

請使用輕鬆但極專業的語氣，善用 Emoji 排版，讓手機閱讀體驗極佳。

直接輸出 LINE 文字內容即可，不需要任何分隔符號或額外說明。
"""

    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
    report_text = None
    last_error = None

    for model_name in models_to_try:
        try:
            print(f"嘗試使用 Gemini 模型 [{model_name}] 進行全產業深度分析...")
            result = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = getattr(result, "text", None) or getattr(result, "output_text", None)
            if text:
                report_text = text.strip()
                print(f"成功使用 [{model_name}] 完成深度分析！")
                break
        except Exception as e:
            last_error = e
            print(f"模型 [{model_name}] 失敗: {e}")

    if not report_text:
        raise RuntimeError(f"Gemini API 呼叫失敗: {last_error}")

    return report_text


def send_line_text_broadcast(line_text):
    """發送 LINE 純文字廣播訊息"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not line_token:
        print("未設定 LINE_CHANNEL_ACCESS_TOKEN，略過推播。")
        return
    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}",
    }

    # 只發送純文字訊息，速度極快且不占空間
    payload = {
        "messages": [
            {
                "type": "text",
                "text": line_text
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 純文字深度晨報推播成功發送！")
    else:
        print(f"LINE 發送失敗：{response.status_code}, {response.text}")


if __name__ == "__main__":
    print("1. 大規模抓取今早全市場新聞...")
    news = fetch_comprehensive_market_news()

    print("2. 呼叫 Gemini AI 進行多產業歸類與深度精闢剖析...")
    line_report = generate_deep_text_report(news)

    print("3. 發送 LINE 純文字晨報推播...")
    send_line_text_broadcast(line_report)
