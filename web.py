from __future__ import annotations

from datetime import datetime
import hashlib
import os
import re

import pandas as pd
import streamlit as st

from bizscope.gemini import DEFAULT_MODEL, explain_calculation, request_analysis_plan
from bizscope.visualization import AGGREGATIONS, build_chart, get_field_types, suggest_calculations, suggest_charts
from bizscope.data import (
    interpret_question,
    profile_table,
    read_uploaded_tables,
    run_planned_analysis,
    summarize_table,
)


st.set_page_config(page_title="BizScope", page_icon="◉", layout="wide", initial_sidebar_state="expanded")

COLORS = {
    "midnight": "#142A32",
    "teal": "#236C67",
    "lime": "#C7E66B",
    "paper": "#F6F8F7",
    "slate": "#71817F",
    "white": "#FFFFFF",
    "line": "#DCE5E1",
}

st.markdown(
    f"""
    <style>
    .stApp, [data-testid="stAppViewContainer"] {{
        background: radial-gradient(ellipse at 8% 0%, #EAF2ED 0, transparent 36%), {COLORS['paper']};
        color: {COLORS['midnight']}; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    [data-testid="stMainBlockContainer"] {{ max-width: 1480px; padding-top: 1.8rem; padding-bottom: 4rem; }}
    [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
    [data-testid="stMain"] p, [data-testid="stMain"] label,
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] {{ color: {COLORS['midnight']} !important; }}
    [data-testid="stMain"] h2 {{ font-size: 1.45rem; letter-spacing: -.025em; margin: .35rem 0 .5rem; }}
    [data-testid="stMain"] h3 {{ font-size: 1.08rem; letter-spacing: -.015em; margin: .8rem 0 .35rem; }}
    [data-testid="stMain"] p {{ line-height: 1.55; }}
    [data-testid="stSidebar"] {{ background: {COLORS['midnight']};
        --background-color: {COLORS['midnight']}; --secondary-background-color: #203B43;
        --text-color: #F3F6F4; }}
    [data-testid="stSidebar"] * {{ color: #F3F6F4; }}
    [data-testid="stMetric"] {{ background: linear-gradient(145deg, #FFFFFF, #FBFCFB); border: 1px solid {COLORS['line']};
        padding: 17px 18px; border-radius: 17px; box-shadow: 0 5px 18px rgba(20,42,50,.035); min-height: 104px; }}
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{ color: {COLORS['midnight']} !important; }}
     [data-testid="stTabs"] [role="tablist"] {{ gap: 1.2rem !important; border-bottom: 1px solid {COLORS['line']}; }}
    [data-testid="stTabs"] button[role="tab"] {{ border-radius: 10px 10px 0 0; padding: .75rem .65rem;
        margin-right: .35rem !important; min-width: max-content; white-space: nowrap;
        color: #344F50; font-size: 10rem; font-weight: 750; letter-spacing: .005em;
        transition: color .15s ease, background .15s ease; }}
    [data-testid="stTabs"] button[role="tab"]:hover {{ background: #EAF1ED; color: {COLORS['midnight']}; }}
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{ color: {COLORS['teal']}; font-weight: 800 !important; }}
    div.stButton > button {{ border-radius: 12px; border: 1px solid #CFDCD6; background: #FFFFFF;
        color: {COLORS['midnight']}; min-height: 42px; transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; }}
    div.stButton > button:hover {{ border-color: {COLORS['teal']}; color: {COLORS['teal']};
        box-shadow: 0 5px 16px rgba(35,108,103,.10); transform: translateY(-1px); }}
    div.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button {{
        background: {COLORS['teal']} !important; color: #FFFFFF !important; border: 0 !important;
        font-weight: 650; box-shadow: 0 5px 14px rgba(35,108,103,.17); }}
    div.stButton > button[kind="primary"]:hover {{ background: #195954 !important; color: #FFFFFF !important; }}
    [data-testid="stDataFrame"] {{ border: 1px solid {COLORS['line']}; border-radius: 14px; overflow: hidden; }}
    [data-testid="stAlert"] {{ border-radius: 14px; border: 1px solid rgba(35,108,103,.10); }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ background: rgba(255,255,255,.82);
        border-color: {COLORS['line']} !important; border-radius: 16px; box-shadow: 0 5px 18px rgba(20,42,50,.035); }}
    [data-testid="stChatMessage"] {{ background: rgba(255,255,255,.83); border: 1px solid {COLORS['line']};
        border-radius: 16px; padding: 1rem 1.15rem; box-shadow: 0 4px 16px rgba(20,42,50,.035); }}
    [data-testid="stChatInput"] {{ border-radius: 16px; }}
    [data-testid="stChatInput"] textarea {{ background: #FFFFFF; border-color: #D6E0DB; border-radius: 14px; }}
    [data-testid="stFileUploaderDropzone"] {{ background: rgba(255,255,255,.85); border: 1px dashed #AABDB5; border-radius: 16px; }}
    [data-testid="stFileUploaderDropzone"]:hover {{ border-color: {COLORS['teal']}; background: #FFFFFF; }}
    [data-testid="stMain"] a {{ color: {COLORS['teal']}; }}
    [data-testid="stMain"] [data-baseweb="input"] > div,
    [data-testid="stMain"] [data-baseweb="textarea"] > div,
    [data-testid="stMain"] [data-baseweb="select"] > div {{ background: #FFFFFF; border-color: #D6E0DB; border-radius: 11px; }}
    [data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"],
    [data-testid="stSidebar"] [data-baseweb="input"] > div {{
        background: #203B43 !important; background-color: #203B43 !important;
        border-color: #5C767B !important; color: #FFFFFF !important;
    }}
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-testid="stExpander"] details,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary,
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{
        background: #203B43 !important; border-color: #5C767B !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"] {{
        color: #FFFFFF !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg {{ fill: #D7E4E0 !important; }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary * {{
        background-color: transparent !important; color: #FFFFFF !important;
    }}
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"],
    [data-testid="stSidebar"] [data-baseweb="select"] span {{ color: #FFFFFF !important; }}
    [data-testid="stSidebar"] input::placeholder {{ color: #B7C7C3 !important; }}
    [data-baseweb="popover"] [role="listbox"] {{ background: #FFFFFF !important; }}
    [data-baseweb="popover"] [role="option"] {{ color: {COLORS['midnight']} !important; }}
    .biz-hero {{ background: radial-gradient(circle at 84% 42%, #28565A 0, #1B3C43 27%, {COLORS['midnight']} 67%);
        border-radius: 24px; padding: 34px 38px; margin: 2px 0 25px 0; color: #F3F6F4;
        display: flex; align-items: center; justify-content: space-between; gap: 24px; overflow: hidden; }}
    .biz-hero-copy {{ position: relative; z-index: 1; max-width: 720px; }}
    .biz-hero h1 {{ color: #FFFFFF !important; margin: 0 0 9px 0; font-size: clamp(2rem, 3vw, 2.65rem); letter-spacing: -.04em; }}
    .biz-hero p {{ color: #D5E2DD !important; margin: 0; font-size: 1rem; }}
    .biz-hero-art {{ flex: 0 0 210px; height: 160px; display: grid; place-items: center;
        border: 1px solid rgba(200,230,107,.24); border-radius: 28px;
        background: linear-gradient(145deg, rgba(255,255,255,.075), rgba(255,255,255,.02)); }}
    .biz-hero-art svg {{ width: 190px; height: 145px; overflow: visible; }}
    @media (max-width: 720px) {{ .biz-hero {{ padding: 24px; }} .biz-hero-art {{ display: none; }} }}
    .biz-pill {{ display: inline-block; color: {COLORS['midnight']}; background: {COLORS['lime']};
        padding: 5px 11px; border-radius: 100px; font-size: .72rem; font-weight: 750;
        letter-spacing: .04em; margin-bottom: 12px; }}
    .biz-brand {{ display: flex; align-items: center; gap: 12px; margin: 8px 0 5px; }}
    .biz-brand-mark {{ width: 42px; height: 42px; display: grid; place-items: center; flex: 0 0 42px;
        border-radius: 13px; background: #203B43; border: 1px solid #47666A; }}
    .biz-brand-mark svg {{ width: 25px; height: 25px; }}
    .biz-brand-name {{ color: #FFFFFF; font-size: 1.8rem; line-height: 1; font-weight: 750;
        letter-spacing: -.045em; }}
    .biz-guide {{ margin-top: 24px; padding: 17px 16px 15px; border: 1px solid #35555A;
        border-radius: 15px; background: linear-gradient(145deg, #203D44, #1A343B); }}
    .biz-guide-title {{ color: #C7E66B; font-size: .76rem; font-weight: 750;
        letter-spacing: .09em; margin-bottom: 12px; }}
    .biz-guide-row {{ display: flex; align-items: flex-start; gap: 10px; margin: 11px 0; }}
    .biz-guide-step {{ display: grid; place-items: center; flex: 0 0 24px; height: 24px;
        border-radius: 8px; background: #C7E66B; color: #142A32; font-size: .76rem; font-weight: 800; }}
    .biz-guide-text {{ color: #F3F6F4; font-size: .88rem; line-height: 1.35; }}
    .biz-guide-text span {{ display: block; margin-top: 2px; color: #B7C7C3; font-size: .76rem; }}
    .biz-subtle {{ color: {COLORS['slate']}; }}
    @media (max-width: 720px) {{ [data-testid="stMainBlockContainer"] {{ padding: 1.1rem 1rem 3rem; }}
        .biz-hero {{ padding: 24px; }} [data-testid="stTabs"] [role="tablist"] {{ gap: .20rem !important; overflow-x: auto; }}
       [data-testid="stTabs"] button[role="tab"] {{ padding: .6rem .55rem; font-size: 1.05rem !important; }} }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _sample_csv() -> bytes:
    sample = pd.DataFrame(
        [
            ["T-1001", "2026-01-04", "Notebook", "North", 12, 4.50, 54.00, 18.00],
            ["T-1002", "2026-01-08", "Pen set", "South", 20, 3.00, 60.00, 24.00],
            ["T-1003", "2026-01-14", "Desk lamp", "East", 5, 24.00, 120.00, 35.00],
            ["T-1004", "2026-01-22", "Notebook", "West", 18, 4.50, 81.00, 27.00],
            ["T-1005", "2026-02-02", "Pen set", "North", 25, 3.00, 75.00, 30.00],
            ["T-1006", "2026-02-11", "Desk lamp", "South", 7, 24.00, 168.00, 49.00],
            ["T-1007", "2026-02-19", "Notebook", "East", 15, 4.50, 67.50, 22.50],
            ["T-1008", "2026-02-25", "Pen set", "West", 16, 3.00, 48.00, 19.20],
            ["T-1009", "2026-03-03", "Desk lamp", "North", 4, 24.00, 96.00, 28.00],
            ["T-1010", "2026-03-10", "Notebook", "South", 22, 4.50, 99.00, 33.00],
            ["T-1011", "2026-03-18", "Pen set", "East", 30, 3.00, 90.00, 36.00],
            ["T-1012", "2026-03-27", "Desk lamp", "West", 6, 24.00, 144.00, 42.00],
        ],
        columns=["Transaction_ID", "Order_Date", "Product", "Region", "Quantity", "Unit_Price", "Revenue", "Profit"],
    )
    return sample.to_csv(index=False).encode("utf-8")


def _report_text(source_name: str, frame: pd.DataFrame, analysis: dict | None) -> str:
    columns_csv = profile_table(frame).to_csv(index=False).strip()
    lines = [
        "# BizScope data summary",
        "",
        f"**Table:** {source_name}",
        f"**Created:** {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        f"**Size:** {len(frame):,} rows × {len(frame.columns):,} columns",
        f"**Missing cells:** {int(frame.isna().sum().sum()):,}",
        f"**Duplicate rows:** {int(frame.duplicated().sum()):,}",
        "",
        "## Column profile",
        "",
        "```csv",
        columns_csv,
        "```",
    ]
    if isinstance(analysis, dict):
        latest_result = analysis.get("result")
        if isinstance(latest_result, pd.DataFrame):
            lines.extend(["", "## Latest result", "", str(analysis.get("description", "")), "", "```", latest_result.to_string(index=False), "```"])
        elif isinstance(analysis.get("answer"), dict):
            response_text = _answer_text(analysis["answer"])
            if response_text:
                lines.extend(["", "## Latest response", "", response_text])
    lines.extend(["", "## Summary statistics", "", "```", summarize_table(frame).to_string(), "```", ""])
    return "\n".join(lines)


def _prepare_table(
    frame: pd.DataFrame,
    *,
    trim_text: bool,
    normalize_text: str,
    drop_empty: bool,
    drop_duplicates: bool,
    fill_missing: str,
    rename_map: dict,
    drop_columns: list,
    convert_column: str | None,
    convert_type: str,
    replace_column: str | None,
    find_value: str,
    replace_value: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Apply explicitly selected, reversible preparation steps to a copy."""
    result = frame.copy()
    notes: list[str] = []
    before_rows, before_missing = len(result), int(result.isna().sum().sum())

    if trim_text:
        for col in result.select_dtypes(include=["object", "string"]).columns:
            result[col] = result[col].map(lambda value: value.strip() if isinstance(value, str) else value)
        notes.append("Trimmed extra spaces around text.")

    if normalize_text != "Keep as-is":
        for col in result.select_dtypes(include=["object", "string"]).columns:
            if normalize_text == "lowercase":
                result[col] = result[col].map(lambda value: value.lower() if isinstance(value, str) else value)
            elif normalize_text == "UPPERCASE":
                result[col] = result[col].map(lambda value: value.upper() if isinstance(value, str) else value)
            else:
                result[col] = result[col].map(lambda value: value.title() if isinstance(value, str) else value)
        notes.append(f"Changed text to {normalize_text}.")

    if replace_column and find_value:
        series = result[replace_column]
        result[replace_column] = series.map(
            lambda value: replace_value if isinstance(value, str) and value == find_value else value
        )
        notes.append(f"Replaced matching values in {replace_column}.")

    if drop_empty:
        old = len(result)
        result = result.dropna(how="all")
        notes.append(f"Removed {old - len(result):,} completely blank row(s).")
    if drop_duplicates:
        old = len(result)
        result = result.drop_duplicates()
        notes.append(f"Removed {old - len(result):,} exact duplicate row(s).")

    if fill_missing == "Numbers: median; text: most common":
        for col in result.select_dtypes(include="number").columns:
            if result[col].isna().any() and result[col].notna().any():
                result[col] = result[col].fillna(result[col].median())
        for col in result.select_dtypes(include=["object", "string", "category"]).columns:
            modes = result[col].mode(dropna=True)
            if result[col].isna().any() and not modes.empty:
                result[col] = result[col].fillna(modes.iloc[0])
        notes.append("Filled blank numbers with each column's median and blank text with its most common value.")
    elif fill_missing == "Numbers: zero; text: most common":
        for col in result.select_dtypes(include="number").columns:
            if result[col].isna().any():
                result[col] = result[col].fillna(0)
        for col in result.select_dtypes(include=["object", "string", "category"]).columns:
            modes = result[col].mode(dropna=True)
            if result[col].isna().any() and not modes.empty:
                result[col] = result[col].fillna(modes.iloc[0])
        notes.append("Filled blank numbers with 0 and blank text with its most common value. Check that zero is meaningful for your data.")

    if convert_column:
        if convert_type == "Number":
            raw = result[convert_column].astype("string").str.strip()
            raw = raw.str.replace(r"^\((.*)\)$", r"-\1", regex=True).str.replace(r"[^0-9eE.+-]", "", regex=True)
            converted = pd.to_numeric(raw, errors="coerce")
        elif convert_type == "Date/time":
            converted = pd.to_datetime(result[convert_column], errors="coerce")
        else:
            converted = result[convert_column].astype("string")
        result[convert_column] = converted
        new_missing = int(result[convert_column].isna().sum())
        notes.append(f"Converted {convert_column} to {convert_type.lower()}; {new_missing:,} value(s) are now blank/unreadable.")

    if drop_columns:
        result = result.drop(columns=drop_columns)
        notes.append(f"Removed {len(drop_columns)} selected column(s).")
    if rename_map:
        result = result.rename(columns=rename_map)
        notes.append(f"Renamed {len(rename_map)} column(s).")

    notes.append(f"Final copy: {len(result):,} rows, {len(result.columns):,} columns; {int(result.isna().sum().sum()):,} missing cells (started with {before_rows:,} rows and {before_missing:,} missing cells).")
    return result, notes


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        return ""


def _data_improvement_suggestions(
    frame: pd.DataFrame,
    result: pd.DataFrame | None = None,
    dimension: str | None = None,
    metric: str | None = None,
    operation: str | None = None,
) -> list[str]:
    """Create cautious next steps from measurable facts in the selected table."""
    suggestions: list[str] = []
    missing_total = int(frame.isna().sum().sum())
    if missing_total:
        affected = frame.isna().sum().sort_values(ascending=False)
        affected = affected[affected > 0]
        fields = ", ".join(str(name) for name in affected.index[:3])
        suggestions.append(f"Review the {missing_total:,} blank value(s), especially in {fields}, before relying on totals or comparisons.")

    duplicates = int(frame.duplicated().sum())
    if duplicates:
        suggestions.append(f"Check the {duplicates:,} repeated row(s) to confirm whether they are duplicate records or valid repeated transactions.")

    revenue_col = _numeric_column_named(frame, ("revenue", "sales", "turnover"))
    profit_col = _numeric_column_named(frame, ("net profit", "gross profit", "profit"))
    if profit_col is not None and "margin" in str(profit_col).lower():
        profit_col = None
    if revenue_col is not None and profit_col is not None:
        revenue = pd.to_numeric(frame[revenue_col], errors="coerce").sum()
        profit = pd.to_numeric(frame[profit_col], errors="coerce").sum()
        if revenue > 0:
            margin = profit / revenue * 100
            if margin < 0:
                suggestions.append(f"Recorded profit is below zero overall ({margin:.1f}% of recorded sales). Review costs, discounts, and entries before changing prices.")
            elif margin < 10:
                suggestions.append(f"Recorded profit is {margin:.1f}% of recorded sales. Review cost and discount entries to understand the narrow recorded margin.")

    if result is not None and dimension is not None and dimension in result.columns:
        dimension_is_time = any(word in str(dimension).lower() for word in ("date", "time", "year", "month", "period"))
        if "Result" in result.columns and len(result) > 1 and str(operation).lower() in ("sum", "count", "distinct_count") and not dimension_is_time:
            positive = pd.to_numeric(result["Result"], errors="coerce").clip(lower=0)
            total = float(positive.sum())
            if total > 0:
                leader_index = positive.idxmax()
                share = float(positive.loc[leader_index] / total)
                if share >= 0.6:
                    leader_name = result.loc[leader_index, dimension]
                    suggestions.append(f"{leader_name} represents {share:.0%} of this total. Check whether this concentration is expected.")

    metric_name = str(metric or "").lower().replace("_", " ")
    dimension_name = str(dimension or "").lower().replace("_", " ")
    if any(word in dimension_name for word in ("product", "item")) and any(word in dimension_name for word in (" id", " code", " sku")):
        product_label = _column_named(frame, ("product name", "item name", "product description", "item description"))
        if product_label is None:
            suggestions.append(f"This table identifies items with {dimension}. Join a product catalog on that ID to show product names.")
    if any(word in metric_name for word in ("price", "msrp", "cost")) and any(word in dimension_name for word in ("brand", "product", "item")):
        if _numeric_column_named(frame, ("quantity", "units", "sold")) is not None or profit_col is not None:
            suggestions.append("Before changing prices, compare these average prices with units sold and profit by brand or product.")

    stock_col = _numeric_column_named(frame, ("on hand", "inventory quantity", "stock"))
    if stock_col is not None and pd.api.types.is_numeric_dtype(frame[stock_col]):
        low_stock = int((frame[stock_col] <= 0).sum())
        if low_stock:
            suggestions.append(f"{low_stock:,} row(s) have zero or negative {stock_col}. Check availability and whether these entries need correction.")
        elif _numeric_column_named(frame, ("quantity sold", "units sold", "sales quantity")) is not None:
            suggestions.append("Compare on-hand stock with units sold over the same period to identify products that may need a closer restock review.")

    if metric_name.isdigit() and any(str(col).strip().isdigit() and len(str(col).strip()) == 4 for col in frame.columns):
        suggestions.append("The table contains multiple years; compare the year-to-year trend to see whether country rankings are changing.")

    return list(dict.fromkeys(suggestions))[:3]


def _suggest_visualizations(frame: pd.DataFrame) -> list[dict]:
    """Backwards-compatible wrapper for dataset-based chart recommendations."""
    return suggest_charts(frame)


def _local_answer(question: str, frame: pd.DataFrame) -> tuple[dict, pd.DataFrame | None, str | None]:
    plan = interpret_question(question, frame)
    if not plan:
        q = question.lower()
        if any(word in q for word in ("sales", "sale", "sell", "sells", "sold", "selling")) and any(word in q for word in ("most", "highest", "top", "best", "more")):
            product_fields = [str(col) for col in frame.columns if any(token in str(col).lower().replace("_", " ") for token in ("product", "item", "sku"))]
            available = ", ".join(product_fields[:4]) if product_fields else "no product field"
            return (
                {
                    "answer": "I can't determine which product made the most sales from this table alone.",
                    "finding": f"Found {available}, but no usable sales/revenue or transaction measure to rank them by.",
                    "suggestions": ["Upload transaction-level records with a Transaction_ID, or add numeric Quantity and Sales/Revenue fields. If one row equals one sale, tell me that and I can compare row counts."],
                    "caveat": "A product list by itself cannot show which products sold most.",
                },
                None,
                None,
            )
        numeric_fields = [str(col) for col in frame.columns if not _is_index_artifact(col) and pd.api.types.is_numeric_dtype(frame[col])]
        category_fields = [str(col) for col in frame.columns if pd.api.types.is_object_dtype(frame[col]) or isinstance(frame[col].dtype, pd.CategoricalDtype)]
        if numeric_fields and category_fields:
            finding = f"Available measures: {', '.join(numeric_fields[:6])}. Available categories: {', '.join(category_fields[:6])}."
            suggestions = [f"For example, ask: ‘Compare {numeric_fields[0]} by {category_fields[0]}.’"]
        elif numeric_fields:
            finding = f"Available numeric measures: {', '.join(numeric_fields[:8])}."
            suggestions = [f"Name one of these measures, such as ‘What is the total {numeric_fields[0]}?’"]
        else:
            finding = "This table has no numeric measure that can support the requested calculation."
            suggestions = ["Choose a table with numeric values, or ask me to make a chart from a table that has them."]
        return (
            {
                "answer": "I couldn't safely match that question to one calculation in this table, so I didn't calculate a result.",
                "finding": finding,
                "suggestions": suggestions,
                "caveat": "Please name the measure and, for a comparison, the category you want to compare.",
            },
            None,
            None,
        )

    plan["dimension"] = _human_friendly_group(frame, plan.get("dimension"), question)
    api_plan = {
        **plan,
        "operation": plan["operation"].lower().replace(" ", "_"),
        "sort_order": "lowest" if plan.get("ascending") else "highest",
        "time_grain": "none",
    }
    try:
        result, dimension, description = run_planned_analysis(frame, api_plan)
    except Exception as exc:
        return (
            {"answer": "I couldn't calculate that from the selected table.", "finding": "", "suggestions": ["Try another question using a numeric column and a category."], "caveat": str(exc)},
            None,
            None,
        )

    finding = "The result is calculated from the selected table."
    suggestions = []
    if dimension and not result.empty:
        leader = result.iloc[0]
        direction = "fewest" if plan.get("ascending") else "most"
        if plan.get("count_basis") == "distinct transaction IDs":
            finding = f"{leader[dimension]} has the {direction} transactions: {leader['Result']:,.0f} distinct transaction IDs."
        elif plan.get("count_basis") == "rows":
            finding = f"{leader[dimension]} appears most often in this table: {leader['Result']:,.0f} rows."
            suggestions.append("This is a row count, not confirmed sales. Treat it as sales only if each row represents one sale.")
        elif str(plan.get("operation", "")).lower() == "average" and plan.get("ascending"):
            finding = f"{leader[dimension]} has the lowest average {plan['metric']}: {leader['Result']:,.2f}. I compared brand averages, not individual listings."
        else:
            direction = "lowest" if plan.get("ascending") else "highest"
            finding = f"{leader[dimension]} has the {direction} matching result in this table: {leader['Result']:,.2f}."
        suggestions.append(f"Compare the remaining {dimension} groups to see whether this pattern is consistent.")
    suggestions.extend(_data_improvement_suggestions(frame, result, dimension, plan.get("metric"), plan.get("operation")))
    if not suggestions:
        suggestions.append("Verify the result against its source before acting on it.")
    if plan.get("count_basis") == "distinct transaction IDs":
        answer_text = f"I counted distinct transaction IDs for each {dimension}. This measures transaction frequency, not revenue or units sold."
        caveat = "Use a numeric sales or quantity field if you want to compare sales value or units."
    elif plan.get("count_basis") == "rows":
        answer_text = f"I counted rows for each {dimension}. This can indicate sales frequency only if each row is one sale."
        caveat = "This table has no transaction ID or numeric sales field, so the count may not equal actual sales."
    elif str(plan.get("operation", "")).lower() == "average" and plan.get("ascending"):
        answer_text = f"{leader[dimension]} has the lowest average {plan['metric']} among the groups in this table."
        caveat = "Compared the average listed price for each group. This does not account for differences in model, year, condition, or number of listings."
    else:
        answer_text = f"I calculated {description} using Pandas."
        caveat = "Calculated directly from the selected table."
    return (
        {
            "answer": answer_text,
            "finding": finding,
            "suggestions": suggestions,
            "caveat": caveat,
        },
        result,
        dimension,
    )


def _column_named(frame: pd.DataFrame, words: tuple[str, ...]):
    for word in words:
        for column in frame.columns:
            if word in str(column).lower().replace("_", " "):
                return column
    return None


def _is_index_artifact(column) -> bool:
    return str(column).strip().lower() in {"unnamed: 0", "unnamed 0", "index", "row number"}


def _numeric_column_named(frame: pd.DataFrame, words: tuple[str, ...]):
    for word in words:
        for column in frame.columns:
            if word in str(column).lower().replace("_", " ") and pd.api.types.is_numeric_dtype(frame[column]):
                return column
    return None


def _human_friendly_group(frame: pd.DataFrame, dimension: str | None, question: str = ""):
    if dimension is None:
        return None
    normalized = str(dimension).lower().replace("_", " ")
    q = question.lower().replace("_", " ")
    if any(word in normalized for word in ("product", "item")) and any(word in normalized for word in (" id", " code", " sku")):
        if not any(word in q for word in ("product id", "item id", "sku", "product code")):
            for candidate in frame.columns:
                name = str(candidate).lower().replace("_", " ")
                if any(token in name for token in ("product name", "item name", "product description", "item description", "product title")):
                    if pd.api.types.is_object_dtype(frame[candidate]) or isinstance(frame[candidate].dtype, pd.CategoricalDtype):
                        return candidate
    return dimension


def _data_summary_request(question: str, frame: pd.DataFrame) -> dict | None:
    q = question.lower()
    wants_summary = any(phrase in q for phrase in (
        "summarize", "summary", "overview of the data", "overview of this data",
        "describe this data", "describe the data", "what does this table tell",
        "make the summary",
    ))
    if not wants_summary:
        return None

    profile = profile_table(frame)
    numeric = [str(col) for col in frame.columns if pd.api.types.is_numeric_dtype(frame[col])]
    categorical = [
        str(col) for col in frame.columns
        if pd.api.types.is_object_dtype(frame[col]) or isinstance(frame[col].dtype, pd.CategoricalDtype)
    ]
    date_fields = [str(col) for col in frame.columns if pd.api.types.is_datetime64_any_dtype(frame[col])]
    missing_total = int(frame.isna().sum().sum())
    duplicate_rows = int(frame.duplicated().sum())
    pieces = [f"This table has {len(frame):,} rows and {len(frame.columns):,} columns."]
    if numeric:
        pieces.append(f"Numeric fields: {', '.join(numeric[:8])}.")
    if categorical:
        pieces.append(f"Category or label fields: {', '.join(categorical[:8])}.")
    if date_fields:
        pieces.append(f"Date fields: {', '.join(date_fields[:5])}.")
    if missing_total:
        pieces.append(f"It contains {missing_total:,} blank cells.")
    else:
        pieces.append("No blank cells were detected.")
    if duplicate_rows:
        pieces.append(f"It has {duplicate_rows:,} exact duplicate rows to review.")
    else:
        pieces.append("No exact duplicate rows were detected.")
    suggestions = _data_improvement_suggestions(frame)
    if not suggestions:
        suggestions = ["Ask for a chart or comparison using one of the numeric fields and a category field."]
    return {
        "answer": {
            "answer": " ".join(pieces),
            "finding": "The summary describes the selected table only.",
            "suggestions": suggestions,
            "caveat": "Calculated directly from the selected table using Pandas.",
        },
        "result": profile,
        "table_title": "Column summary",
        "description": "Data summary",
        "mode": "summary",
    }


def _data_insights_request(question: str, frame: pd.DataFrame) -> dict | None:
    q = question.lower()
    wants_insights = any(word in q for word in ("analy", "suggest", "recommend", "insight", "improve", "what stands out"))
    if not wants_insights:
        return None

    numeric = [col for col in frame.columns if not _is_index_artifact(col) and pd.api.types.is_numeric_dtype(frame[col])]
    revenue_col = _numeric_column_named(frame, ("revenue", "sales", "turnover", "amount"))
    profit_col = _numeric_column_named(frame, ("profit", "gross profit", "net profit"))
    quantity_col = _numeric_column_named(frame, ("quantity", "units sold", "units", "volume"))
    dimension = _column_named(
        frame,
        ("product name", "product", "item name", "item", "category", "brand", "region", "store", "customer", "country"),
    )
    findings: list[str] = [
        f"I reviewed {len(frame):,} rows and {len(frame.columns):,} fields in the selected table."
    ]
    result = None
    result_dimension = None
    metric = None

    if revenue_col is not None:
        metric = revenue_col
        revenue_total = pd.to_numeric(frame[revenue_col], errors="coerce").sum()
        findings.append(f"Recorded {revenue_col} totals {revenue_total:,.2f}.")
        if profit_col is not None and revenue_total > 0:
            profit_total = pd.to_numeric(frame[profit_col], errors="coerce").sum()
            margin = profit_total / revenue_total * 100
            findings.append(f"Recorded {profit_col} totals {profit_total:,.2f}, about {margin:.1f}% of recorded revenue.")
            if margin < 0:
                suggestions = [f"Recorded profit is negative overall. Review cost, discount, and profit entries before changing prices."]
            elif margin < 10:
                suggestions = [f"Recorded profit is {margin:.1f}% of revenue. Review costs and discounts to understand the narrow recorded margin."]
            else:
                suggestions = [f"Compare profit by product or region before deciding where to focus promotions."]
        else:
            suggestions = []
    elif profit_col is not None:
        metric = profit_col
        profit_total = pd.to_numeric(frame[profit_col], errors="coerce").sum()
        findings.append(f"Recorded {profit_col} totals {profit_total:,.2f}.")
        suggestions = ["Compare profit across products or locations to see where the recorded results differ."]
    elif quantity_col is not None:
        metric = quantity_col
        quantity_total = pd.to_numeric(frame[quantity_col], errors="coerce").sum()
        findings.append(f"Recorded {quantity_col} totals {quantity_total:,.2f}.")
        suggestions = ["Compare units by product and check whether the busiest products have enough stock."]
    elif len(numeric) == 1:
        metric = numeric[0]
        metric_total = pd.to_numeric(frame[metric], errors="coerce").sum()
        findings.append(f"The only numeric measure is {metric}; its recorded total is {metric_total:,.2f}.")
        suggestions = [f"Tell me what {metric} represents so I can suggest a meaningful comparison."]
    elif numeric:
        findings.append(f"I found numeric fields ({', '.join(str(col) for col in numeric[:8])}), but their meanings are not clear from the column names.")
        suggestions = ["Tell me which field represents sales, profit, quantity, or another important measure before I rank performance."]
    else:
        categorical = [col for col in frame.columns if pd.api.types.is_object_dtype(frame[col]) or isinstance(frame[col].dtype, pd.CategoricalDtype)]
        findings.append("There are no numeric measures, so I can't assess revenue, profit, price, or units from this table.")
        suggestions = ["Add or connect records with a numeric measure to compare results."]
        if categorical:
            most_common = _column_named(frame, ("product name", "product", "item name", "item", "category", "brand", "region", "country")) or categorical[0]
            frequent = frame[most_common].dropna().value_counts()
            if not frequent.empty:
                findings.append(f"The most frequent value in {most_common} is {frequent.index[0]} ({int(frequent.iloc[0]):,} rows); this is a row count, not a sales result.")

    if metric is not None and dimension is not None and dimension != metric:
        grouped = frame[[dimension, metric]].dropna(subset=[dimension, metric]).groupby(dimension, dropna=False)[metric].sum().sort_values(ascending=False)
        if not grouped.empty:
            top_name, top_value = grouped.index[0], float(grouped.iloc[0])
            findings.append(f"By {metric}, {top_name} is highest at {top_value:,.2f}.")
            result = grouped.rename("Result").reset_index()
            result_dimension = dimension
            if len(grouped) > 1:
                low_name, low_value = grouped.index[-1], float(grouped.iloc[-1])
                findings.append(f"{low_name} is lowest at {low_value:,.2f}.")
                if profit_col is not None and revenue_col is not None:
                    suggestions.append("Compare each product's or location's profit margin, not just its sales total, before deciding where to invest.")
                elif revenue_col is not None:
                    suggestions.append("Compare the strongest and weakest groups with profit and stock data before making changes.")
                elif quantity_col is not None:
                    suggestions.append("Compare the highest-volume group with its stock level and profit, if available.")

    suggestions.extend(_data_improvement_suggestions(frame, result, result_dimension, metric, "sum"))
    if not suggestions:
        suggestions = ["Choose a measure and category for a comparison, or add the fields you want to examine."]
    return {
        "answer": {
            "answer": "Here is a data-based overview of the selected table.",
            "finding": " ".join(findings),
            "suggestions": list(dict.fromkeys(suggestions))[:4],
            "caveat": "These are patterns in the uploaded records; they do not prove what caused the results.",
        },
        "result": result,
        "dimension": result_dimension,
        "description": "Data insights",
        "mode": "analysis",
    }


def _visualization_request(question: str, frame: pd.DataFrame) -> dict | None:
    """Build a chart only when the question and table provide a clear measure and category."""
    q = question.lower().replace("_", " ")
    has_viz_intent = any(word in q for word in ("chart", "graph", "plot", "visuali", "visualis")) or any(phrase in q for phrase in ("bar chat", "pie chat", "line chat", "area chat"))
    asks_lowest = any(word in q for word in ("cheapest", "lowest", "least expensive", "most affordable"))
    population_compare = "population" in q and any(word in q for word in ("country", "countries"))
    recommendation = any(phrase in q for phrase in ("important visualization", "important visualisation", "useful visualization", "useful visualisation", "useful patterns", "best chart", "recommend a chart", "best visualization", "best visualisation"))
    if has_viz_intent and any(word in q for word in ("important", "recommend", "useful", "best", "suggest")):
        recommendation = True
    if not (has_viz_intent or population_compare or recommendation):
        return None

    numeric = [col for col in frame.columns if not _is_index_artifact(col) and pd.api.types.is_numeric_dtype(frame[col])]
    if "pie" in q:
        requested_category = None
        category_terms = []
        if any(word in q for word in ("country", "countries", "nation")):
            category_terms.extend(("country name", "country", "nation", "entity", "origin"))
        if any(word in q for word in ("brand", "manufacturer", "make")):
            category_terms.extend(("brand", "manufacturer", "make"))
        if any(word in q for word in ("product", "products", "item", "items")):
            category_terms.extend(("product name", "product", "item name", "item"))
        if any(word in q for word in ("region", "area", "location", "store")):
            category_terms.extend(("region", "area", "location", "store"))
        requested_category = _column_named(frame, tuple(category_terms)) if category_terms else None
        if requested_category is None:
            requested_category = next(
                (col for col in frame.columns if pd.api.types.is_object_dtype(frame[col]) or isinstance(frame[col].dtype, pd.CategoricalDtype)),
                None,
            )
        if requested_category is None:
            return {"error": "I couldn't find a category field for the pie chart. It needs a field such as Country, Brand, Product, or Region."}
        known_measure_words = ("population", "revenue", "sales", "amount", "profit", "quantity", "units", "price", "cost")
        named_measure = any(word in q for word in known_measure_words) or any(str(col).lower().replace("_", " ") in q for col in numeric)
        measure = None
        if named_measure:
            measure = _numeric_column_named(frame, ("population", "revenue", "sales", "amount", "profit", "quantity", "units", "price", "cost"))
            if measure is None and "population" in q:
                candidate_years = [col for col in numeric if re.fullmatch(r"(?:18|19|20|21)\d{2}", str(col).strip())]
                if candidate_years:
                    explicit = next((col for col in candidate_years if re.search(rf"\b{re.escape(str(col))}\b", q)), None)
                    measure = explicit or max(candidate_years, key=lambda col: int(str(col)))
            if measure is None:
                return {"error": "I couldn't find a numeric field for the measure you named. Check Your data to see whether that field was read as text, or ask for record counts by category instead."}
        if measure is None:
            identifier = _column_named(frame, ("vehicle id", "car id", "vin", "record id"))
            if identifier is not None:
                counts = frame.dropna(subset=[requested_category]).groupby(requested_category, dropna=False)[identifier].nunique()
                count_label = f"Unique {identifier} count"
            else:
                counts = frame[requested_category].dropna().value_counts()
                count_label = "Record count"
            counts = counts.sort_values(ascending=False)
            if len(counts) > 8:
                counts = pd.concat([counts.iloc[:7], pd.Series({"Other categories": counts.iloc[7:].sum()})])
            result = counts.rename("Result").reset_index()
            result.columns = [requested_category, "Result"]
            result = result.reset_index(drop=True)
            top = result.iloc[0]
            counted_entities = "unique vehicle IDs" if identifier is not None else "rows"
            response = {
                "answer": {"answer": f"This pie chart shows {count_label.lower()} by {requested_category}. {top[requested_category]} has the most {counted_entities} ({int(top['Result']):,}).", "finding": "A pie chart is useful here for showing the share of records in each category.", "suggestions": _data_improvement_suggestions(frame), "caveat": f"This counts {counted_entities}, not price or sales totals, because no numeric measure was named."},
                "result": result,
                "dimension": requested_category,
                "chart_type": "pie",
                "chart_title": f"{count_label} by {requested_category}",
                "description": f"{count_label} by {requested_category}",
                "mode": "visualization",
            }
            return response

    if not numeric:
        return {"error": "I can make a chart once this table has a numeric value column to compare."}

    if "scatter" in q:
        axes = [col for col in numeric if str(col).lower().replace("_", " ") in q]
        if len(axes) < 2:
            return {"error": "For a scatter plot, name two numeric fields, for example: ‘Create a scatter plot of Revenue vs Profit.’"}
        x_axis, y_axis = axes[:2]
        plot_data = frame[[x_axis, y_axis]].apply(pd.to_numeric, errors="coerce").dropna()
        if plot_data.empty:
            return {"error": f"There are no complete {x_axis} and {y_axis} values to plot."}
        return {
            "answer": {"answer": f"Here is a scatter plot comparing {y_axis} with {x_axis}. Each dot represents one row in the selected table.", "finding": "The chart shows a relationship between the two selected fields; it does not prove that one causes the other.", "suggestions": [], "caveat": "Values come from the selected table; no AI-generated data is used."},
            "result": plot_data,
            "dimension": None,
            "chart_type": "scatter",
            "chart_title": f"{y_axis} vs {x_axis}",
            "x_axis": x_axis,
            "y_axis": y_axis,
            "description": f"{y_axis} vs {x_axis}",
            "mode": "visualization",
        }

    year_columns = [col for col in numeric if re.fullmatch(r"(?:18|19|20|21)\d{2}", str(col).strip())]
    explicit_year = next((col for col in year_columns if re.search(rf"\b{re.escape(str(col))}\b", q)), None)
    country_col = _column_named(frame, ("country name", "country", "nation", "entity", "location", "geo"))
    if "population" in q:
        population_col = _numeric_column_named(frame, ("population", "populations"))
        if population_col is not None:
            metric = population_col
        elif year_columns:
            metric = explicit_year or max(year_columns, key=lambda col: int(str(col)))
        else:
            metric = None
    elif any(word in q for word in ("profit", "margin")):
        metric = _numeric_column_named(frame, ("profit", "margin"))
    elif any(word in q for word in ("revenue", "sales", "income", "amount")):
        metric = _numeric_column_named(frame, ("revenue", "sales", "income", "amount"))
    elif any(word in q for word in ("price", "cost", "msrp", "value")):
        metric = _numeric_column_named(frame, ("price", "msrp", "cost", "value"))
    elif any(word in q for word in ("quantity", "units", "stock")):
        metric = _numeric_column_named(frame, ("quantity", "units", "stock"))
    else:
        metric = next((col for col in numeric if col in q), None)

    if metric not in numeric:
        # For an analysis suggestion, prefer common measures when they are available.
        if recommendation:
            metric = next(
                (col for term in ("revenue", "sales", "profit", "amount", "quantity", "units") for col in numeric if term in str(col).lower()),
                None,
            )
            if metric not in numeric:
                metric = next((col for col in numeric if col not in year_columns), None)
        if metric not in numeric:
            return {"error": "I couldn't identify a numeric measure in this table. Name the value you want compared, such as Population, Sales, Profit, or Quantity."}

    time_intent = any(word in q for word in ("trend", "over time", "line chart", "by date", "by month", "by year"))
    if population_compare:
        dimension = country_col
    elif time_intent:
        dimension = _column_named(frame, ("date", "time", "year", "month", "period"))
    elif any(word in q for word in ("country", "countries", "nation")):
        dimension = country_col
    elif any(word in q for word in ("product", "products", "item", "items", "sku")):
        dimension = _column_named(frame, ("product name", "product", "item name", "item", "sku"))
    elif any(word in q for word in ("brand", "brands", "manufacturer", "make")):
        dimension = _column_named(frame, ("brand", "manufacturer", "make"))
    elif any(word in q for word in ("region", "area", "location", "store")):
        dimension = _column_named(frame, ("region", "area", "location", "store"))
    else:
        dimension = None

    if dimension is None and recommendation:
        dimension = _column_named(frame, ("product name", "item name", "brand", "manufacturer", "make", "product", "category", "region", "store", "country name", "country", "item"))
        if dimension is None:
            dimension = _column_named(frame, ("date", "time", "year", "month", "period"))
    if dimension is None:
        dimension = next(
            (col for col in frame.columns if col != metric and (pd.api.types.is_object_dtype(frame[col]) or isinstance(frame[col].dtype, pd.CategoricalDtype))),
            None,
        )
    if dimension is None or dimension == metric:
        return {"error": "I found the value to chart, but not a category to compare it by. Add or select a field such as Country, Product, Region, or Date."}

    working = frame[[dimension, metric]].copy()
    period_col = _column_named(frame, ("year", "date", "period"))
    if "population" in q and metric not in year_columns and period_col and period_col not in (dimension, metric):
        values = frame[period_col]
        if pd.api.types.is_datetime64_any_dtype(values):
            years = values.dt.year
            requested_year = next((int(value) for value in re.findall(r"\b(?:18|19|20|21)\d{2}\b", q) if (years == int(value)).any()), None)
            selected_year = requested_year if requested_year is not None else years.max()
            working = frame.loc[years == selected_year, [dimension, metric]].copy()
            metric_label = f"{metric} ({selected_year})"
        elif pd.api.types.is_numeric_dtype(values):
            year_values = pd.to_numeric(values, errors="coerce")
            requested_year = next((int(value) for value in re.findall(r"\b(?:18|19|20|21)\d{2}\b", q) if (year_values == int(value)).any()), None)
            selected_year = requested_year if requested_year is not None else year_values.max()
            working = frame.loc[year_values == selected_year, [dimension, metric]].copy()
            metric_label = f"{metric} ({int(selected_year)})"
        else:
            metric_label = str(metric)
    elif metric in year_columns:
        metric_label = str(metric)
    else:
        metric_label = str(metric)
    if metric in year_columns and explicit_year is None and not population_compare:
        # Don't silently chart an arbitrary year column unless the user asked for a population comparison.
        return {"error": f"This table has year columns. Please specify which year to chart, for example {max(year_columns, key=lambda col: int(str(col)))}."}
    working[metric] = pd.to_numeric(working[metric], errors="coerce")
    price_comparison = any(token in str(metric).lower() for token in ("price", "msrp", "cost")) and any(token in q for token in ("brand", "manufacturer", "make"))
    if price_comparison and not any(token in q for token in ("total", "sum")):
        result = working.dropna(subset=[dimension, metric]).groupby(dimension, dropna=False)[metric].mean().rename("Result").reset_index()
        metric_label = f"Average {metric}"
    else:
        result = working.dropna(subset=[dimension, metric]).groupby(dimension, dropna=False)[metric].sum().rename("Result").reset_index()
    if result.empty:
        return {"error": "There are no usable values for that chart in the selected table."}
    if "pie" in q:
        chart_type = "pie"
        result = result.sort_values("Result", ascending=False).head(8).reset_index(drop=True)
    elif "area chart" in q:
        chart_type = "area"
    elif any(word in q for word in ("trend", "over time", "line chart")):
        chart_type = "line"
    else:
        chart_type = "bar"
    if chart_type == "bar" and pd.api.types.is_datetime64_any_dtype(result[dimension]):
        chart_type = "line"
    if chart_type == "line":
        result = result.sort_values(dimension).reset_index(drop=True)
    else:
        result = result.sort_values("Result", ascending=asks_lowest).head(20).reset_index(drop=True)
    title = f"{metric_label} by {dimension}"
    top = result.iloc[0]
    formatted_value = f"{top['Result']:,.0f}" if "population" in str(metric_label).lower() or str(metric_label).strip().isdigit() else f"{top['Result']:,.2f}"
    rank_word = "lowest" if asks_lowest else "highest"
    answer = f"Here is a {chart_type} chart of {metric_label} by {dimension}. {top[dimension]} is {rank_word} at {formatted_value} in the selected data."
    if recommendation:
        answer = f"Recommended visualization: compare {metric_label} by {dimension}. {top[dimension]} is highest at {formatted_value}."
    chart_suggestions = _data_improvement_suggestions(
        frame,
        result,
        dimension,
        metric,
        "mean" if price_comparison else "sum",
    )
    return {
        "answer": {"answer": answer, "finding": "The chart uses values from the selected table, grouped by the selected category.", "suggestions": chart_suggestions, "caveat": "The chart is calculated locally from your data; no AI-generated values are used."},
        "result": result,
        "dimension": dimension,
        "chart_type": chart_type,
        "chart_title": title,
        "metric_label": metric_label,
        "description": title,
        "mode": "visualization",
    }


def _ask_bizscope(question: str, frame: pd.DataFrame, api_key: str, consent: bool, model: str, history: list[dict]) -> dict:
    summary = _data_summary_request(question, frame)
    if summary is not None:
        return summary

    visualization = _visualization_request(question, frame)
    if visualization is not None:
        if "error" in visualization:
            return {"answer": {"answer": visualization["error"], "finding": "", "suggestions": [], "caveat": "No chart was created because BizScope could not match the request to fields in this table."}, "result": None, "dimension": None, "description": question, "mode": "clarification"}
        return visualization

    insights = _data_insights_request(question, frame)
    if insights is not None:
        return insights

    # Handle transaction counts deterministically: this prevents Quantity from
    # being mistaken for transaction count if the request is interpreted incorrectly.
    local_plan = interpret_question(question, frame)
    if local_plan and (
        local_plan.get("count_basis")
        or (str(local_plan.get("operation", "")).lower() == "average" and local_plan.get("ascending"))
    ):
        answer, result, dimension = _local_answer(question, frame)
        return {"answer": answer, "result": result, "dimension": dimension, "description": question, "mode": "calculated"}

    if not api_key or not consent:
        answer, result, dimension = _local_answer(question, frame)
        return {"answer": answer, "result": result, "dimension": dimension, "description": question, "mode": "local"}

    planned = request_analysis_plan(api_key, question, frame, model=model, history=history)
    plan = planned.get("plan")
    if plan is None:
        text = planned.get("text", "").strip() or "Could you rephrase that question?"
        return {
            "answer": {"answer": text, "finding": "", "suggestions": [], "caveat": "No calculation was run for this reply."},
            "result": None,
            "dimension": None,
            "description": question,
            "mode": "ai",
        }

    if plan.get("intent") == "analysis" and plan.get("group_by") != "__none__":
        plan["group_by"] = _human_friendly_group(frame, plan.get("group_by"), question)
    confidence = float(plan.get("confidence", 0.0))
    if plan.get("intent") in ("clarify", "unsupported") or confidence < 0.6:
        clarification = str(plan.get("clarification", "")).strip()
        if not clarification:
            clarification = "I couldn't match your question to one clear calculation. Which column should I measure, and which column should I compare it by?"
        return {
            "answer": {"answer": clarification, "finding": "No calculation was run because the request could not be matched confidently to this table.", "suggestions": [], "caveat": "Please clarify the measure or category, or choose a chart request."},
            "result": None,
            "dimension": None,
            "description": question,
            "mode": "ai",
            "plan": plan,
        }

    result = None
    dimension = None
    description = question
    if plan.get("intent") == "analysis":
        if plan.get("group_by") == "__none__":
            plan["group_by"] = None
        result, dimension, description = run_planned_analysis(frame, plan)
        # Send only the grouped calculation result, never the original table rows.
        result_for_ai = result.head(12).to_dict(orient="records")
    else:
        result_for_ai = None

    answer = explain_calculation(
        api_key,
        planned,
        {
            "question": question,
            "intent": plan.get("intent"),
            "clarification": plan.get("clarification", ""),
            "description": description,
            "calculated_result": result_for_ai,
        },
        model=model,
    )
    data_suggestions = _data_improvement_suggestions(
        frame,
        result if plan.get("intent") == "analysis" else None,
        dimension,
        plan.get("metric") if plan.get("intent") == "analysis" else None,
        plan.get("operation") if plan.get("intent") == "analysis" else None,
    )
    answer = {"answer": answer, "finding": "", "suggestions": data_suggestions, "caveat": ""}
    return {"answer": answer, "result": result, "dimension": dimension, "description": description, "mode": "ai", "plan": plan}


def _render_response(response: dict, source_name: str) -> None:
    result = response.get("result")
    if isinstance(result, pd.DataFrame):
        if response.get("table_title"):
            st.subheader(response["table_title"])
            st.dataframe(result, use_container_width=True, hide_index=True)
            return
        if response.get("chart_title"):
            st.subheader(response["chart_title"])
            dimension = response.get("dimension")
            values = [col for col in result.columns if col != dimension]
            if dimension in result.columns and values:
                chart_data = result.set_index(dimension)[values]
                if response.get("chart_type") == "line":
                    st.line_chart(chart_data, use_container_width=True)
                elif response.get("chart_type") == "area":
                    st.area_chart(chart_data, use_container_width=True)
                elif response.get("chart_type") == "pie":
                    pie_values = values[0]
                    st.vega_lite_chart(
                        result,
                        {
                            "mark": {"type": "arc", "tooltip": True},
                            "encoding": {
                                "theta": {"field": pie_values, "type": "quantitative"},
                                "color": {"field": dimension, "type": "nominal"},
                                "tooltip": [{"field": dimension, "type": "nominal"}, {"field": pie_values, "type": "quantitative"}],
                            },
                        },
                        use_container_width=True,
                    )
                else:
                    st.bar_chart(chart_data, use_container_width=True)
            elif response.get("chart_type") == "scatter":
                st.scatter_chart(result, x=response["x_axis"], y=response["y_axis"], use_container_width=True)
        with st.expander("See the calculation behind this answer", expanded=True):
            st.dataframe(result, use_container_width=True, hide_index=True)
            dimension = response.get("dimension")
            if not response.get("chart_title") and dimension and dimension in result.columns and "Result" in result.columns:
                chart = result[[dimension, "Result"]].dropna(subset=[dimension]).copy()
                if pd.api.types.is_datetime64_any_dtype(chart[dimension]):
                    chart = chart.sort_values(dimension)
                    st.line_chart(chart.set_index(dimension)[["Result"]], use_container_width=True)
                else:
                    st.bar_chart(chart.set_index(dimension)[["Result"]], use_container_width=True)


def _answer_text(answer: dict) -> str:
    parts = [answer.get("answer", "")]
    if answer.get("finding"):
        parts.extend(["", f"**What the data shows:** {answer['finding']}"])
    if answer.get("suggestions"):
        parts.extend(["", "**Ideas to consider:**"])
        parts.extend(f"- {suggestion}" for suggestion in answer["suggestions"])
    if answer.get("caveat"):
        parts.extend(["", f"_{answer['caveat']}_"])
    return "\n".join(parts).strip()


def _put_question(question: str) -> None:
    st.session_state["pending_question"] = question


st.sidebar.markdown("<div class='biz-pill'>DATA, MADE CLEAR</div>", unsafe_allow_html=True)
st.sidebar.markdown(
    """<div class="biz-brand"><span class="biz-brand-mark"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="10.5" cy="10.5" r="6.5" stroke="#C7E66B" stroke-width="2"/>
    <path d="m15.5 15.5 5 5M7 13l2.4-2.6 2 1.5 3.8-4" stroke="#F3F6F4" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg></span><span class="biz-brand-name">BizScope</span></div>""",
    unsafe_allow_html=True,
)
st.sidebar.divider()
configured_key = _get_api_key()
if configured_key:
    key_value = configured_key
else:
    key_value = ""
ai_model = os.getenv("BIZSCOPE_GEMINI_MODEL", DEFAULT_MODEL)

st.markdown(
    """
    <div class="biz-hero">
      <div class="biz-hero-copy">
        <div class="biz-pill">DATA, MADE CLEAR</div>
        <h1>See the story inside your data.</h1>
        <p>Explore patterns and find your next step.</p>
      </div>
      <div class="biz-hero-art" aria-hidden="true">
        <svg viewBox="0 0 220 170" role="img" aria-label="Magnifying glass and rising trend chart">
          <circle cx="91" cy="69" r="48" fill="#203B43" stroke="#C8E66B" stroke-width="5"/>
          <path d="M126 105 L164 143" stroke="#C8E66B" stroke-width="11" stroke-linecap="round"/>
          <path d="M59 89 V72 H75 V89 M84 89 V56 H100 V89 M109 89 V43 H125 V89"
                fill="#6FAE9C" stroke="#6FAE9C" stroke-width="3" stroke-linejoin="round"/>
          <path d="M55 56 L78 46 L94 53 L119 32" fill="none" stroke="#FFFFFF"
                stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M109 32 H119 V42" fill="none" stroke="#FFFFFF" stroke-width="4"
                stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="166" cy="37" r="5" fill="#C8E66B"/>
          <path d="M166 25 V17 M166 57 V49 M154 37 H146 M186 37 H178"
                stroke="#C8E66B" stroke-width="3" stroke-linecap="round"/>
        </svg>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded_files = st.file_uploader(
    "Add your data",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
    help="Upload any tabular CSV or Excel data. Each CSV and workbook sheet becomes a table you can explore.",
)

if not uploaded_files:
    st.sidebar.markdown(
        """<div class="biz-guide">
        <div class="biz-guide-title">QUICK START</div>
        <div class="biz-guide-row"><span class="biz-guide-step">1</span><div class="biz-guide-text"><b>Upload data</b><span>CSV or Excel file</span></div></div>
        <div class="biz-guide-row"><span class="biz-guide-step">2</span><div class="biz-guide-text"><b>Prepare</b><span>Clean blanks and columns</span></div></div>
        <div class="biz-guide-row"><span class="biz-guide-step">3</span><div class="biz-guide-text"><b>Explore</b><span>Charts, comparisons, and reports</span></div></div>
        </div>""",
        unsafe_allow_html=True,
    )

if not uploaded_files:
    st.subheader("Start with your data")
    st.write("Upload a CSV or Excel file to explore its contents.")
    st.download_button("Get a sample sales file", _sample_csv(), "bizscope_sample_sales.csv", "text/csv")
    st.stop()

tables, file_issues = read_uploaded_tables(uploaded_files)
for issue in file_issues:
    st.warning(issue)
if not tables:
    st.error("I couldn't find a readable table in those files. Check that each table has one header row.")
    st.stop()

signature = tuple((file.name, hashlib.sha256(file.getvalue()).hexdigest()) for file in uploaded_files)
if st.session_state.get("upload_signature") != signature:
    st.session_state["upload_signature"] = signature
    for name in ("joined_table", "cleaned_table", "cleaned_source", "cleaning_changes", "assistant_history", "assistant_result", "last_analysis", "custom_visualization", "table_selector", "select_prepared_next_run"):
        st.session_state.pop(name, None)

if st.session_state.get("joined_table") is not None:
    tables["Joined table"] = st.session_state["joined_table"]

prepared_source = st.session_state.get("cleaned_source")
prepared_label = None
if prepared_source in tables and isinstance(st.session_state.get("cleaned_table"), pd.DataFrame):
    prepared_label = f"Prepared copy · {prepared_source}"
    while prepared_label in tables:
        prepared_label += " · 2"
    tables[prepared_label] = st.session_state["cleaned_table"]

if st.session_state.pop("select_prepared_next_run", False) and prepared_label:
    st.session_state["table_selector"] = prepared_label

source_name = st.sidebar.selectbox("Choose a table", list(tables.keys()), key="table_selector")
if st.session_state.get("active_source") != source_name:
    st.session_state["active_source"] = source_name
    st.session_state["assistant_history"] = []
    st.session_state.pop("assistant_result", None)
    st.session_state.pop("custom_visualization", None)
    for widget_key in ("viz_kind", "viz_category", "viz_measure", "viz_aggregation", "viz_top_n", "viz_date", "viz_grain", "viz_time_metric", "viz_time_aggregation", "viz_hist_metric", "viz_bins", "viz_scatter_x", "viz_scatter_y"):
        st.session_state.pop(widget_key, None)
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []
data = tables[source_name]
st.sidebar.markdown("---")
st.sidebar.caption("CURRENT TABLE")
st.sidebar.markdown(f"**{source_name}**")
st.sidebar.caption(f"{len(data):,} rows · {len(data.columns):,} fields · {int(data.isna().sum().sum()):,} blank cells")
if prepared_label and source_name == prepared_label:
    st.sidebar.success("Prepared copy selected. Suggestions and charts use these updated data.")
elif prepared_label:
    st.sidebar.caption("A prepared copy is available in this table selector.")
if data.shape[1] == 0:
    st.warning("This table has no columns. Choose another table or check the source file.")
    st.stop()
if data.empty:
    st.warning("This table has column names but no data rows.")
    st.stop()

numeric_columns = [col for col in data.columns if pd.api.types.is_numeric_dtype(data[col])]
quality_missing = int(data.isna().sum().sum())
quality_duplicates = int(data.duplicated().sum())
top_metrics = st.columns(4)
top_metrics[0].metric("Records", f"{len(data):,}")
top_metrics[1].metric("Fields", f"{len(data.columns):,}")
top_metrics[2].metric("Needs attention", f"{quality_missing:,} missing cells")
top_metrics[3].metric("Repeated rows", f"{quality_duplicates:,}")

overview_tab, data_tab, prepare_tab, connect_tab, visualize_tab, assistant_tab, export_tab = st.tabs(
    ["Overview", "Your data", "Prepare data", "Connect tables", "Visualize", "Ask BizScope", "Downloads"]
)


with overview_tab:
    st.subheader("Overview")
    if numeric_columns:
        preferred = next((col for col in numeric_columns if any(word in str(col).lower() for word in ("revenue", "sales", "profit", "amount"))), None)
        if preferred:
            st.metric(f"Total {preferred.replace('_', ' ').lower()}", f"{data[preferred].sum(skipna=True):,.2f}")
        else:
            st.info("Open Ask BizScope to calculate or compare a number field.")
    else:
        st.info("No number fields found. View category counts or convert a field in Prepare data.")
    preview_rows = st.slider("Show records", 5, min(100, max(5, len(data))), min(15, max(5, len(data))), key="preview_rows")
    st.dataframe(data.head(preview_rows), use_container_width=True, hide_index=True)

    st.subheader("Useful next steps")
    next_steps = _data_improvement_suggestions(data)
    if next_steps:
        for suggestion in next_steps:
            st.markdown(f"- {suggestion}")
    else:
        st.write("No obvious data-quality issue was detected. Open Visualize for chart ideas based on these fields.")


with visualize_tab:
    st.subheader("Visualize")
    recommendations = _suggest_visualizations(data)
    if recommendations:
        st.markdown("#### Suggested views for this dataset")
        for index, idea in enumerate(recommendations):
            with st.container(border=True):
                st.markdown(f"**{idea['title']}**")
                st.caption(idea["note"])
                chart_data = idea["data"]
                if idea["type"] == "line":
                    st.line_chart(chart_data.set_index(idea["x"])[[idea["y"]]], use_container_width=True)
                elif idea["type"] == "area":
                    st.area_chart(chart_data.set_index(idea["x"])[[idea["y"]]], use_container_width=True)
                elif idea["type"] == "pie":
                    st.vega_lite_chart(
                        chart_data,
                        {"mark": {"type": "arc", "tooltip": True}, "encoding": {
                            "theta": {"field": idea["y"], "type": "quantitative"},
                            "color": {"field": idea["x"], "type": "nominal"},
                            "tooltip": [{"field": idea["x"], "type": "nominal"}, {"field": idea["y"], "type": "quantitative"}],
                        }},
                        use_container_width=True,
                    )
                elif idea["type"] == "scatter":
                    st.scatter_chart(chart_data, x=idea["x"], y=idea["y"], use_container_width=True)
                else:
                    st.bar_chart(chart_data, x=idea["x"], y=idea["y"], use_container_width=True)
    else:
        st.info("No chart suggestion yet. Check the field types or prepare the columns first.")

    st.divider()
    st.markdown("#### Build a chart")
    numeric_fields, category_fields, date_fields = get_field_types(data)
    available_chart_types = []
    if category_fields:
        available_chart_types.extend(["Bar chart", "Pie chart"])
    if date_fields:
        available_chart_types.extend(["Line chart", "Area chart"])
    if numeric_fields:
        available_chart_types.append("Histogram")
    if len(numeric_fields) >= 2:
        available_chart_types.append("Scatter plot")

    if not available_chart_types:
        st.info("No supported chart fields found. Check field types or convert a column in Prepare data.")
    else:
        chart_kind = st.selectbox("What would you like to create?", available_chart_types, key="viz_kind")
        kind = chart_kind.split()[0].lower()
        left, right = st.columns(2)
        if kind in ("bar", "pie"):
            with left:
                x_field = st.selectbox("Compare categories from", category_fields, key="viz_category")
            y_choices = ["Count rows"] + numeric_fields
            with right:
                y_choice = st.selectbox("Measure", y_choices, key="viz_measure")
            y_field = None if y_choice == "Count rows" else y_choice
            if y_field is not None:
                aggregation = st.selectbox("How should values be combined?", AGGREGATIONS, index=AGGREGATIONS.index("Average") if any(word in str(y_field).lower() for word in ("price", "cost", "rate", "margin", "score", "rating", "temperature")) else 0, key="viz_aggregation")
            else:
                aggregation = "Record count"
            top_n = st.slider("Number of categories", min_value=3, max_value=30, value=12, key="viz_top_n") if kind == "bar" else 10
            date_grain = "Month"
            bins = 12
        elif kind in ("line", "area"):
            with left:
                x_field = st.selectbox("Date field", date_fields, key="viz_date")
                date_grain = st.selectbox("Group dates by", ["Day", "Week", "Month", "Quarter", "Year"], index=2, key="viz_grain")
            with right:
                y_field = st.selectbox("Value to follow", numeric_fields + ["Count rows"], key="viz_time_metric")
            if y_field == "Count rows":
                y_field = None
                aggregation = "Record count"
            else:
                aggregation = st.selectbox("How should values be combined?", AGGREGATIONS, index=AGGREGATIONS.index("Average") if any(word in str(y_field).lower() for word in ("price", "cost", "rate", "margin", "score", "rating", "temperature")) else 0, key="viz_time_aggregation")
            top_n, bins = 15, 12
        elif kind == "histogram":
            x_field = st.selectbox("Number field", numeric_fields, key="viz_hist_metric")
            bins = st.slider("Number of ranges", 5, 40, 12, key="viz_bins")
            y_field, aggregation, date_grain, top_n = None, "Record count", "Month", 15
        else:
            with left:
                x_field = st.selectbox("Horizontal axis", numeric_fields, key="viz_scatter_x")
            y_options = [column for column in numeric_fields if column != x_field]
            with right:
                y_field = st.selectbox("Vertical axis", y_options, key="viz_scatter_y")
            aggregation, date_grain, top_n, bins = "Record count", "Month", 15, 12

        chart_settings = (kind, str(x_field), str(y_field), aggregation, bins, top_n, date_grain)
        if st.button("Create visualization", type="primary", key="build_visualization"):
            try:
                chart_data, metadata = build_chart(data, kind, x_field, y_field, aggregation, bins=bins, top_n=top_n, date_grain=date_grain)
                st.session_state["custom_visualization"] = {"source": source_name, "settings": chart_settings, "kind": kind, "data": chart_data, **metadata}
            except Exception as exc:
                st.error(f"I couldn't create that chart: {exc}")

        custom_chart = st.session_state.get("custom_visualization")
        if custom_chart and custom_chart.get("source") == source_name and custom_chart.get("settings") != chart_settings:
            st.info("Your chart choices changed. Select **Create visualization** to refresh the chart.")
        elif custom_chart and custom_chart.get("source") == source_name:
            st.markdown(f"#### {custom_chart['title']}")
            st.caption(custom_chart["note"])
            chart_data = custom_chart["data"]
            if custom_chart["kind"] == "line":
                st.line_chart(chart_data.set_index(custom_chart["x"])[[custom_chart["y"]]], use_container_width=True)
            elif custom_chart["kind"] == "area":
                st.area_chart(chart_data.set_index(custom_chart["x"])[[custom_chart["y"]]], use_container_width=True)
            elif custom_chart["kind"] == "pie":
                st.vega_lite_chart(chart_data, {"mark": {"type": "arc", "tooltip": True}, "encoding": {
                    "theta": {"field": custom_chart["y"], "type": "quantitative"},
                    "color": {"field": custom_chart["x"], "type": "nominal"},
                    "tooltip": [{"field": custom_chart["x"], "type": "nominal"}, {"field": custom_chart["y"], "type": "quantitative"}],
                }}, use_container_width=True)
            elif custom_chart["kind"] == "scatter":
                st.scatter_chart(chart_data, x=custom_chart["x"], y=custom_chart["y"], use_container_width=True)
            else:
                st.bar_chart(chart_data, x=custom_chart["x"], y=custom_chart["y"], use_container_width=True)
            st.dataframe(chart_data, use_container_width=True, hide_index=True)
            st.download_button(
                "Download chart data as CSV",
                chart_data.to_csv(index=False).encode("utf-8-sig"),
                file_name="bizscope_chart_data.csv",
                mime="text/csv",
                key="download_chart_data",
            )


with assistant_tab:
    st.subheader("Ask BizScope")
    st.write("Calculate totals, averages, rankings, and comparisons.")
    if key_value:
        ai_consent = st.checkbox("Use Gemini to help interpret your question.", value=False, key="ai_data_consent_v2")
        st.caption("Gemini receives your question, field names, and calculated results. Uploaded rows stay in BizScope.")
    else:
        ai_consent = False
    numeric_fields, category_fields, date_fields = get_field_types(data)
    st.markdown("#### Available fields")
    if numeric_fields:
        group_fields = category_fields + date_fields
        field_col, group_col = st.columns(2)
        with field_col:
            with st.container(border=True):
                st.markdown("**Number fields**")
                st.caption(", ".join(str(col) for col in numeric_fields[:10]))
        with group_col:
            with st.container(border=True):
                st.markdown("**Group by**")
                st.caption(", ".join(str(col) for col in group_fields[:10]) if group_fields else "None found")
        calculation_ideas = suggest_calculations(data)
        if calculation_ideas:
            st.markdown("#### Try a calculation")
            idea_columns = st.columns(min(3, len(calculation_ideas)))
            for index, idea in enumerate(calculation_ideas):
                button_label = idea.removeprefix("What is the ").removesuffix("?")
                idea_columns[index % len(idea_columns)].button(
                    button_label,
                    key=f"calculation_idea_{index}",
                    on_click=_put_question,
                    args=(idea,),
                    use_container_width=True,
                )
    else:
        st.info("No numeric fields found. Use Visualize for category counts or Prepare data to convert a value field.")
    history_to_show = list(st.session_state.get("assistant_history", []))
    for entry in history_to_show:
        with st.chat_message(entry["role"]):
            st.markdown(entry["text"])

    latest_answer = st.session_state.get("assistant_result")
    if latest_answer and latest_answer.get("source") == source_name:
        _render_response(latest_answer, source_name)

    typed_question = st.chat_input("Ask a calculation about this table…", key="assistant_chat_input")
    pending_question = st.session_state.pop("pending_question", "")
    question = typed_question or pending_question
    if question and question.strip():
        previous_history = list(st.session_state["assistant_history"])
        st.session_state["assistant_history"].append({"role": "user", "text": question.strip()})
        try:
            with st.spinner("Looking at your data…"):
                response = _ask_bizscope(
                    question.strip(), data, key_value.strip(), bool(ai_consent),
                    ai_model if "ai_model" in locals() else DEFAULT_MODEL,
                    previous_history,
                )
        except Exception as exc:
            if key_value and ai_consent:
                fallback, result, dimension = _local_answer(question.strip(), data)
                if result is not None:
                    response = {"answer": fallback, "result": result, "dimension": dimension, "description": question.strip(), "mode": "local"}
                else:
                    response = {
                        "answer": fallback,
                        "result": None,
                        "dimension": None,
                        "description": question.strip(),
                        "mode": "error",
                    }
            else:
                fallback, result, dimension = _local_answer(question.strip(), data)
                response = {"answer": fallback, "result": result, "dimension": dimension, "description": question.strip(), "mode": "local"}
        st.session_state["assistant_result"] = {**response, "source": source_name}
        answer_text = _answer_text(response.get("answer", {})) or "I couldn't prepare an answer."
        st.session_state["assistant_history"].append({"role": "assistant", "text": answer_text})
        st.rerun()


with data_tab:
    st.subheader("Data profile")
    st.dataframe(profile_table(data), use_container_width=True, hide_index=True)
    st.markdown("#### Summary values")
    st.dataframe(summarize_table(data), use_container_width=True)
    st.markdown("#### Data preview")
    st.dataframe(data.head(100), use_container_width=True, hide_index=True)


with prepare_tab:
    st.subheader("Prepare data")
    st.caption("Changes create a separate copy. Your uploaded table stays unchanged.")

    prep_left, prep_right = st.columns(2)
    with prep_left:
        st.markdown("#### Clean values and rows")
        trim_text = st.checkbox("Trim extra spaces around text", value=True, key="prep_trim")
        normalize_text = st.selectbox("Text capitalization", ["Keep as-is", "lowercase", "UPPERCASE", "Title Case"], key="prep_case")
        drop_empty = st.checkbox("Remove completely blank rows", key="prep_empty")
        drop_duplicates = st.checkbox("Remove exact duplicate rows", key="prep_duplicates")
        fill_missing = st.selectbox(
            "Fill missing values",
            ["Leave blank", "Numbers: median; text: most common", "Numbers: zero; text: most common"],
            help="Filling is optional. Median is a common numeric choice; zero is only appropriate when a blank really means zero.",
            key="prep_fill",
        )
        replace_column = st.selectbox("Find and replace in a column (optional)", ["Skip"] + list(data.columns), key="prep_replace_col")
        find_value = st.text_input("Find exact text", key="prep_find")
        replace_value = st.text_input("Replace with", key="prep_replace")

    with prep_right:
        st.markdown("#### Set up columns")
        convert_column = st.selectbox("Convert a column's format (optional)", ["Skip"] + list(data.columns), key="prep_convert_col")
        convert_type = st.selectbox("Convert to", ["Number", "Date/time", "Text"], key="prep_convert_type")
        columns_to_drop = st.multiselect("Remove columns you don't need", list(data.columns), key="prep_drop_cols")
        rename_column = st.selectbox("Rename a column (optional)", ["Skip"] + list(data.columns), key="prep_rename_col")
        rename_to = st.text_input("New column name", key="prep_rename_to", disabled=rename_column == "Skip")

    if st.button("Apply changes to a copy", type="primary", key="create_cleaned_copy"):
        rename_map = {}
        if rename_column != "Skip" and rename_to.strip() and rename_to.strip() != str(rename_column):
            rename_map[rename_column] = rename_to.strip()
        try:
            remaining_columns = [col for col in data.columns if col not in columns_to_drop]
            if not remaining_columns:
                raise ValueError("Keep at least one column in the prepared copy.")
            if rename_map and rename_map[rename_column] in remaining_columns and rename_map[rename_column] != rename_column:
                raise ValueError("That new name already belongs to another column. Choose a unique name.")
            cleaned, notes = _prepare_table(
                data,
                trim_text=trim_text,
                normalize_text=normalize_text,
                drop_empty=drop_empty,
                drop_duplicates=drop_duplicates,
                fill_missing=fill_missing,
                rename_map=rename_map,
                drop_columns=columns_to_drop,
                convert_column=None if convert_column == "Skip" else convert_column,
                convert_type=convert_type,
                replace_column=None if replace_column == "Skip" else replace_column,
                find_value=find_value,
                replace_value=replace_value,
            )
            st.session_state["cleaned_table"] = cleaned
            base_source = st.session_state.get("cleaned_source") if prepared_label and source_name == prepared_label else source_name
            st.session_state["cleaned_source"] = base_source
            st.session_state["cleaning_changes"] = notes
            st.session_state["select_prepared_next_run"] = True
            st.rerun()
        except Exception as exc:
            st.error(f"I couldn't prepare this copy: {exc}")
    if prepared_label and source_name == prepared_label and "cleaned_table" in st.session_state:
        st.info("You are viewing the prepared copy. The original remains available in the table selector.")
    if (st.session_state.get("cleaned_source") == source_name or (prepared_label and source_name == prepared_label)) and "cleaned_table" in st.session_state:
        cleaned = st.session_state["cleaned_table"]
        changes = st.session_state["cleaning_changes"]
        st.markdown("#### Preparation summary")
        for note in changes:
            st.write(f"- {note}")
        st.download_button(
            "Download prepared copy as CSV",
            data=cleaned.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{source_name.replace(' ', '_').replace('·', '-')}_prepared.csv",
            mime="text/csv",
            key="download_prepared_copy",
        )
        st.markdown("#### Preview the prepared copy")
        st.dataframe(cleaned.head(100), use_container_width=True, hide_index=True)


with connect_tab:
    st.subheader("Connect tables")
    st.caption("Join related tables using a shared ID or matching field.")
    source_options = [name for name in tables if name != "Joined table"]
    if len(source_options) < 2:
        st.info("Upload at least two CSV files or workbook sheets to connect tables.")
    else:
        left_column, right_column = st.columns(2)
        left_name = left_column.selectbox("Main table", source_options, key="join_left")
        right_options = [name for name in source_options if name != left_name]
        right_name = right_column.selectbox("Table to add", right_options, key="join_right")
        left_data, right_data = tables[left_name], tables[right_name]
        common_keys = [column for column in left_data.columns if column in right_data.columns]
        join_type = st.selectbox("When a row has no match", ["Keep the transaction row", "Leave unmatched rows out"])
        if common_keys:
            common_key = st.selectbox("Matching ID field", common_keys)
            left_key = right_key = common_key
        else:
            st.info("The ID fields have different names. Select the matching field from each table.")
            key_left, key_right = st.columns(2)
            left_key = key_left.selectbox("ID in main table", list(left_data.columns), key="left_join_key")
            right_key = key_right.selectbox("ID in added table", list(right_data.columns), key="right_join_key")
        if st.button("Connect these tables", type="primary"):
            try:
                joined = left_data.merge(
                    right_data,
                    how="left" if join_type == "Keep the transaction row" else "inner",
                    left_on=left_key,
                    right_on=right_key,
                    suffixes=("_main", "_added"),
                    indicator=True,
                    validate="many_to_many",
                )
                match_count = int((joined["_merge"] == "both").sum())
                joined = joined.drop(columns="_merge")
                st.session_state["joined_table"] = joined
                st.success(f"Connected. {match_count:,} row(s) matched; the new table has {len(joined):,} rows.")
                if right_data[right_key].duplicated().any():
                    st.warning("Some IDs repeat in the added table, so the join may repeat transaction rows. Check these IDs before using totals.")
                st.dataframe(joined.head(30), use_container_width=True, hide_index=True)
                st.info("Select Joined table in the table menu to continue.")
            except Exception as exc:
                st.error(f"I couldn't connect those tables: {exc}")


with export_tab:
    st.subheader("Downloads")
    export_frame = data
    if st.session_state.get("cleaned_source") == source_name and "cleaned_table" in st.session_state:
        use_cleaned = st.checkbox("Use the cleaned copy", value=False)
        if use_cleaned:
            export_frame = st.session_state["cleaned_table"]
    st.download_button(
        "Download this table as CSV",
        data=export_frame.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{source_name.replace(' ', '_').replace('·', '-')}.csv",
        mime="text/csv",
    )
    last_result = st.session_state.get("assistant_result")
    if last_result and last_result.get("source") != source_name:
        last_result = None
    report = _report_text(source_name, export_frame, last_result)
    st.download_button("Download data summary", report.encode("utf-8"), "bizscope_summary.md", "text/markdown")


st.sidebar.divider()
