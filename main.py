import os
import time
import re
import datetime
import asyncio
import requests
import feedparser
import edge_tts
from google import genai
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip, ImageClip

def fetch_latest_stock_news():
    """抓取過去 12 小時內最新財經頭條"""
    rss_url = "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+美股+OR+夜盤+OR+ADR+OR+半導體+OR+AI)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now_tw = datetime.datetime.now(tz_tw)
    clean_titles = []
    
    for entry in feed.entries:
        if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
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

def generate_video_script(news_titles):
    """由 Gemini 生成 60 秒短影音旁白逐字稿"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y 年 %m 月 %d 日")
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
今天是 {today_str}。以下是今日清晨最新財經頭條：
{news_text}

請扮演專業財經主播，將上述頭條濃縮成一份約 150-200 字的【60 秒短影音口播腳本】。
要求：
1. 開頭快速問好並點出今日市場核心主軸。
2. 語氣自然流暢、抑揚頓挫，適合語音合成朗讀。
3. 嚴格禁止使用任何 Markdown 符號（如 **、#、-），僅輸出純文字逐字稿。
"""
    
    config = {"automatic_function_calling": {"disable": True}}
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=config
    )
    
    # 徹底清除 Markdown 符號
    script = re.sub(r'[\*\#\-\_]', '', response.text).strip()
    return script

async def text_to_speech(text, output_file="narration.mp3"):
    """使用 Edge TTS 生成高音質繁體中文語音（雲希）"""
    voice = "zh-TW-YunXiNeural" # 自然流暢的台灣男聲
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def create_cover_image(script_text, output_img="cover.png"):
    """使用 Pillow 生成 9:16 短影音封面圖卡 (1080x1920)"""
    width, height = 1080, 1920
    img = Image.new('RGB', (width, height), color='#0b1329')
    draw = ImageDraw.Draw(img)
    
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")
    
    # 嘗試載入系統中文字型
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    try:
        title_font = ImageFont.truetype(font_path, 80)
        sub_font = ImageFont.truetype(font_path, 45)
        body_font = ImageFont.truetype(font_path, 38)
    except:
        title_font = sub_font = body_font = ImageFont.load_default()

    # 繪製標題與日期
    draw.text((80, 150), "盤前極速總研", font=title_font, fill="#38bdf8")
    draw.text((80, 260), f"📅 {today_str} 每日 60 秒晨報", font=sub_font, fill="#94a3b8")
    draw.line([(80, 330), (1000, 330)], fill="#334155", width=4)

    # 繪製逐字稿文字區域（自動折行）
    margin = 80
    max_width = width - (2 * margin)
    lines = []
    current_line = ""
    
    for char in script_text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=body_font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)

    y_offset = 380
    for line in lines[:25]: # 限制最大顯示行數
        draw.text((margin, y_offset), line, font=body_font, fill="#e2e8f0")
        y_offset += 55

    img.save(output_img)

def render_video(audio_file="narration.mp3", image_file="cover.png", output_mp4="daily_report.mp4"):
    """結合圖卡與語音生成 MP4 影片"""
    audio = AudioFileClip(audio_file)
    clip = ImageClip(image_file).set_duration(audio.duration)
    video = clip.set_audio(audio)
    video.write_videofile(output_mp4, fps=1, codec="libx264", audio_codec="aac")

def send_line_broadcast():
    """發送 LINE 影音推播通知"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_short = datetime.datetime.now(tz_tw).strftime("%m/%d").lstrip('0').replace('/0', '/')
    timestamp = int(time.time())
    
    # jsDelivr CDN 直連 MP4 網址
    video_url = f"https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/daily_report.mp4?v={timestamp}"
    preview_url = f"https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/cover.png?v={timestamp}"
    
    payload = {
        "messages": [
            {
                "type": "video",
                "originalContentUrl": video_url,
                "previewImageUrl": preview_url
            },
            {
                "type": "text",
                "text": f"🎬 {today_short} 台股盤前 60 秒影音晨報生成完畢！"
            }
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
    
    print("2. Gemini 生成影音腳本...")
    script = generate_video_script(news)
    
    print("3. 合成高音質語音 (Edge-TTS)...")
    asyncio.run(text_to_speech(script, "narration.mp3"))
    
    print("4. 製作短影音封面圖卡...")
    create_cover_image(script, "cover.png")
    
    print("5. 渲染 MP4 影片檔案...")
    render_video("narration.mp3", "cover.png", "daily_report.mp4")
    
    print("6. 發送 LINE 影音推播...")
    send_line_broadcast()
