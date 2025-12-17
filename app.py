import re
import time
import json
import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from urllib.parse import urljoin

USER_AGENT = os.environ.get("SEC_USER_AGENT", "zhaojw42@gmail.com - prospectus-finder (streamlit demo)")
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*"
}

# Only consider these specific form tokens (user-requested)
ALLOWED_FORM_TOKENS = [
    "S-1",
    "F-1",
    "S-1/A",
    "F-1/A",
    "S-1MEF",
    "F-1MEF",
    "EFFECT",
    "424B4",
    "424B5",
    "424B3",
    "S-3",
    "F-3",
    "F-10",
    "S-3MEF",
    "F-3MEF",
    "S-3ASR",
    "F-3ASR",
]

SEC_TICKERS_JSON = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik_padded}.json"

st.set_page_config(page_title="SEC Prospectus Finder", layout="wide")
# Inject CSS to ensure readability in dark Streamlit themes (force light text on dark backgrounds)
st.markdown(
        """
        <style>
        /* Force readable light text for app content and headers */
        .stApp, body, header, main, .block-container, .element-container, h1, h2, h3, h4, h5, h6, p, div, span, th, td, label {
            color: #ffffff !important;
        }
        /* Ensure form controls (textareas, inputs) use readable foreground/background */
        textarea, input, .stTextArea textarea, .stTextInput input {
            color: #fff !important;
            background: #222425 !important;
        }
        /* Buttons */
        .stButton>button { color: #fff !important; }
        /* Links */
        a { color: #6ec1ff !important; }
        /* Table styling: dark body text, but make header dark-on-light for readability */
        table.prospectus td { color: #fff !important; }
        table.prospectus th { color: #111 !important; background: #f6f6f6 !important; }
        /* Make Streamlit labels readable */
        .stMarkdown, .css-1adrfps, .css-1r6slb0 { color: #fff !important; }
        </style>
        """,
        unsafe_allow_html=True,
)

def load_ticker_map():
    try:
        r = requests.get(SEC_TICKERS_JSON, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        mapping = {}
        for v in data.values():
            mapping[v["ticker"].upper()] = str(v["cik_str"])
        return mapping
    except Exception:
        return {}

def to_cik(ticker, ticker_map):
    t = ticker.strip().upper()
    if not t:
        return None
    return ticker_map.get(t)

def pad_cik(cik):
    return str(cik).zfill(10)

def build_filing_index_url(cik, accession):
    accession_nodash = accession.replace("-", "")
    try:
        cik_int = int(cik)
    except Exception:
        cik_int = cik
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{accession}-index.html"

def looks_like_prospectus(form, description, primary_doc):
    """Strictly match form types the user cares about.

    We only consider filings whose `form` field matches one of
    `ALLOWED_FORM_TOKENS` (case-insensitive, prefix or containment).
    """
    form_up = (form or "").upper()
    for token in ALLOWED_FORM_TOKENS:
        tok = token.upper()
        if form_up.startswith(tok) or tok in form_up:
            return True
    return False


def collect_matches_from_submissions(submissions_json, days=365):
    """Return a list of filings from submissions_json within the past `days`
    that match the allowed form tokens.
    """
    matches = []
    recent = submissions_json.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    for i, form in enumerate(forms):
        try:
            fdate = datetime.strptime(dates[i], "%Y-%m-%d").date()
        except Exception:
            continue
        if fdate < cutoff:
            continue
        if looks_like_prospectus(form, descriptions[i] if i < len(descriptions) else "", primary_docs[i] if i < len(primary_docs) else ""):
            matches.append({
                "form": form,
                "filingDate": dates[i] if i < len(dates) else None,
                "accessionNumber": accessions[i] if i < len(accessions) else None,
                "primaryDocument": primary_docs[i] if i < len(primary_docs) else None,
                "description": descriptions[i] if i < len(descriptions) else ""
            })
    return matches

def find_recent_prospectus_from_submissions(submissions_json):
    filings = []
    recent = submissions_json.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    for i, form in enumerate(forms):
        filing = {
            "form": form,
            "filingDate": dates[i] if i < len(dates) else None,
            "accessionNumber": accessions[i] if i < len(accessions) else None,
            "primaryDocument": primary_docs[i] if i < len(primary_docs) else None,
            "description": descriptions[i] if i < len(descriptions) else ""
        }
        filings.append(filing)
    for f in filings:
        if looks_like_prospectus(f["form"], f.get("description"), f.get("primaryDocument")):
            return f
    return None

def query_for_ticker(ticker, ticker_map, pause=0.5):
    """Return a list of result dicts for the given ticker. Each dict is
    one filing (or a single row with status if none found / error).
    """
    cik = to_cik(ticker, ticker_map)
    if not cik:
        return [{"ticker": ticker, "error": "CIK not found"}]
    cik_p = pad_cik(cik)
    url = SUBMISSIONS_TEMPLATE.format(cik_padded=cik_p)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        candidates = collect_matches_from_submissions(data, days=365)
        time.sleep(pause)
        if not candidates:
            return [{"ticker": ticker, "cik": cik, "status": "no_prospectus_found"}]
        out = []
        for candidate in candidates:
            accession = candidate.get("accessionNumber")
            link = build_filing_index_url(cik, accession) if accession else ""
            out.append({
                "ticker": ticker,
                "cik": cik,
                "form": candidate.get("form"),
                "filingDate": candidate.get("filingDate"),
                "accession": accession,
                "primaryDocument": candidate.get("primaryDocument"),
                "description": candidate.get("description"),
                "link": link,
                "status": "found"
            })
        return out
    except Exception as e:
        return [{"ticker": ticker, "cik": cik, "error": str(e)}]

# Streamlit UI
st.title("SEC Prospectus Finder")
st.markdown("输入多行 ticker（每行一个），点击 `查找`。结果将在表格中展示，并提供 CSV/JSON 下载。")

col1, col2 = st.columns([2,1])

with col1:
    tickers_text = st.text_area("Tickers 列表", value="BDRX\nIMG\nKYTX\nMIST\nARBB\nIMNM\nYCBD\nALBT\nQIPT", height=180)
    submit_btn = st.button("查找")
with col2:
    opt_download_docs = st.checkbox("自动下载原文 (可能较大)", value=False)
    opt_output_json = st.checkbox("提供 JSON 输出", value=True)
    concurrency = st.slider("请求间隔 (秒)", min_value=0.1, max_value=2.0, value=0.4, step=0.1)
    st.write("注意：请求需带 User-Agent，且请遵守 SEC 速率限制。")

if submit_btn:
    raw = tickers_text.strip()
    tickers = [t.strip().upper() for t in re.split(r"[,\n;]+", raw) if t.strip()]
    if not tickers:
        st.warning("未检测到有效 ticker")
    else:
        with st.spinner(f"加载 company ticker map 并查询 {len(tickers)} 个 ticker..."):
            ticker_map = load_ticker_map()
            results = []
            for tk in tickers:
                res_list = query_for_ticker(tk, ticker_map, pause=concurrency)
                if isinstance(res_list, list):
                    results.extend(res_list)
                else:
                    results.append(res_list)
            df = pd.DataFrame(results)
            def format_link(r):
                if r.get("status") == "found":
                    return f"[打开]({r.get('link')})"
                return ""
            if not df.empty:
                df_display = df.copy()
                df_display["link"] = df_display.apply(format_link, axis=1)
                # sort and merge ticker column visually: show ticker only on first row per group
                df_display = df_display.sort_values(by=["ticker", "filingDate"], ascending=[True, False])
                df_display["ticker_display"] = df_display["ticker"].astype(str)
                df_display.loc[df_display["ticker_display"].duplicated(), "ticker_display"] = ""
                st.markdown("### 结果")
                # build HTML table with rowspan on ticker to visually merge ticker cells
                df_full = df_display.drop(columns=["ticker_display"]).copy()
                df_full = df_full.reset_index(drop=True)
                html = []
                html.append("<style>table.prospectus {border-collapse:collapse; width:100%;} table.prospectus th, table.prospectus td {border:1px solid #ddd; padding:8px; text-align:left;} table.prospectus th {background:#f6f6f6;}</style>")
                html.append("<table class=\"prospectus\">")
                # header
                html.append("<tr><th style='width:12%'>Ticker</th><th style='width:10%'>CIK</th><th style='width:10%'>Form</th><th style='width:12%'>Filing Date</th><th style='width:10%'>Accession</th><th>Description</th><th style='width:8%'>Link</th></tr>")
                # group by ticker
                for ticker, group in df_full.groupby('ticker'):
                    rows = group.to_dict('records')
                    rowspan = len(rows)
                    for i, row in enumerate(rows):
                        html.append('<tr>')
                        if i == 0:
                            html.append(f"<td rowspan=\"{rowspan}\">{ticker}</td>")
                        # CIK
                        html.append(f"<td>{row.get('cik','')}</td>")
                        html.append(f"<td>{row.get('form','')}</td>")
                        html.append(f"<td>{row.get('filingDate','')}</td>")
                        html.append(f"<td>{row.get('accession','')}</td>")
                        descr_raw = row.get('description', '')
                        if pd.isna(descr_raw):
                            descr = ''
                        else:
                            descr = str(descr_raw)
                        descr = descr.replace('\n',' ').replace('<','&lt;').replace('>','&gt;')
                        html.append(f"<td>{descr}</td>")
                        link_html = f"<a href=\"{row.get('link','')}\" target=\"_blank\">Open</a>" if row.get('link') else ''
                        html.append(f"<td>{link_html}</td>")
                        html.append('</tr>')
                html.append('</table>')
                st.markdown('\n'.join(html), unsafe_allow_html=True)
                # prepare downloads (use the full data, sorted)
                csv = df_full.to_csv(index=False)
                if opt_output_json:
                    json_data = df_display.drop(columns=["ticker_display"]).to_json(orient="records", force_ascii=False)
                else:
                    json_data = None
                st.download_button("下载 CSV", data=csv, file_name="prospectus_results.csv", mime="text/csv")
                if json_data:
                    st.download_button("下载 JSON", data=json_data, file_name="prospectus_results.json", mime="application/json")
            else:
                st.info("没有结果。")
