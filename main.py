import os
import time
import re
import datetime
import asyncio
import requests
import feedparser
import edge_tts
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips


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


def _is_retryable_gemini_error(error):
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    message = str(error).lower()
    if status in (404,) or "404" in message or "not_found" in message or "not found" in message:
        return False
    if status in (429, 500, 503, 504):
        return True

    retry_markers = (
        "503", "429", "500", "504", "unavailable", "overloaded",
        "resource exhausted", "temporarily", "try again", "timeout",
    )
    return any(marker in message for marker in retry_markers)


def generate_video_script_and_cards(news_titles):
    """由 Gemini 生成 2 分鐘腳本，並結構化拆分為 4 個主題圖卡內容"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，無法呼叫 Gemini Developer API。")

    client = genai.Client(api_key=api_key, vertexai=False)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])

    prompt = f"""
今天是 {today_str}。以下是今日清晨最新財經頭條：
{news_text}

請扮演專業台股財經主播，將上述頭條製作成一份約 500-600 字的【2 分鐘完整影音口播腳本】。

請嚴格按照以下【4 個區塊】輸出，區塊之間用「===CARD===」分隔：

卡片1【盤前開場】：
標題：今日盤前核心主軸
內文：開場問好、總覽今日市場焦點與整體氣氛。

===CARD===

卡片2【即時新聞重點】：
標題：重點財經頭條
內文：播報今日最關鍵的 3 則頭條新聞重點。

===CARD===

卡片3【AI 深度觀點】：
標題：AI 智算盤勢解析
內文：進行 AI 綜合分析，剖析對台股大盤、半導體供應鏈或熱門概念股的影響。

===CARD===

卡片4【今日觀察與風險】：
標題：策略建議與風險提示
內文：提供投資人今日盤中觀察重點、操作策略與風險警示。

格式嚴格要求：
1. 語氣自然流暢、專業且抑揚頓挫。
2. 嚴格禁止使用任何 Markdown 符號（如 **、#、-、*）、表情符號或英文特殊字元，僅輸出純繁體中文。
3. 務必精確使用「===CARD===」分隔 4 個區塊。
"""

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
    script_raw = None
    last_error = None

    for model_name in models_to_try:
        for attempt in range(1, 4):
            try:
                print(f"嘗試使用模型 [{model_name}] 生成 2 分鐘腳本 (第 {attempt} 次)...")
                result = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = getattr(result, "text", None) or getattr(result, "output_text", None)
                if text:
                    script_raw = text
                    print(f"成功使用 [{model_name}] 生成腳本！")
                    break
            except Exception as e:
                last_error = e
                print(f"模型 [{model_name}] 第 {attempt} 次呼叫失敗: {e}")
                if attempt < 3 and _is_retryable_gemini_error(e):
                    time.sleep(attempt * 3)
                    continue
                break
        if script_raw:
            break

    if not script_raw:
        raise RuntimeError(f"所有 Gemini 模型呼叫失敗，最後錯誤: {last_error}")

    # 解析 4 張卡片內容
    raw_cards = script_raw.split("===CARD===")
    cards_data = []

    for idx, card_text in enumerate(raw_cards):
        clean_text = re.sub(r"[^\w\s\u4e00-\u9fa5，。！？；：]", "", card_text).strip()
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        
        title = f"卡片 {idx+1}"
        body = clean_text
        
        if lines:
            if "標題" in lines[0]:
                title = lines[0].replace("標題", "").strip()
                body = "".join(lines[1:])
            else:
                title = lines[0][:10]
                body = "".join(lines)
                
        body = re.sub(r"^(內文|卡片\d+)", "", body).strip()
        cards_data.append({"title": title, "body": body})

    # 確保剛好 4 張
    while len(cards_data) < 4:
        cards_data.append({"title": "市場觀察", "body": "祝您今日投資順利，掌握市場先機。"})
    cards_data = cards_data[:4]

    # 合併完整口播腳本
    full_audio_script = " ".join([c["body"] for c in cards_data])
    return cards_data, full_audio_script


async def text_to_speech(text, output_file="narration.mp3"):
    """使用 Edge TTS 生成高音質繁體中文語音"""
    voice = "zh-TW-HsiaoChenNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def draw_3d_card(title, body_text, card_num, total_cards=4, output_img="card.png"):
    """使用 Pillow 繪製具有 3D 浮雕、玻璃質感與科技光效的 9:16 短影音圖卡 (1080x1920)"""
    width, height = 1080, 1920
    
    # 1. 建立深色科技風背景漸層 (Dark Cyberpunk Gradient)
    base = Image.new("RGBA", (width, height), (11, 19, 41, 255))
    draw = ImageDraw.Draw(base)

    # 背景幾何光暈裝飾 (Glow effect)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # 頂部青藍光暈
    glow_draw.ellipse([(-200, -200), (800, 800)], fill=(56, 189, 248, 40))
    # 底部藍紫光暈
    glow_draw.ellipse([(400, 1100), (1300, 2000)], fill=(139, 92, 246, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(100))
    base = Image.alpha_composite(base, glow)
    draw = ImageDraw.Draw(base)

    # 字型載入
    font_candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
    ]
    title_font = sub_font = body_font = card_tag_font = None
    for font_path in font_candidates:
        try:
            title_font = ImageFont.truetype(font_path, 64)
            sub_font = ImageFont.truetype(font_path, 42)
            body_font = ImageFont.truetype(font_path, 46)
            card_tag_font = ImageFont.truetype(font_path, 32)
            break
        except OSError:
            continue
    if title_font is None:
        title_font = sub_font = body_font = card_tag_font = ImageFont.load_default()

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")

    # 2. 頂部抬頭區塊
    draw.text((80, 110), "AI 盤前極速總研", font=title_font, fill="#38bdf8")
    draw.text((80, 200), f"📅 {today_str} ｜ 全方位財經智算", font=sub_font, fill="#94a3b8")

    # 頁碼標籤 (例: 01 / 04)
    tag_text = f"STEP {card_num:02d} / {total_cards:02d}"
    draw.rectangle([(800, 120), (1000, 180)], fill=(30, 41, 59, 200), outline="#38bdf8", width=2)
    draw.text((820, 133), tag_text, font=card_tag_font, fill="#38bdf8")

    # 3. 繪製 3D 立體玻璃感卡片主體 (3D Glassmorphism Box)
    box_x1, box_y1 = 60, 280
    box_x2, box_y2 = 1020, 1780
    corner_radius = 35

    # 3D 陰影層 (Drop Shadow)
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        [box_x1 + 15, box_y1 + 20, box_x2 + 15, box_y2 + 20],
        radius=corner_radius,
        fill=(0, 0, 0, 160)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(25))
    base = Image.alpha_composite(base, shadow)

    # 3D 半透明玻璃主體
    glass = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glass_draw = ImageDraw.Draw(glass)
    glass_draw.rounded_rectangle(
        [box_x1, box_y1, box_x2, box_y2],
        radius=corner_radius,
        fill=(15, 23, 42, 210),
        outline="#38bdf8",
        width=3
    )
    # 卡片頂部高光邊條 (3D Bevel Light Effect)
    glass_draw.rounded_rectangle(
        [box_x1 + 3, box_y1 + 3, box_x2 - 3, box_y1 + 15],
        radius=corner_radius,
        fill=(255, 255, 255, 40)
    )
    base = Image.alpha_composite(base, glass)
    draw = ImageDraw.Draw(base)

    # 4. 卡片內部標題與裝飾
    draw.text((110, 340), f"【 {title} 】", font=title_font, fill="#f8fafc")
    draw.line([(110, 430), (970, 430)], fill="#0284c7", width=3)

    # 5. 排版內文
    margin = 110
    max_width = box_x2 - box_x1 - 100
    lines = []
    current_line = ""

    for char in body_text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=body_font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)

    y_offset = 480
    for line in lines[:18]:
        # 給文字加上微微立體文字陰影
        draw.text((margin + 2, y_offset + 2), line, font=body_font, fill="#0f172a")
        draw.text((margin, y_offset), line, font=body_font, fill="#e2e8f0")
        y_offset += 68

    # 底部裝飾條
    draw.rectangle([(80, 1810), (1000, 1815)], fill="#38bdf8")

    base.convert("RGB").save(output_img)


def render_multi_card_video(cards_data, audio_file="narration.mp3", output_mp4="daily_report.mp4"):
    """渲染多頁動態切換圖卡的 MP4 影片（MoviePy 2.0+ 相容）"""
    audio = AudioFileClip(audio_file)
    total_duration = audio.duration
    num_cards = len(cards_data)
    per_card_duration = total_duration / num_cards

    clips = []
    for idx, card in enumerate(cards_data):
        img_filename = f"card_{idx+1}.png"
        draw_3d_card(card["title"], card["body"], card_num=idx+1, total_cards=num_cards, output_img=img_filename)
        
        # 動態計算最後一張圖卡的時間補齊
        dur = per_card_duration if idx < num_cards - 1 else (total_duration - per_card_duration * (num_cards - 1))
        clip = ImageClip(img_filename).with_duration(dur)
        clips.append(clip)

    final_clip = concatenate_videoclips(clips, method="compose").with_audio(audio)
    try:
        final_clip.write_videofile(output_mp4, fps=2, codec="libx264", audio_codec="aac")
    finally:
        audio.close()
        for c in clips:
            c.close()
        final_clip.close()


def send_line_broadcast():
    """發送 LINE 影音推播通知"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not line_token:
        print("未設定 LINE_CHANNEL_ACCESS_TOKEN，略過推播。")
        return
    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}",
    }

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_short = datetime.datetime.now(tz_tw).strftime("%m/%d").lstrip("0").replace("/0", "/")
    timestamp = int(time.time())

    video_url = f"https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/daily_report.mp4?v={timestamp}"
    preview_url = f"https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/card_1.png?v={timestamp}"

    payload = {
        "messages": [
            {
                "type": "video",
                "originalContentUrl": video_url,
                "previewImageUrl": preview_url,
            },
            {
                "type": "text",
                "text": f"🎬 {today_short} 台股盤前 2 分鐘【AI 智算深度晨報】已生成！含 3D 視覺解析與即時新聞動態。",
            },
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 影音推播成功！")
    else:
        print(f"LINE 發送失敗：{response.status_code}, {response.text}")


if __name__ == "__main__":
    print("1. 抓取最新財經頭條...")
    news = fetch_latest_stock_news()

    print("2. Gemini 生成 2 分鐘深度腳本與 4 張圖卡結構...")
    cards, audio_script = generate_video_script_and_cards(news)

    print("3. 合成 2 分鐘高音質語音 (Edge-TTS)...")
    asyncio.run(text_to_speech(audio_script, "narration.mp3"))

    print("4. 繪製 3D 科技感立體圖卡並渲染影片...")
    render_multi_card_video(cards, "narration.mp3", "daily_report.mp4")

    print("5. 發送 LINE 影音推播...")
    send_line_broadcast()
