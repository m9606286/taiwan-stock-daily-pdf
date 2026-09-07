import time
from google.genai import errors

def generate_report_content(news_titles):
    """2. 將新聞餵給 Gemini 生成深度分析內文（含 503 重試機制）"""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    news_text = "\n".join([f"- {title}" for title in news_titles])
    
    prompt = f"""
以下是今日剛發布的台股重點即時新聞標題：
{news_text}

請扮演專業的台股分析師，根據上述最新的新聞內容，幫我撰寫一份結構清晰、專業且易讀的「每日台股市場剖析」。
請務必包含以下三大區塊：
一、【大盤焦點與市場趨勢】
二、【熱門族群與重點個股動態】
三、【後續操作觀察與風險提示】

請全部使用繁體中文呈現，用語精煉專業，重點明確。
"""
    
    # 重試機制：最多嘗試 3 次
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            return response.text
        except errors.APIError as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Gemini API 繁忙 (503)，等待 5 秒後進行第 {attempt + 1} 次重試...")
                time.sleep(5)
            else:
                raise e
                
    # 若重試三次仍失敗，進行最後一次呼叫
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    return response.text
