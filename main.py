import os
import time
import re
import datetime
import requests
import feedparser
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def fetch_all_market_news():
    """廣泛抓取最新台股、美股、產業相關新聞"""
    rss_urls = [
        "https://news.google.com/rss/search?q=site:money.udn.com+(台股+OR+半導體+OR+AI+OR+電子+OR+金融)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=site:ctee.com.tw+(台股+OR+產業+OR+營收+OR+概念股)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=site:cnyes.com+(台股+OR+美股+OR+夜盤+OR+ADR)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ]

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now_tw = datetime.datetime.now(tz_tw)
    clean_titles = []

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.split(" - ")[0].strip()
                # 簡單過濾重複與無關新聞
                if title and title not in clean_titles:
                    clean_titles.append(title)
                if len(clean_titles) >= 15:
                    break
        except Exception as e:
            print(f"抓取 RSS 失敗 ({url}): {e}")

    return clean_titles[:12]  # 取得最新 12 則全市場焦點新聞


def generate_deep_industry_analysis(news_titles):
    """由 Gemini AI 進行產業歸類與精闢分析"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，無法呼叫 Gemini API。")

    client = genai.Client(api_key=api_key, vertexai=False)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")
    news_text = "\n".join([f"- {title}" for title in news_titles])

    prompt = f"""
今天是 {today_str}。以下是搜集到的最新市場即時新聞：
{news_text}

請扮演首席台股產業分析師，針對上述新聞進行【產業歸納】與【精闢盤勢分析】。

輸出格式要求（請嚴格遵守分隔符號）：

[卡片標題]
寫出一個吸睛、專業的盤前核心主題（12字以內，如：AI與半導體領軍 族群輪動加速）。

[產業分類與焦點新聞]
請將新聞歸類為 3-4 個主要產業別（例如：【半導體/晶圓代工】、【AI伺服器/散熱】、【車用/光電】、【金融/傳產】），每個產業別列出 1-2 點關鍵摘要（每點 20 字以內，精準寫出重點）。

[AI精闢分析]
撰寫 150 字左右的精闢分析，包含：
1. 市場資金流向與利多/利空解讀
2. 今日觀察族群與盤前操作策略

===SPLIT===

[LINE推播內容]
撰寫一份適合手機閱讀的 LINE 格式訊息，包含開場、產業分類亮點、AI 深度剖析與祝語。

範例輸出形式：
AI與半導體領頭 聚焦夜盤連動
【半導體/先進封裝】台積電法說帶勁，設備股接續吸金。
【AI伺服器/散熱】美股AI巨頭走強，散熱族群營收亮眼。
【金融/傳產】外資回補金融股，重電題材持續發酵。
市場焦點集中於AI供應鏈，夜盤與美股ADR表現強勁，帶動台股開高預期。操作上建議順應資金流向，佈局展望明確的權值與績優中小型股，嚴格落實停損停利。
===SPLIT===
📊 【AI 智算台股產業盤前晨報】
📅 日期：{today_str}

🔍 【今日重點產業歸納】
🔹 半導體/先進封裝：台積電法說帶勁，帶動設備族群
🔹 AI伺服器/散熱：美股AI走強，伺服器供應鏈受惠
🔹 金融/傳產：外資點火金融，政策題材帶動重電

💡 【AI 首席分析師精闢剖析】
今日盤面主軸依然由 AI 供應鏈與半導體領軍。夜盤與 ADR 表現亮眼給予多頭信心，操作上建議聚焦具營收支撐之績優股。

祝您今日投資順利！
"""

    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
    report_raw = None
    last_error = None

    for model_name in models_to_try:
        try:
            print(f"嘗試使用 Gemini 模型 [{model_name}] 進行產業分析...")
            result = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = getattr(result, "text", None) or getattr(result, "output_text", None)
            if text:
                report_raw = text
                print(f"成功使用 [{model_name}] 完成分析！")
                break
        except Exception as e:
            last_error = e
            print(f"模型 [{model_name}] 失敗: {e}")

    if not report_raw:
        raise RuntimeError(f"Gemini API 呼叫失敗: {last_error}")

    parts = report_raw.split("===SPLIT===")
    card_raw = parts[0].strip()
    line_text = parts[1].strip() if len(parts) > 1 else card_raw

    card_lines = [l.strip() for l in card_raw.splitlines() if l.strip()]
    card_title = card_lines[0] if card_lines else "台股產業盤前解析"

    # 分離產業歸納與 AI 分析
    industry_sections = []
    ai_analysis_lines = []
    is_analysis_part = False

    for line in card_lines[1:]:
        if "市場" in line or "操作" in line or "建議" in line or "觀測" in line or len(industry_sections) >= 4:
            is_analysis_part = True
        
        if is_analysis_part:
            ai_analysis_lines.append(line)
        else:
            industry_sections.append(line)

    industry_text = "\n".join(industry_sections)
    ai_analysis_text = "\n".join(ai_analysis_lines)

    card_title = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", card_title)[:14]

    return card_title, industry_text, ai_analysis_text, line_text


def create_futuristic_3d_card(title, industry_text, ai_analysis, output_img="cover.png"):
    """繪製手機專用、立體科技感 3D 圖卡"""
    width, height = 1080, 1920

    # 1. 建立 3D 深色科技背景
    base = Image.new("RGBA", (width, height), (12, 18, 34, 255))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    
    # 3D 光暈效果
    glow_draw.ellipse([(-150, -150), (950, 950)], fill=(0, 210, 255, 40))
    glow_draw.ellipse([(150, 1000), (1250, 2100)], fill=(130, 60, 255, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    base = Image.alpha_composite(base, glow)

    draw = ImageDraw.Draw(base)

    # 2. 字型設定
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\msjh.ttc"

    try:
        header_font = ImageFont.truetype(font_path, 42)
        title_font = ImageFont.truetype(font_path, 46)
        sec_title_font = ImageFont.truetype(font_path, 36)
        content_font = ImageFont.truetype(font_path, 32)
        sub_font = ImageFont.truetype(font_path, 28)
    except OSError:
        header_font = title_font = sec_title_font = content_font = sub_font = ImageFont.load_default()

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")

    # 頂部 Header
    draw.text((80, 85), "AI MARKET INTELLIGENCE", font=sub_font, fill="#00E5FF")
    draw.text((800, 85), today_str, font=sub_font, fill="#94A3B8")
    draw.line([(80, 130), (1000, 130)], fill=(0, 229, 255, 100), width=2)

    # 主標題玻璃面板 (3D Box)
    draw.rounded_rectangle([75, 160, 1005, 270], radius=20, fill=(20, 32, 60, 230), outline="#00E5FF", width=2)
    display_title = f"【 {title} 】"
    title_bbox = draw.textbbox((0, 0), display_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_w) // 2, 192), display_title, font=title_font, fill="#FFD700")

    # 區塊 1：產業分類歸納面板
    draw.rounded_rectangle([75, 300, 1005, 1020], radius=24, fill=(16, 26, 48, 240), outline="#38BDF8", width=2)
    draw.rectangle([100, 330, 420, 385], fill=(30, 58, 108, 255))
    draw.text((115, 340), "🏷️ 焦點產業即時歸納", font=sec_title_font, fill="#38BDF8")

    # 繪製產業內容
    y_idx = 410
    for line in industry_text.splitlines():
        if not line.strip():
            continue
        # 自動截斷過長文字以符合圖卡版面
        if len(line) > 28:
            line = line[:27] + "..."
        draw.text((115, y_idx), line, font=content_font, fill="#F1F5F9")
        y_idx += 68

    # 區塊 2：AI 精闢分析面板
    draw.rounded_rectangle([75, 1050, 1005, 1780], radius=24, fill=(16, 26, 48, 240), outline="#A855F7", width=2)
    draw.rectangle([100, 1080, 420, 1135], fill=(58, 30, 108, 255))
    draw.text((115, 1090), "🧠 AI 首席精闢剖析", font=sec_title_font, fill="#C084FC")

    # 繪製 AI 精闢分析內容 (自動換行)
    max_w = 830
    ai_lines = []
    for paragraph in ai_analysis.splitlines():
        if not paragraph.strip():
            continue
        cur = ""
        for c in paragraph:
            test = cur + c
            bbox = draw.textbbox((0, 0), test, font=content_font)
            if bbox[2] - bbox[0] <= max_w:
                cur = test
            else:
                ai_lines.append(cur)
                cur = c
        if cur:
            ai_lines.append(cur)

    y_idx = 1160
    for line in ai_lines[:9]:
        draw.text((115, y_idx), line, font=content_font, fill="#E2E8F0")
        y_idx += 62

    # 底部標註
    draw.text((360, 1820), "Generated by Gemini AI • 盤前智算晨報", font=sub_font, fill="#64748B")

    base.convert("RGB").save(output_img)
    print(f"極速 3D 產業圖卡成功產出：{output_img}")


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
        print("LINE 產業圖文推播成功發送！")
    else:
        print(f"LINE 發送失敗：{response.status_code}, {response.text}")


if __name__ == "__main__":
    print("1. 廣泛抓取最新市場新聞...")
    news = fetch_all_market_news()

    print("2. 呼叫 Gemini AI 進行產業歸類與深度剖析...")
    card_title, industry_text, ai_analysis, line_text = generate_deep_industry_analysis(news)

    print("3. 繪製手機專用 3D 視覺產業圖卡 (cover.png)...")
    create_futuristic_3d_card(card_title, industry_text, ai_analysis, "cover.png")

    print("4. 發送 LINE 圖文推播...")
    send_line_broadcast(line_text)
