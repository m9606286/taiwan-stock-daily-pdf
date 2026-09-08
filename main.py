import os
import time
import re
import datetime
import requests
import feedparser
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def fetch_latest_stock_news():
    """抓取過去 12 小時內最新財經頭條"""
    rss_url = "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+美股+OR+夜盤+OR+ADR+OR+半導體+OR+AI)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now_tw = datetime.datetime.now(tz_tw)
    clean_titles = []

    for entry in feed.entries:
        if not hasattr(entry, "published_parsed") or not entry.published_parsed:
            continue
        pub_utc_epoch = time.mktime(entry.published_parsed)
        pub_tw_dt = datetime.datetime.fromtimestamp(pub_utc_epoch, tz=datetime.timezone.utc).astimezone(tz_tw)
        time_diff_seconds = (now_tw - pub_tw_dt).total_seconds()

        if 0 <= time_diff_seconds <= 12 * 3600:
            title = entry.title.split(" - ")[0].strip()
            if title not in clean_titles:
                clean_titles.append(title)
        if len(clean_titles) >= 5:
            break

    if len(clean_titles) < 3:
        for entry in feed.entries:
            title = entry.title.split(" - ")[0].strip()
            if title not in clean_titles:
                clean_titles.append(title)
            if len(clean_titles) >= 5:
                break

    return clean_titles


def generate_report_content(news_titles):
    """由 Gemini 生成精簡重點分析與新聞條列"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，無法呼叫 Gemini API。")

    client = genai.Client(api_key=api_key, vertexai=False)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])

    prompt = f"""
今天是 {today_str}。以下是今日最新財經頭條：
{news_text}

請扮演專業台股財經分析師，根據上述新聞撰寫一份【台股盤前 AI 智算晨報】。

格式要求：
1. 第一行：圖卡核心標題（12字以內，重點摘要，例如：AI半導體領漲 關注夜盤波動）。
2. 第二行起：圖卡內文（約 150-200 字，分析盤勢重點與操作建議，請分為 3 個重點短段落）。
3. 第三部分：LINE 純文字訊息內容（包含開場招呼、重點新聞與分析）。

請用「===SPLIT===」將【圖卡內容】與【LINE文字訊息】分開。

範例輸出：
AI強勢領漲 聚焦台積電與夜盤
昨日美股強勁反彈，台積電ADR大漲帶動市場信心。
AI伺服器供應鏈獲利動能明確，盤中留意大盤成交量變化。
操作上建議逢低布局核心權值股，嚴格設好停損。
===SPLIT===
📊 【AI 智算台股盤前晨報】
📅 日期：{today_str}

🔥 今日核心頭條：
1. {news_titles[0] if len(news_titles) > 0 else '焦點新聞'}
2. {news_titles[1] if len(news_titles) > 1 else '焦點新聞'}

💡 盤前重點剖析：
美股與夜盤表現強勁，AI供應鏈持續成為盤面主軸。建議投資人密切關注成交量與族群輪動。

祝您今日投資順利！
"""

    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
    
    report_raw = None
    last_error = None

    for model_name in models_to_try:
        try:
            print(f"嘗試使用 Gemini 模型 [{model_name}]...")
            result = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = getattr(result, "text", None) or getattr(result, "output_text", None)
            if text:
                report_raw = text
                print(f"成功使用 [{model_name}] 生成內容！")
                break
        except Exception as e:
            last_error = e
            print(f"模型 [{model_name}] 失敗: {e}")
            continue

    if not report_raw:
        raise RuntimeError(f"所有 Gemini 模型呼叫失敗，最後錯誤: {last_error}")

    parts = report_raw.split("===SPLIT===")
    card_raw = parts[0].strip()
    line_text = parts[1].strip() if len(parts) > 1 else card_raw

    card_lines = [l.strip() for l in card_raw.splitlines() if l.strip()]
    card_title = card_lines[0] if card_lines else "台股盤前重點解析"
    card_body = "\n".join(card_lines[1:]) if len(card_lines) > 1 else card_title

    # 清理非文字符號
    card_title = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", card_title)[:14]

    return card_title, card_body, line_text


def create_fallback_3d_template(width=1080, height=1920):
    """預設 3D 科技感底圖"""
    base = Image.new("RGBA", (width, height), (10, 16, 35, 255))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([(-100, -100), (900, 900)], fill=(0, 180, 255, 45))
    glow_draw.ellipse([(200, 1000), (1200, 2000)], fill=(120, 50, 255, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    base = Image.alpha_composite(base, glow)

    draw = ImageDraw.Draw(base)
    draw.text((90, 80), "AI 盤前極速總研", fill="#00E5FF")
    draw.rounded_rectangle([60, 270, 1020, 1750], radius=30, fill=(15, 23, 42, 220), outline="#00E5FF", width=3)
    return base


def draw_3d_card(title, body_text, output_img="cover.png"):
    """繪製高質感晨報圖卡"""
    width, height = 1080, 1920
    
    template_path = "template.png"
    if os.path.exists(template_path):
        base = Image.open(template_path).convert("RGBA")
        if base.size != (width, height):
            base = base.resize((width, height), Image.Resampling.LANCZOS)
    else:
        base = create_fallback_3d_template(width, height)

    draw = ImageDraw.Draw(base)
    draw.rectangle([75, 410, 1005, 1620], fill=(10, 18, 38, 255))

    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\msjh.ttc"

    try:
        title_font = ImageFont.truetype(font_path, 46)
        body_font = ImageFont.truetype(font_path, 40)
        sub_font = ImageFont.truetype(font_path, 30)
    except OSError:
        title_font = body_font = sub_font = ImageFont.load_default()

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")

    # 日期與標籤
    draw.rectangle([210, 190, 390, 230], fill=(10, 18, 38, 255))
    draw.text((215, 195), today_str, font=sub_font, fill="#94A3B8")

    draw.rectangle([780, 85, 980, 130], fill=(10, 18, 38, 255))
    draw.text((785, 90), "DAILY REPORT", font=sub_font, fill="#00E5FF")

    # 標題
    draw.rectangle([150, 275, 930, 345], fill=(15, 25, 50, 255))
    display_title = f"【 {title} 】"
    title_bbox = draw.textbbox((0, 0), display_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (width - title_w) // 2
    
    draw.text((title_x + 2, 287), display_title, font=title_font, fill="#8B6508")
    draw.text((title_x, 285), display_title, font=title_font, fill="#FFD700")

    # 內文自動換行
    box_x1, box_x2 = 110, 970
    max_width = box_x2 - box_x1

    lines = []
    for paragraph in body_text.splitlines():
        if not paragraph.strip():
            continue
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=body_font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        lines.append("") # 空行分隔段落

    y_offset = 430
    line_height = 62

    for line in lines[:18]:
        if line == "":
            y_offset += 20
            continue
        draw.text((box_x1 + 2, y_offset + 2), line, font=body_font, fill="#000000")
        draw.text((box_x1, y_offset), line, font=body_font, fill="#F8FAFC")
        y_offset += line_height

    base.convert("RGB").save(output_img)
    print(f"圖卡成功產出：{output_img}")


def send_line_broadcast(line_text):
    """發送 LINE 圖片與文字廣播訊息"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not line_token:
        print("未設定 LINE_CHANNEL_ACCESS_TOKEN，略過推播。")
        return
    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}",
    }

    timestamp = int(time.time())
    image_url = f"https://raw.githubusercontent.com/m9606286/taiwan-stock-daily-pdf/main/cover.png?v={timestamp}"

    payload = {
        "messages": [
            {
                "type": "image",
                "originalContentUrl": image_url,
                "previewImageUrl": image_url
            },
            {
                "type": "text",
                "text": line_text
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 圖文推播成功發送！")
    else:
        print(f"LINE 發送失敗：{response.status_code}, {response.text}")


if __name__ == "__main__":
    print("1. 抓取最新財經頭條...")
    news = fetch_latest_stock_news()

    print("2. 呼叫 Gemini 生成智算晨報重點與文字...")
    card_title, card_body, line_text = generate_report_content(news)

    print("3. 繪製 3D 視覺晨報圖卡 (cover.png)...")
    draw_3d_card(card_title, card_body, "cover.png")

    print("4. 發送 LINE 圖文推播...")
    send_line_broadcast(line_text)
