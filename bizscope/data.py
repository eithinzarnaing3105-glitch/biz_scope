from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath

import pandas as pd


def read_uploaded_tables(files) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Read CSVs and every sheet in XLSX workbooks into named tables."""
    tables: dict[str, pd.DataFrame] = {}
    issues: list[str] = []

    for uploaded in files:
        filename = PurePosixPath(uploaded.name.replace("\\", "/")).name
        suffix = PurePosixPath(filename).suffix.lower()
        try:
            raw = uploaded.getvalue()
            if suffix == ".csv":
                try:
                    frame = pd.read_csv(BytesIO(raw), sep=None, engine="python", encoding="utf-8-sig")
                except UnicodeDecodeError:
                    frame = pd.read_csv(BytesIO(raw), sep=None, engine="python", encoding="latin-1")
                tables[_unique_name(filename, tables)] = _tidy_headers(frame)
            elif suffix == ".xlsx":
                excel = pd.ExcelFile(BytesIO(raw), engine="openpyxl")
                if not excel.sheet_names:
                    issues.append(f"{filename}: workbook contains no sheets.")
                for sheet in excel.sheet_names:
                    frame = pd.read_excel(excel, sheet_name=sheet)
                    name = f"{PurePosixPath(filename).stem} · {sheet}"
                    tables[_unique_name(name, tables)] = _tidy_headers(frame)
            else:
                issues.append(f"{filename}: unsupported format. Use CSV or XLSX.")
        except Exception as exc:  # surface file-specific errors in the UI
            issues.append(f"{filename}: could not be read ({exc}).")

    return tables, issues


def _unique_name(name: str, existing: dict[str, pd.DataFrame]) -> str:
    candidate = name
    number = 2
    while candidate in existing:
        candidate = f"{name} ({number})"
        number += 1
    return candidate


def _tidy_headers(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(col).strip() or f"Column {i + 1}" for i, col in enumerate(result.columns)]
    # Drop only the common CSV-saved index artifact, and only when its values
    # exactly match row numbers. Keep meaningful columns that happen to start
    # with "Unnamed" or contain other values.
    for column in list(result.columns):
        if str(column).strip().lower() in {"unnamed: 0", "unnamed 0"}:
            values = pd.to_numeric(result[column], errors="coerce")
            expected = pd.Series(range(len(result)), index=result.index, dtype="float64")
            expected_one_based = pd.Series(range(1, len(result) + 1), index=result.index, dtype="float64")
            if values.notna().all() and (values.astype("float64").equals(expected) or values.astype("float64").equals(expected_one_based)):
                result = result.drop(columns=[column])
    for column in result.columns:
        label = str(column).lower()
        if any(token in label for token in ("date", "datetime", "timestamp", "time")):
            parsed = pd.to_datetime(result[column], errors="coerce")
            nonempty = int(result[column].notna().sum())
            if nonempty and int(parsed.notna().sum()) / nonempty >= 0.8:
                result[column] = parsed
        elif any(token in label for token in ("price", "cost", "amount", "revenue", "sales", "profit", "value", "msrp", "quantity", "units", "stock")) and not pd.api.types.is_numeric_dtype(result[column]):
            values = result[column].astype("string").str.strip()
            values = values.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
            values = values.str.replace(r"[^0-9eE.+-]", "", regex=True)
            parsed = pd.to_numeric(values, errors="coerce")
            nonempty = int(result[column].notna().sum())
            if nonempty and int(parsed.notna().sum()) / nonempty >= 0.8:
                result[column] = parsed
        elif label == "year" or (label.isdigit() and len(label) == 4 and 1800 <= int(label) <= 2100):
            values = result[column].astype("string").str.replace(",", "", regex=False)
            parsed = pd.to_numeric(values, errors="coerce")
            nonempty = int(result[column].notna().sum())
            if nonempty and int(parsed.notna().sum()) / nonempty >= 0.8:
                result[column] = parsed
    return result


def profile_table(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Column": frame.columns,
            "Data type": [str(frame[col].dtype) for col in frame.columns],
            "Filled values": [int(frame[col].notna().sum()) for col in frame.columns],
            "Missing": [int(frame[col].isna().sum()) for col in frame.columns],
            "Unique values": [int(frame[col].nunique(dropna=True)) for col in frame.columns],
        }
    )


def summarize_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.shape[1] == 0:
        return pd.DataFrame()
    return frame.describe(include="all").transpose()


def aggregate_table(
    frame: pd.DataFrame,
    metric: str,
    operation: str,
    dimension: str | None = None,
    ascending: bool = False,
) -> pd.DataFrame:
    """Perform a constrained Pandas aggregation; never evaluates generated code."""
    if metric not in frame.columns:
        raise ValueError("Choose a valid metric column.")
    operations = {
        "Sum": "sum", "Average": "mean", "Median": "median", "Minimum": "min",
        "Maximum": "max", "Count": "count", "Distinct count": "nunique",
    }
    if operation not in operations:
        raise ValueError("Choose a supported calculation.")
    method = operations[operation]
    series = frame[metric]
    if method not in ("count", "nunique") and not pd.api.types.is_numeric_dtype(series):
        raise ValueError(f"{metric} must be numeric for {operation.lower()}.")
    if dimension and dimension not in frame.columns:
        raise ValueError("Choose a valid grouping column.")

    if dimension:
        if method in ("count", "nunique"):
            result = frame.groupby(dimension, dropna=False)[metric].agg(method).rename("Result").reset_index()
        else:
            result = frame.groupby(dimension, dropna=False)[metric].agg(method).rename("Result").reset_index()
        return result.sort_values("Result", ascending=ascending, na_position="last").reset_index(drop=True)

    value = series.count() if method == "count" else getattr(series, method)()
    return pd.DataFrame({"Metric": [metric], "Calculation": [operation], "Result": [value]})


def run_planned_analysis(frame: pd.DataFrame, plan: dict) -> tuple[pd.DataFrame, str | None, str]:
    """Validate an AI/local plan, then run only an allowed Pandas aggregation."""
    operation_names = {
        "sum": "Sum",
        "average": "Average",
        "median": "Median",
        "minimum": "Minimum",
        "maximum": "Maximum",
        "count": "Count",
        "distinct_count": "Distinct count",
    }
    raw_operation = str(plan.get("operation", "")).lower()
    if raw_operation not in operation_names:
        raise ValueError("That calculation is not supported yet.")
    operation = operation_names[raw_operation]
    metric = plan.get("metric")
    if metric not in frame.columns:
        raise ValueError("I couldn't match the requested measure to a column in this table.")
    if operation not in ("Count", "Distinct count") and not pd.api.types.is_numeric_dtype(frame[metric]):
        raise ValueError(f"{metric} is not numeric, so BizScope cannot calculate {operation.lower()} for it.")

    group_by = plan.get("group_by")
    if group_by is not None and group_by not in frame.columns:
        raise ValueError("I couldn't match the requested category to a column in this table.")

    working = frame
    display_group = group_by
    grain = str(plan.get("time_grain", "none")).lower()
    if group_by and grain != "none":
        if not pd.api.types.is_datetime64_any_dtype(frame[group_by]):
            raise ValueError(f"{group_by} is not recognized as a date column. Check its format in Your data.")
        frequency = {"day": "D", "week": "W-SUN", "month": "M", "quarter": "Q", "year": "Y"}.get(grain)
        if frequency is None:
            raise ValueError("That date grouping is not supported yet.")
        working = frame.copy()
        display_group = f"{group_by} ({grain.title()})"
        working[display_group] = frame[group_by].dt.to_period(frequency).dt.start_time

    ascending = str(plan.get("sort_order", "highest")).lower() == "lowest"
    result = aggregate_table(working, metric, operation, display_group, ascending=ascending)
    description = f"{operation.lower()} of {metric}"
    if display_group:
        description += f" by {display_group}"
    if group_by and grain != "none":
        description += f" ({grain} totals)"
    return result, display_group, description


def interpret_question(question: str, frame: pd.DataFrame) -> dict | None:
    """Interpret only questions that map clearly to fields in the table."""
    q = question.lower().replace("_", " ").replace("-", " ")
    numeric = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]

    def normalized(col) -> str:
        return " ".join(str(col).lower().replace("_", " ").replace("-", " ").split())

    def mentioned(col) -> bool:
        name = normalized(col)
        return bool(name) and name in q

    def preferred_label(candidates: list) -> object | None:
        if not candidates:
            return None
        descriptive = [
            col for col in candidates
            if any(token in normalized(col) for token in ("product name", "item name", "product description", "item description", "product title"))
        ]
        if descriptive:
            return descriptive[0]
        readable = [
            col for col in candidates
            if not any(token in normalized(col) for token in (" id", " code", " sku"))
        ]
        return readable[0] if readable else candidates[0]

    # A common plain-language business question: compare typical prices by
    # brand and identify the lowest average. Use the average, not the cheapest
    # individual listing, and say so in the resulting explanation.
    if any(word in q for word in ("cheapest", "most affordable", "lowest price", "least expensive")):
        price = next((col for col in numeric if any(token in normalized(col) for token in ("price", "msrp", "cost"))), None)
        brands = [
            col for col in frame.columns
            if any(token in normalized(col) for token in ("brand", "manufacturer", "make"))
            and col != price
        ]
        brand = next((col for col in brands if mentioned(col)), None) or preferred_label(brands)
        if price is not None and brand is not None:
            return {"metric": price, "dimension": brand, "operation": "Average", "ascending": True}

    # Transaction questions are counts of transactions, not sums of quantities.
    # Count distinct transaction IDs when available, grouped by the requested item field.
    transaction_words = ("transaction", "transactions", "order", "orders", "receipt", "receipts", "invoice", "invoices")
    if any(word in q for word in transaction_words) and any(word in q for word in ("most", "highest", "top", "least", "fewest", "lowest", "count", "number")):
        group_candidates = [
            c for c in frame.columns
            if any(token in str(c).lower().replace("_", " ") for token in ("product", "item", "sku", "category"))
        ]
        dimension = next((c for c in group_candidates if mentioned(c)), None)
        if dimension is None:
            requested_groups = []
            if "product" in q or "products" in q:
                requested_groups.append("product")
            if "item" in q or "items" in q:
                requested_groups.append("item")
            if "sku" in q:
                requested_groups.append("sku")
            if "categor" in q:
                requested_groups.append("category")
            matching_groups = [
                c for token in requested_groups
                for c in group_candidates if token in normalized(c)
            ]
            dimension = preferred_label(list(dict.fromkeys(matching_groups)))
        if dimension is None and len(group_candidates) == 1:
            dimension = group_candidates[0]
        if dimension is None and len(group_candidates) > 1 and not requested_groups:
            dimension = preferred_label(group_candidates)
        if dimension is None:
            return None
        transaction_id = next(
            (
                c for c in frame.columns
                if c != dimension
                and any(token in str(c).lower().replace("_", " ") for token in ("transaction id", "order id", "receipt id", "invoice id"))
            ),
            None,
        )
        metric = transaction_id or dimension
        operation = "Distinct count" if transaction_id else "Count"
        return {
            "metric": metric,
            "dimension": dimension,
            "operation": operation,
            "ascending": any(word in q for word in ("least", "fewest", "lowest")),
            "count_basis": "distinct transaction IDs" if transaction_id else "rows",
        }

    asks_most_sales = (
        any(word in q for word in ("sales", "sale", "sell", "sells", "sold", "selling"))
        and any(word in q for word in ("most", "highest", "top", "best", "more", "number", "count"))
        and not any(word in q for word in ("units", "quantity", "revenue", "amount", "price", "profit"))
    )
    has_numeric_sales_measure = any(
        pd.api.types.is_numeric_dtype(frame[col])
        and any(token in normalized(col) for token in ("sales", "revenue", "amount", "turnover"))
        for col in frame.columns
    )
    if asks_most_sales and not has_numeric_sales_measure:
        product_candidates = [
            col for col in frame.columns
            if any(token in normalized(col) for token in ("product name", "product", "item name", "item", "sku"))
        ]
        product_col = preferred_label(product_candidates)
        if product_col is not None:
            transaction_id = next(
                (
                    col for col in frame.columns
                    if col != product_col
                    and any(token in normalized(col) for token in ("transaction id", "order id", "receipt id", "invoice id"))
                ),
                None,
            )
            if transaction_id is not None:
                return {
                    "metric": transaction_id,
                    "dimension": product_col,
                    "operation": "Distinct count",
                    "ascending": False,
                    "count_basis": "distinct transaction IDs",
                }
            row_counts = frame[product_col].dropna().value_counts()
            if len(row_counts) > 1 and row_counts.iloc[0] != row_counts.iloc[-1]:
                return {
                    "metric": product_col,
                    "dimension": product_col,
                    "operation": "Count",
                    "ascending": False,
                    "count_basis": "rows",
                }

    if not numeric:
        return None

    exact_measures = [col for col in numeric if mentioned(col)]
    metric = exact_measures[0] if len(exact_measures) == 1 else None
    if len(exact_measures) > 1:
        return None

    semantic_measures = [
        (("population", "populated", "people"), ("population",)),
        (("revenue", "sales", "turnover", "income"), ("revenue", "sales", "amount", "turnover", "income")),
        (("profit", "margin"), ("net profit", "gross profit", "profit")),
        (("quantity", "units", "volume", "sold"), ("quantity", "units", "volume", "qty")),
        (("price", "prices", "cost", "msrp"), ("price", "cost", "msrp")),
        (("expense", "expenses"), ("expense", "expenses", "cost")),
    ]
    if metric is None:
        for question_terms, column_terms in semantic_measures:
            if any(term in q for term in question_terms):
                candidates = [
                    col for col in numeric
                    if any(term in normalized(col) for term in column_terms)
                    and not ("margin" in normalized(col) and "profit" in column_terms)
                ]
                if len(candidates) == 1:
                    metric = candidates[0]
                elif len(candidates) > 1:
                    # Prefer a clearly named total/primary measure over its subcomponents.
                    preferred = next((col for col in candidates if any(term in normalized(col) for term in column_terms[:2])), None)
                    metric = preferred if preferred is not None and sum(any(term in normalized(col) for term in column_terms[:2]) for col in candidates) == 1 else None
                if metric is not None:
                    break

    year_columns = [col for col in numeric if normalized(col).isdigit() and len(normalized(col)) == 4 and 1800 <= int(normalized(col)) <= 2100]
    if metric is None and any(word in q for word in ("population", "populated", "people")):
        if year_columns:
            requested = next((col for col in year_columns if normalized(col) in q), None)
            metric = requested or max(year_columns, key=lambda col: int(normalized(col)))
    if metric is None:
        # Do not invent a calculation by silently choosing the first numeric column.
        return None

    numeric_category_terms = ("class", "category", "group", "segment", "level", "status", "flag", "type")
    categorical = [
        c for c in frame.columns
        if c != metric and (
            pd.api.types.is_object_dtype(frame[c])
            or pd.api.types.is_string_dtype(frame[c])
            or str(frame[c].dtype) == "category"
            or pd.api.types.is_bool_dtype(frame[c])
            or (
                pd.api.types.is_numeric_dtype(frame[c])
                and any(term in str(c).lower().replace("_", " ") for term in numeric_category_terms)
                and 2 <= frame[c].nunique(dropna=True) <= 15
            )
        )
    ]
    exact_dimensions = [col for col in categorical if mentioned(col)]
    dimension = exact_dimensions[0] if len(exact_dimensions) == 1 else None
    if len(exact_dimensions) > 1:
        return None
    semantic_dimensions = [
        (("country", "countries", "nation"), ("country name", "country", "nation", "entity")),
        (("brand", "brands", "manufacturer", "make"), ("brand", "manufacturer", "make")),
        (("product", "products", "item", "items", "sku"), ("product name", "product", "item name", "item", "sku")),
        (("region", "area", "store", "location"), ("region", "area", "store", "location")),
        (("category", "categories", "type", "segment"), ("category", "type", "segment")),
        (("customer", "client"), ("customer", "client")),
    ]
    if dimension is None:
        for question_terms, column_terms in semantic_dimensions:
            if any(term in q for term in question_terms):
                candidates = [col for col in categorical if any(term in normalized(col) for term in column_terms)]
                if candidates:
                    dimension = preferred_label(candidates)
                    if dimension is not None:
                        break

    grouped_intent = any(word in q for word in ("by", "which", "most", "least", "highest", "lowest", "top", "best", "worst"))
    if dimension is None and grouped_intent:
        if len(categorical) == 1:
            dimension = categorical[0]
        elif len(categorical) > 1:
            return None

    if any(word in q for word in ("average", "mean", "avg")):
        operation = "Average"
    elif "median" in q:
        operation = "Median"
    elif any(word in q for word in ("count", "number of")):
        operation = "Count"
    elif any(word in q for word in ("minimum", "smallest", "lowest", "maximum", "largest", "highest")):
        if dimension and any(term in normalized(metric) for term in ("price", "cost", "msrp")):
            operation = "Maximum" if any(term in q for term in ("maximum", "largest", "highest")) else "Minimum"
        else:
            operation = "Sum" if dimension else ("Minimum" if any(term in q for term in ("minimum", "smallest", "lowest")) else "Maximum")
    elif any(word in q for word in ("most", "top", "best", "worst", "least", "fewest")):
        if any(term in normalized(metric) for term in ("price", "cost", "msrp")) and dimension:
            operation = "Average"
        else:
            operation = "Sum"
    elif any(word in q for word in ("total", "sum", "overall")):
        operation = "Sum"
    else:
        return None

    return {
        "metric": metric,
        "dimension": dimension,
        "operation": operation,
        "ascending": any(word in q for word in ("lowest", "minimum", "smallest", "least", "worst")),
    }


def clean_table(
    frame: pd.DataFrame,
    trim_text: bool,
    drop_empty: bool,
    drop_duplicates: bool,
    fill_numeric: bool,
    fill_text: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    cleaned = frame.copy()
    before_rows = len(cleaned)
    before_missing = int(cleaned.isna().sum().sum())
    if trim_text:
        for column in cleaned.select_dtypes(include=["object", "string"]).columns:
            cleaned[column] = cleaned[column].map(lambda value: value.strip() if isinstance(value, str) else value)
    if drop_empty:
        cleaned = cleaned.dropna(how="all")
    if drop_duplicates:
        cleaned = cleaned.drop_duplicates()
    if fill_numeric:
        for column in cleaned.select_dtypes(include="number").columns:
            if cleaned[column].isna().any():
                cleaned[column] = cleaned[column].fillna(cleaned[column].median())
    if fill_text:
        for column in cleaned.select_dtypes(include=["object", "string", "category"]).columns:
            if cleaned[column].isna().any() and not cleaned[column].mode(dropna=True).empty:
                cleaned[column] = cleaned[column].fillna(cleaned[column].mode(dropna=True).iloc[0])
    return cleaned, {
        "rows_removed": before_rows - len(cleaned),
        "missing_filled": before_missing - int(cleaned.isna().sum().sum()),
    }
