def generate_video_script(news_titles):
    """由 Gemini 生成 60 秒短影音旁白逐字稿（含自動重試與模型備援機制）"""
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
    
    # 優先使用的模型與備援模型順序
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash"
    ]
    
    response = None
    last_error = None

    for model_name in models_to_try:
        # 每個模型嘗試最多 3 次，間隔遞增
        for attempt in range(1, 4):
            try:
                print(f"嘗試使用模型 [{model_name}] 生成腳本 (第 {attempt} 次)...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    print(f"成功使用 [{model_name}] 生成腳本！")
                    break
            except Exception as e:
                last_error = e
                print(f"模型 [{model_name}] 第 {attempt} 次呼叫失敗: {e}")
                time.sleep(attempt * 3) # 重試等待時間：3秒, 6秒, 9秒
        
        if response and response.text:
            break

    if not response or not response.text:
        raise RuntimeError(f"所有 Gemini 模型呼叫失敗，最後錯誤: {last_error}")

    script = re.sub(r'[\*\#\-\_]', '', response.text).strip()
    return script
