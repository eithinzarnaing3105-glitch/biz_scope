"""Gemini Interactions API client using Python's standard library."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_MODEL = "gemini-3.8-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def _post(api_key: str, payload: dict) -> dict:
    request = Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("error", {}).get("message", "Request rejected.")
        except Exception:
            detail = "Request rejected. Check the Gemini API key and its project access."
        raise RuntimeError(f"Gemini API returned {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError("BizScope could not reach Gemini. Check your internet connection and try again.") from exc
    except TimeoutError as exc:
        raise RuntimeError("Gemini took too long to respond. Please try again.") from exc


def request_analysis_plan(
    api_key: str,
    question: str,
    frame,
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Ask Gemini to choose one allowed calculation using column names only."""
    columns = []
    numeric_columns = []
    date_columns = []
    for column in frame.columns:
        dtype = str(frame[column].dtype)
        name = str(column).lower().replace("_", " ")
        if "datetime" in dtype or any(token in name for token in ("date", "time", "year", "month")):
            role = "date_or_time"
        elif any(token in name for token in ("id", "key", "code", "sku")):
            role = "identifier"
        elif dtype.startswith(("int", "float", "uint")):
            role = "numeric_measure"
        elif dtype in ("object", "string", "category"):
            role = "category_or_label"
        else:
            role = "other"
        columns.append({"name": str(column), "type": dtype, "role": role, "missing": int(frame[column].isna().sum())})
        if dtype.startswith(("int", "float", "uint")):
            numeric_columns.append(str(column))
        if "datetime" in dtype:
            date_columns.append(str(column))

    column_names = [str(column) for column in frame.columns]
    metric_names = column_names or ["__none__"]
    group_names = ["__none__", *column_names]
    tool = {
        "type": "function",
        "name": "choose_data_analysis",
        "description": (
            "Choose a supported calculation for a question about the selected business table. "
            "Do not calculate values. Use exact column names. If the question asks what is highest or lowest, "
            "choose the category in group_by and set sort_order. For a time trend, choose a date column and time_grain."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": ["analysis", "help", "clarify", "unsupported"]},
                "metric": {"type": "string", "enum": metric_names},
                "group_by": {"type": "string", "enum": group_names},
                "operation": {"type": "string", "enum": ["sum", "average", "median", "minimum", "maximum", "count", "distinct_count"]},
                "sort_order": {"type": "string", "enum": ["highest", "lowest"]},
                "time_grain": {"type": "string", "enum": ["none", "day", "week", "month", "quarter", "year"]},
                "clarification": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["intent", "metric", "group_by", "operation", "sort_order", "time_grain", "clarification", "confidence"],
        },
    }

    prior_turns = []
    for item in (history or [])[-8:]:
        speaker = "Shop owner" if item.get("role") == "user" else "BizScope"
        message = str(item.get("text", "")).strip()
        if message:
            prior_turns.append(f"{speaker}: {message[:1000]}")

    prompt = (
        "You are Gemini inside BizScope, a helpful assistant for people exploring many kinds of tabular datasets. Use plain, friendly language. "
        "The application will calculate every number using Pandas; you only select the operation. Never invent values or code. "
        "Do not guess a measure or category from the first numeric/text field. Use the column roles and exact names. "
        "If multiple measures could match (for example, best product could mean revenue, units, or profit), set intent to clarify and ask which one. "
        "If the user asks for help using BizScope, set intent to help. If the table cannot answer, set intent to unsupported "
        "If the question is unclear or the schema does not confidently support the requested calculation, set intent to clarify. "
        "Set confidence below 0.6 and ask a specific question instead of making a weak guess. "
        "and explain what field is missing in clarification. For analysis, use only the listed columns. "
        "For questions about how many transactions, orders, receipts, or invoices each product has, count distinct IDs "
        "from the transaction/order/receipt/invoice ID column, grouped by the product/item/category field. Never sum Quantity "
        "when the user asks for a number of transactions. "
        "When a calculation result is returned, explain it simply, state the observed finding, give practical suggestions, "
        "and mention limitations. Keep facts tied to the returned calculation and do not claim unproven causes.\n\n"
        f"Recent conversation:\n{chr(10).join(prior_turns) if prior_turns else '(none)'}\n\n"
        f"Current question: {question}\n\n"
        f"Selected table schema: {json.dumps({'rows': len(frame), 'columns': columns, 'numeric_columns': numeric_columns, 'date_columns': date_columns}, ensure_ascii=False)}"
    )
    response = _post(
        api_key,
        {
            "model": model,
            "store": False,
            "input": prompt,
            "tools": [tool],
        },
    )
    for step in response.get("steps", []):
        if step.get("type") == "function_call" and step.get("name") == "choose_data_analysis":
            arguments = step.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Gemini returned an unreadable analysis plan. Please rephrase your question.") from exc
            return {"plan": arguments, "interaction": response, "call": step, "tool": tool, "prompt": prompt}
    return {"plan": None, "text": str(response.get("output_text", "")).strip(), "interaction": response, "tool": tool, "prompt": prompt}


def explain_calculation(
    api_key: str,
    planned: dict,
    result: dict,
    model: str = DEFAULT_MODEL,
) -> str:
    """Return the Pandas result to Gemini and get a plain-language answer."""
    call = planned["call"]
    interaction = planned["interaction"]
    function_result = {
        "type": "function_result",
        "name": call["name"],
        "call_id": call["id"],
        "result": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
    }
    response = _post(
        api_key,
        {
            "model": model,
            "store": False,
            "tools": [planned["tool"]],
            "input": [
                {"type": "user_input", "content": planned["prompt"]},
                *interaction.get("steps", []),
                function_result,
            ],
        },
    )
    answer = str(response.get("output_text", "")).strip()
    if not answer:
        raise RuntimeError("Gemini returned no explanation. The calculated result is still available.")
    return answer
