"""Safe, local chart suggestions and chart data preparation."""

from __future__ import annotations

import pandas as pd


AGGREGATIONS = ["Sum", "Average", "Median", "Minimum", "Maximum", "Record count", "Distinct count"]


def _clean_name(column) -> str:
    return str(column).strip().lower().replace("_", " ").replace("-", " ")


def is_identifier(column) -> bool:
    name = _clean_name(column)
    return (
        name in {"index", "row number", "unnamed: 0", "unnamed 0"}
        or name.endswith((" id", " code", " sku", " key"))
        or name in {"id", "code", "sku", "key"}
    )


def get_field_types(frame: pd.DataFrame) -> tuple[list, list, list]:
    """Return useful measures, categories, and dates while excluding identifiers."""
    numeric = [
        col for col in frame.columns
        if pd.api.types.is_numeric_dtype(frame[col])
        and not is_identifier(col)
        and frame[col].notna().any()
    ]
    categories = [
        col for col in frame.columns
        if (pd.api.types.is_object_dtype(frame[col])
            or pd.api.types.is_string_dtype(frame[col])
            or isinstance(frame[col].dtype, pd.CategoricalDtype)
            or pd.api.types.is_bool_dtype(frame[col]))
        and not is_identifier(col)
        and 2 <= frame[col].nunique(dropna=True) <= 100
    ]
    # Numeric labels such as 0/1 outcomes or coded groups can be meaningful
    # categories; include these when their column names indicate that role.
    categorical_numeric_terms = ("class", "category", "group", "segment", "level", "status", "flag", "type")
    categories.extend(
        col for col in frame.columns
        if col in numeric
        and any(term in _clean_name(col) for term in categorical_numeric_terms)
        and 2 <= frame[col].nunique(dropna=True) <= 15
    )
    dates = [col for col in frame.columns if pd.api.types.is_datetime64_any_dtype(frame[col])]
    return numeric, categories, dates


def _default_aggregation(metric) -> str:
    name = _clean_name(metric)
    if any(word in name for word in ("revenue", "sales", "profit", "quantity", "units", "population", "amount", "count", "total", "volume")):
        return "Sum"
    return "Average"


def _top_with_other(result: pd.DataFrame, label: str, limit: int = 8) -> pd.DataFrame:
    if len(result) <= limit:
        return result
    visible = result.head(limit).copy()
    other_total = pd.to_numeric(result.iloc[limit:]["Result"], errors="coerce").sum()
    other = pd.DataFrame([{label: "Other categories", "Result": other_total}])
    return pd.concat([visible, other], ignore_index=True)


def build_chart(
    frame: pd.DataFrame,
    chart_type: str,
    x_field,
    y_field=None,
    aggregation: str = "Sum",
    *,
    bins: int = 12,
    top_n: int = 15,
    date_grain: str = "Month",
) -> tuple[pd.DataFrame, dict]:
    """Prepare chart values from a dataframe; never executes generated code."""
    if x_field not in frame.columns:
        raise ValueError("Choose a valid field for the horizontal axis.")
    chart_type = chart_type.lower()
    if chart_type not in {"bar", "pie", "line", "area", "histogram", "scatter"}:
        raise ValueError("Choose a supported chart type.")

    if chart_type in {"histogram", "scatter"}:
        numeric, _, _ = get_field_types(frame)
        if x_field not in numeric:
            raise ValueError("Choose a numeric field for this chart.")
        if chart_type == "histogram":
            values = pd.to_numeric(frame[x_field], errors="coerce").dropna()
            if values.empty:
                raise ValueError(f"{x_field} has no usable numeric values.")
            bins = max(3, min(60, int(bins)))
            counts = pd.cut(values, bins=bins, duplicates="drop")
            result = counts.value_counts(sort=False).rename("Records").reset_index()
            result.columns = ["Range", "Records"]
            result["Range"] = result["Range"].astype(str)
            return result, {"x": "Range", "y": "Records", "title": f"Distribution of {x_field}", "note": f"Each bar shows how many records fall within a {x_field} range."}

        if y_field not in numeric or y_field == x_field:
            raise ValueError("Choose a different numeric field for the vertical axis.")
        chart_data = frame[[x_field, y_field]].apply(pd.to_numeric, errors="coerce").dropna()
        sampled = len(chart_data) > 10000
        if sampled:
            chart_data = chart_data.sample(10000, random_state=7)
        return chart_data, {"x": x_field, "y": y_field, "title": f"{y_field} compared with {x_field}", "note": "Each dot is one record." + (" Showing a consistent sample of 10,000 rows." if sampled else "")}

    if chart_type in {"line", "area"} and not pd.api.types.is_datetime64_any_dtype(frame[x_field]):
        raise ValueError("Choose a date/time field for a line or area chart.")

    if y_field is None:
        if chart_type == "pie":
            counts = frame[x_field].fillna("(Blank)").value_counts()
            if counts.empty:
                raise ValueError("There are no category values to chart.")
            result = counts.rename("Result").rename_axis(x_field).reset_index()
            result = _top_with_other(result, x_field)
            return result, {"x": x_field, "y": "Result", "title": f"Record count by {x_field}", "note": "This counts rows; it does not measure sales or value."}
        y = "__record_count__"
        working = frame[[x_field]].copy()
        working[y] = 1
        aggregation = "Record count"
    else:
        numeric, _, _ = get_field_types(frame)
        if y_field not in numeric:
            raise ValueError("Choose a numeric field to measure, or select record count.")
        if aggregation not in AGGREGATIONS or aggregation in {"Record count", "Distinct count"}:
            if aggregation == "Distinct count":
                pass
            else:
                raise ValueError("Choose a supported calculation.")
        working = frame[[x_field, y_field]].copy()
        y = y_field

    if chart_type in {"line", "area"}:
        frequency = {"Day": "D", "Week": "W-SUN", "Month": "M", "Quarter": "Q", "Year": "Y"}.get(date_grain)
        if frequency is None:
            raise ValueError("Choose a supported date grouping.")
        working[x_field] = pd.to_datetime(working[x_field], errors="coerce").dt.to_period(frequency).dt.start_time

    working = working.dropna(subset=[x_field])
    if y_field is not None:
        working = working.dropna(subset=[y])
    if working.empty:
        raise ValueError("There are no usable values for this chart.")
    if y_field is None:
        grouped = working.groupby(x_field, dropna=False)[y].sum()
    elif aggregation == "Distinct count":
        grouped = working.groupby(x_field, dropna=False)[y].nunique()
    else:
        operations = {"Sum": "sum", "Average": "mean", "Median": "median", "Minimum": "min", "Maximum": "max", "Record count": "count"}
        operation = operations.get(aggregation)
        if operation is None:
            raise ValueError("Choose a supported calculation.")
        grouped = working.groupby(x_field, dropna=False)[y].agg(operation)
    result = grouped.rename("Result").reset_index()
    if result.empty:
        raise ValueError("This chart has no results to display.")
    if chart_type in {"bar", "pie"}:
        result = result.sort_values("Result", ascending=False).head(10 if chart_type == "pie" else max(1, min(50, int(top_n))))
        if chart_type == "pie":
            # Keep the tail total so chart slices still represent the full data.
            full = grouped.rename("Result").reset_index().sort_values("Result", ascending=False).reset_index(drop=True)
            result = _top_with_other(full, x_field)
    else:
        result = result.sort_values(x_field)
    label = "records" if y_field is None else f"{aggregation.lower()} {y_field}"
    title = f"{label.title()} by {x_field}"
    return result.reset_index(drop=True), {"x": x_field, "y": "Result", "title": title, "note": f"Calculated as {label} for each {x_field} group."}


def suggest_charts(frame: pd.DataFrame) -> list[dict]:
    """Suggest charts only when the detected columns and value counts are suitable."""
    numeric, categories, dates = get_field_types(frame)
    suggestions: list[dict] = []
    if not numeric:
        if categories:
            category = categories[0]
            data, meta = build_chart(frame, "bar", category)
            suggestions.append({"type": "bar", "data": data, **meta})
        return suggestions

    if dates:
        metric = next((col for col in numeric if any(word in _clean_name(col) for word in ("revenue", "sales", "profit", "quantity", "amount"))), numeric[0])
        agg = _default_aggregation(metric)
        data, meta = build_chart(frame, "line", dates[0], metric, agg, date_grain="Month")
        if len(data) > 1:
            suggestions.append({"type": "line", "data": data, **meta})

    if categories:
        category = next((col for word in ("product", "brand", "category", "region", "country", "store", "type") for col in categories if word in _clean_name(col)), categories[0])
        metric = next((col for col in numeric if any(word in _clean_name(col) for word in ("revenue", "sales", "profit", "quantity", "amount"))), numeric[0])
        agg = _default_aggregation(metric)
        data, meta = build_chart(frame, "bar", category, metric, agg, top_n=12)
        if len(data) > 1:
            suggestions.append({"type": "bar", "data": data, **meta})

    if categories and 2 <= frame[categories[0]].nunique(dropna=True) <= 6:
        category = categories[0]
        data, meta = build_chart(frame, "pie", category)
        if len(data) > 1:
            suggestions.append({"type": "pie", "data": data, **meta})
    elif len(numeric) >= 2:
        x, y = numeric[:2]
        data, meta = build_chart(frame, "scatter", x, y)
        suggestions.append({"type": "scatter", "data": data, **meta})

    if numeric:
        data, meta = build_chart(frame, "histogram", numeric[0], bins=12)
        suggestions.append({"type": "histogram", "data": data, **meta})
    return suggestions[:4]


def suggest_calculations(frame: pd.DataFrame, limit: int = 4) -> list[str]:
    """Create clickable calculation examples from fields in the current table."""
    numeric, categories, _ = get_field_types(frame)
    if not numeric:
        return []
    ideas: list[str] = []
    for metric in numeric[:2]:
        ideas.extend([f"What is the total {metric}?", f"What is the average {metric}?"])
    if categories:
        metric = next(
            (col for word in ("revenue", "sales", "profit", "quantity", "amount", "price") for col in numeric if word in _clean_name(col)),
            numeric[0],
        )
        category = next(
            (col for word in ("product", "brand", "category", "region", "country", "group", "type") for col in categories if word in _clean_name(col)),
            categories[0],
        )
        ideas.insert(0, f"What is the average {metric} by {category}?")
    return list(dict.fromkeys(ideas))[:max(1, limit)]
