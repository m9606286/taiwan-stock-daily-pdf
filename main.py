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


def generate_video_script_and_cards(news_titles):
    """由 Gemini 生成 2 分鐘腳本，並拆分為 4 個主題圖卡內容"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，無法呼叫 Gemini Developer API。")

    client = genai.Client(api_key=api_key, vertexai=False)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])

    prompt = f"""
今天是 {today_str}。以下是今日最新財經頭條：
{news_text}

請扮演專業台股財經主播，將上述頭條製作成一份約 500-600 字的【2 分鐘完整影音口播腳本】。

請嚴格按照以下【4 個區塊】輸出，區塊之間用「===CARD===」分隔：

盤前核心主軸
各位觀眾朋友早上好，歡迎收看今天的台股財經早報...（此處撰寫開場總覽）

===CARD===

即時頭條焦點
今日最關鍵的三則財經焦點動態...（此處撰寫重點新聞播報）

===CARD===

AI智算盤勢解析
進行AI深度綜合剖析，解讀對台股與科技產業影響...（此處撰寫產業觀點）

===CARD===

策略建議與風險提示
提供今日盤中觀察重點與操作風險提示...（此處撰寫結尾建議）

格式要求：
1. 每個卡片第一行為「標題」（10字以內），第二行起為「口播內文」。
2. 絕對不要出現「標題：」、「內文：」、「卡片1：」等標籤文字。
3. 語氣專業順暢，嚴格禁止使用任何 Markdown 符號（如 **、#、-、*）、表情符號，僅輸出純繁體中文。
4. 務必使用「===CARD===」分隔 4 個區塊。
"""

    # 配置輪詢模型清單，確保 404 (失效) 或 429 (配額額滿) 時自動備援切換
    models_to_try = [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash"
    ]
    
    script_raw = None
    last_error = None

    for model_name in models_to_try:
        try:
            print(f"嘗試使用模型 [{model_name}] 生成 2 分鐘腳本...")
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
            err_msg = str(e)
            print(f"模型 [{model_name}] 呼叫失敗: {err_msg}")
            # 當遭遇 404 停用、429 配額額滿或 RESOURCE_EXHAUSTED，自動跳過切換下一個模型
            continue

    if not script_raw:
        raise RuntimeError(f"所有 Gemini 模型呼叫失敗，最後錯誤: {last_error}")

    # 解析 4 張卡片內容
    raw_cards = script_raw.split("===CARD===")
    cards_data = []

    for idx, card_text in enumerate(raw_cards):
        lines = [l.strip() for l in card_text.strip().splitlines() if l.strip()]
        if not lines:
            continue
        
        raw_title = lines[0]
        raw_body = "".join(lines[1:]) if len(lines) > 1 else lines[0]

        # 清除前綴贅字與標籤
        clean_title = re.sub(r"^(標題|卡片\d+|區塊\d+)[:：\s]*", "", raw_title).strip()
        clean_body = re.sub(r"^(內文|標題)[:：\s]*", "", raw_body).strip()
        clean_body = re.sub(r"[^\w\s\u4e00-\u9fa5，。！？；：]", "", clean_body).strip()

        cards_data.append({
            "title": clean_title[:12] if clean_title else f"重點解析 {idx+1}",
            "body": clean_body
        })

    # 確保剛好 4 張卡片
    while len(cards_data) < 4:
        cards_data.append({"title": "市場觀察", "body": "祝您今日投資順利，掌握市場先機。"})
    cards_data = cards_data[:4]

    full_audio_script = " ".join([c["body"] for c in cards_data])
    return cards_data, full_audio_script


async def text_to_speech(text, output_file="narration.mp3"):
    """使用 Edge TTS 生成高音質繁體中文語音"""
    voice = "zh-TW-HsiaoChenNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def create_fallback_3d_template(width=1080, height=1920):
    """當找不到 template.png 時的備用 3D 科技底圖"""
    base = Image.new("RGBA", (width, height), (10, 16, 35, 255))
    draw = ImageDraw.Draw(base)

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


def draw_3d_card(title, body_text, card_num, total_cards=4, output_img="card.png"):
    """渲染 3D 炫彩科技風圖卡"""
    width, height = 1080, 1920
    
    # 1. 載入 3D 模板或自動生成備用模板
    template_path = "template.png"
    if os.path.exists(template_path):
        base = Image.open(template_path).convert("RGBA")
        if base.size != (width, height):
            base = base.resize((width, height), Image.Resampling.LANCZOS)
    else:
        base = create_fallback_3d_template(width, height)

    draw = ImageDraw.Draw(base)

    # 2. 清理中段面板背景（覆蓋掉舊圖片的預設文字）
    draw.rectangle([75, 410, 1005, 1620], fill=(10, 18, 38, 255))

    # 3. 字型設定
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\msjh.ttc"

    try:
        title_font = ImageFont.truetype(font_path, 48)
        body_font = ImageFont.truetype(font_path, 42)
        sub_font = ImageFont.truetype(font_path, 30)
    except OSError:
        title_font = body_font = sub_font = ImageFont.load_default()

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")

    # 4. 動態寫入頂部日期與卡片計數
    draw.rectangle([210, 190, 390, 230], fill=(10, 18, 38, 255))
    draw.text((215, 195), today_str, font=sub_font, fill="#94A3B8")

    tag_text = f"STEP {card_num:02d} / {total_cards:02d}"
    draw.rectangle([780, 85, 980, 130], fill=(10, 18, 38, 255))
    draw.text((785, 90), tag_text, font=sub_font, fill="#00E5FF")

    # 5. 渲染 3D 金屬標題
    draw.rectangle([220, 275, 860, 345], fill=(15, 25, 50, 255))
    display_title = f"【 {title} 】"
    
    title_bbox = draw.textbbox((0, 0), display_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (width - title_w) // 2
    
    # 標題金色立體發光效果
    draw.text((title_x + 2, 287), display_title, font=title_font, fill="#8B6508")
    draw.text((title_x, 285), display_title, font=title_font, fill="#FFD700")

    # 6. 動態排版與繪製內文
    box_x1, box_x2 = 100, 980
    max_width = box_x2 - box_x1

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
    if current_line:
        lines.append(current_line)

    y_offset = 430
    line_height = 66

    for line in lines[:15]:
        draw.text((box_x1 + 2, y_offset + 2), line, font=body_font, fill="#000000")
        draw.text((box_x1, y_offset), line, font=body_font, fill="#F8FAFC")
        y_offset += line_height

    base.convert("RGB").save(output_img)


def render_multi_card_video(cards_data, audio_file="narration.mp3", output_mp4="daily_report.mp4"):
    """渲染多頁動態切換 3D 圖卡的 2 分鐘 MP4 影片"""
    audio = AudioFileClip(audio_file)
    total_duration = audio.duration
    num_cards = len(cards_data)
    per_card_duration = total_duration / num_cards

    clips = []
    for idx, card in enumerate(cards_data):
        img_filename = f"card_{idx+1}.png"
        draw_3d_card(card["title"], card["body"], card_num=idx+1, total_cards=num_cards, output_img=img_filename)
        
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

    video_url = "https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/daily_report.mp4"
    preview_url = "https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/card_1.png"

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

    print("2. 呼叫 Gemini 生成 2 分鐘腳本與 4 張圖卡結構...")
    cards, audio_script = generate_video_script_and_cards(news)

    print("3. 合成 2 分鐘高音質語音 (Edge-TTS)...")
    asyncio.run(text_to_speech(audio_script, "narration.mp3"))

    print("4. 繪製 3D 科技感立體圖卡並渲染影片...")
    render_multi_card_video(cards, "narration.mp3", "daily_report.mp4")

    print("5. 發送 LINE 影音推播...")
    send_line_broadcast()
