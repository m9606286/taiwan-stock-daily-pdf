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
from moviepy import AudioFileClip, ImageClip


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
    """判斷是否為可重試錯誤（503 / 過載 / 暫時不可用）。404 NOT_FOUND 不重試。"""
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    message = str(error).lower()
    if status in (404,) or "404" in message or "not_found" in message or "not found" in message:
        return False
    if status in (429, 500, 503, 504):
        return True

    retry_markers = (
        "503",
        "429",
        "500",
        "504",
        "unavailable",
        "overloaded",
        "resource exhausted",
        "temporarily",
        "try again",
        "timeout",
    )
    return any(marker in message for marker in retry_markers)


def generate_video_script(news_titles):
    """由 Gemini 生成 60 秒短影音旁白逐字稿（含自動重試與模型備援機制）"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，無法呼叫 Gemini Developer API。")

    # 明確使用 Gemini Developer API（api_key），避免誤走 Vertex AI 導致模型 404
    client = genai.Client(api_key=api_key, vertexai=False)
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

    models_to_try = [
        "gemini-3.6-flash",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
    ]
    tried = set()
    script_text = None
    last_error = None

    def _suggested_model(error):
        match = re.search(r"use models/(gemini-[a-z0-9.\-]+)", str(error), re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_text(result):
        if result is None:
            return None
        text = getattr(result, "text", None) or getattr(result, "output_text", None)
        if text:
            return text
        return None

    idx = 0
    while idx < len(models_to_try):
        model_name = models_to_try[idx]
        idx += 1
        if model_name in tried:
            continue
        tried.add(model_name)

        for attempt in range(1, 4):
            try:
                print(f"嘗試使用模型 [{model_name}] 生成腳本 (第 {attempt} 次)...")
                try:
                    result = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                except Exception as generate_error:
                    # 部分帳號/SDK 版本對舊 generateContent 回 404，改走 Interactions API
                    print(f"generate_content 失敗，改試 interactions.create: {generate_error}")
                    last_error = generate_error
                    result = client.interactions.create(
                        model=model_name,
                        input=prompt,
                    )
                script_text = _extract_text(result)
                if script_text:
                    print(f"成功使用 [{model_name}] 生成腳本！")
                    break
            except Exception as e:
                last_error = e
                print(f"模型 [{model_name}] 第 {attempt} 次呼叫失敗: {e}")
                suggested = _suggested_model(e)
                if suggested and suggested not in tried and suggested not in models_to_try:
                    print(f"API 建議改用模型 [{suggested}]，加入備援清單。")
                    models_to_try.append(suggested)
                if attempt < 3 and _is_retryable_gemini_error(e):
                    wait_seconds = attempt * 3
                    print(f"偵測到可重試錯誤（含 503），等待 {wait_seconds} 秒後重試...")
                    time.sleep(wait_seconds)
                    continue
                break

        if script_text:
            break

    if not script_text:
        raise RuntimeError(f"所有 Gemini 模型呼叫失敗，最後錯誤: {last_error}")

    script = re.sub(r"[\*\#\-\_]", "", script_text).strip()
    return script


async def text_to_speech(text, output_file="narration.mp3"):
    """使用 Edge TTS 生成高音質繁體中文語音"""
    voice = "zh-TW-YunXiNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def create_cover_image(script_text, output_img="cover.png"):
    """使用 Pillow 生成 9:16 短影音封面圖卡 (1080x1920)"""
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color="#0b1329")
    draw = ImageDraw.Draw(img)

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")

    font_candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\mingliu.ttc",
    ]
    title_font = sub_font = body_font = None
    for font_path in font_candidates:
        try:
            title_font = ImageFont.truetype(font_path, 80)
            sub_font = ImageFont.truetype(font_path, 45)
            body_font = ImageFont.truetype(font_path, 38)
            break
        except OSError:
            continue
    if title_font is None:
        title_font = sub_font = body_font = ImageFont.load_default()

    draw.text((80, 150), "盤前極速總研", font=title_font, fill="#38bdf8")
    draw.text((80, 260), f"📅 {today_str} 每日 60 秒晨報", font=sub_font, fill="#94a3b8")
    draw.line([(80, 330), (1000, 330)], fill="#334155", width=4)

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
    for line in lines[:25]:
        draw.text((margin, y_offset), line, font=body_font, fill="#e2e8f0")
        y_offset += 55

    img.save(output_img)


def render_video(audio_file="narration.mp3", image_file="cover.png", output_mp4="daily_report.mp4"):
    """結合圖卡與語音生成 MP4 影片（MoviePy 2.0+：with_duration / with_audio）"""
    audio = AudioFileClip(audio_file)
    clip = ImageClip(image_file).with_duration(audio.duration)
    video = clip.with_audio(audio)
    try:
        video.write_videofile(output_mp4, fps=1, codec="libx264", audio_codec="aac")
    finally:
        audio.close()
        clip.close()
        video.close()


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
    preview_url = f"https://cdn.jsdelivr.net/gh/m9606286/taiwan-stock-daily-pdf@main/cover.png?v={timestamp}"

    payload = {
        "messages": [
            {
                "type": "video",
                "originalContentUrl": video_url,
                "previewImageUrl": preview_url,
            },
            {
                "type": "text",
                "text": f"🎬 {today_short} 台股盤前 60 秒影音晨報生成完畢！",
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
