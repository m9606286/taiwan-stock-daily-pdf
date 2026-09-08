def create_pdf(news_titles, ai_analysis):
    """生成高級感手機專用 PDF（字型防亂碼修正版）"""
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    today_str = datetime.datetime.now(tz_tw).strftime("%Y/%m/%d")
    cleaned_news = [clean_markdown_text(title) for title in news_titles]
    
    news_li_html = "".join([f'<div class="news-item"><span class="dot"></span>{title}</div>' for title in cleaned_news])
    formatted_analysis_html = format_analysis_html(ai_analysis)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <meta charset="utf-8">
        <style>
            @page {{
                size: 108mm 192mm;
                margin: 6mm;
                background-color: #0b1329;
            }}
            * {{ box-sizing: border-box; }}
            
            /* 強制指定 Ubuntu Linux 內建的 Noto Sans CJK SC/TC 中文字型 */
            body {{
                font-family: "WenQuanYi Micro Hei", "Noto Sans CJK TC", sans-serif;
                margin: 0;
                padding: 0;
                color: #e2e8f0;
                font-size: 10pt;
                line-height: 1.65;
                background-color: #0b1329;
            }}

            .hero-card {{
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border-radius: 12px;
                padding: 14px 16px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                margin-bottom: 10px;
            }}
            .hero-title {{
                font-size: 15pt;
                font-weight: 800;
                margin: 0 0 6px 0;
                color: #ffffff;
                letter-spacing: 0.5px;
            }}
            .tag-group {{ margin-top: 4px; }}
            .badge {{
                display: inline-block;
                background: rgba(16, 185, 129, 0.15);
                color: #34d399;
                font-weight: 700;
                font-size: 8pt;
                padding: 2px 8px;
                border-radius: 6px;
                border: 1px solid rgba(52, 211, 153, 0.3);
                margin-right: 4px;
            }}
            .badge-date {{
                display: inline-block;
                background: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                font-weight: 700;
                font-size: 8pt;
                padding: 2px 8px;
                border-radius: 6px;
                border: 1px solid rgba(56, 189, 248, 0.3);
            }}

            .metrics-grid {{
                display: table;
                width: 100%;
                table-layout: fixed;
                border-spacing: 6px;
                margin-left: -6px;
                margin-right: -6px;
                margin-bottom: 8px;
            }}
            .metric-row {{ display: table-row; }}
            .metric-col {{ display: table-cell; width: 50%; }}
            
            .metric-card {{
                background: rgba(30, 41, 59, 0.5);
                border-radius: 10px;
                padding: 8px;
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.05);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            }}
            .card-up {{ border-top: 2.5px solid #fb7185; }}
            .card-flat {{ border-top: 2.5px solid #38bdf8; }}

            .metric-label {{ font-size: 7.5pt; color: #94a3b8; font-weight: 600; }}
            .metric-value {{ font-size: 10pt; font-weight: 800; margin-top: 2px; color: #f8fafc; }}

            .section-panel {{
                background: rgba(15, 23, 42, 0.6);
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 10px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            
            .section-title {{
                color: #ffffff;
                font-size: 10.5pt;
                font-weight: 800;
                padding-bottom: 6px;
                margin-bottom: 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .news-item {{
                background: rgba(30, 41, 59, 0.4);
                padding: 7px 10px;
                border-radius: 6px;
                margin-bottom: 6px;
                color: #cbd5e1;
                font-size: 9pt;
                font-weight: 500;
            }}
            .dot {{
                display: inline-block;
                width: 5px;
                height: 5px;
                background-color: #38bdf8;
                border-radius: 50%;
                margin-right: 6px;
                vertical-align: middle;
            }}

            .block-title {{
                font-size: 10pt;
                font-weight: 800;
                color: #38bdf8;
                margin-top: 10px;
                margin-bottom: 4px;
            }}
            .block-text {{
                color: #94a3b8;
                font-size: 9pt;
                line-height: 1.6;
                margin: 0 0 6px 0;
            }}

            .callout-box {{
                background: rgba(234, 179, 8, 0.1);
                border: 1px solid rgba(234, 179, 8, 0.3);
                border-radius: 8px;
                padding: 8px 10px;
                color: #fef08a;
                font-size: 8.5pt;
                font-weight: 600;
                margin-top: 8px;
            }}

            .footer {{
                text-align: center;
                font-size: 7.5pt;
                color: #475569;
                margin-top: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="hero-card">
            <div class="hero-title">盤前極速總研</div>
            <div class="tag-group">
                <span class="badge">AI 智算</span>
                <span class="badge-date">{today_str}</span>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-row">
                <div class="metric-col">
                    <div class="metric-card card-up">
                        <div class="metric-label">美股四大指數</div>
                        <div class="metric-value">多頭回升</div>
                    </div>
                </div>
                <div class="metric-col">
                    <div class="metric-card card-flat">
                        <div class="metric-label">台指期夜盤</div>
                        <div class="metric-value">高檔震盪</div>
                    </div>
                </div>
            </div>
            <div class="metric-row">
                <div class="metric-col">
                    <div class="metric-card card-up">
                        <div class="metric-label">台積電 ADR</div>
                        <div class="metric-value">強勢帶勁</div>
                    </div>
                </div>
                <div class="metric-col">
                    <div class="metric-card card-flat">
                        <div class="metric-label">新台幣匯率</div>
                        <div class="metric-value">資金觀察</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="section-panel">
            <div class="section-title">📡 經濟日報精選頭條</div>
            {news_li_html}
        </div>

        <div class="section-panel">
            <div class="section-title">🧠 Gemini 深度策略解讀</div>
            {formatted_analysis_html}
        </div>

        <div class="footer">
            GitHub Actions 自動化生成｜投資有風險，僅供參考
        </div>
    </body>
    </html>
    """
    pdf_path = "taiwan_stock_daily.pdf"
    
    # 關鍵：指定 encoding='utf-8' 寫入 HTML 快照
    HTML(string=html_content, encoding='utf-8').write_pdf(pdf_path)
    return pdf_path
