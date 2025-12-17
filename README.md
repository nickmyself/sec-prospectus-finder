SEC Prospectus Finder (Streamlit)

快速说明

1. 安装依赖：

```bash
python -m pip install -r "c:/Recent SEC Checker/requirements.txt"
```

2. 运行应用：

```bash
streamlit run "c:/Recent SEC Checker/app.py"
```

重要说明

- 请在 `app.py` 中把 `HEADERS["User-Agent"]` 改为包含你邮箱或联系信息的字符串，遵守 SEC 的访问规则。
- 默认只在 recent filings 中查找可能包含 prospectus 的表单（S-1/S-3/F-1/424B/497 等）。
- 如果需要自动下载原文或更深历史检索，请告诉我，我可以继续扩展。
