# BizScope

**See Your Business Clearly.**

BizScope is a Streamlit application for exploring many kinds of tabular data, including business, survey, education, research, and public datasets. Pandas performs calculations and charts locally; an optional Google Gemini assistant interprets questions and explains supported results in plain language.

## Features

- Upload multiple CSV files and Excel workbooks (`.xlsx`). Each CSV and each workbook sheet becomes a selectable table.
- Inspect data previews, column types, missing values, duplicate rows, and summary statistics.
- Get chart suggestions based on detected fields, then build bar, pie, line, area, histogram, or scatter charts by selecting the fields and calculation. Suggested charts are local Pandas calculations; identifiers are excluded from measures and pie charts combine smaller categories into “Other categories.”
- Recognize common currency-formatted price and amount fields (for example, `$1,250.00`) when most values can be parsed safely.
- Ignore a CSV's accidental saved row-number column when it is a verified sequential `Unnamed: 0` index; compare requests such as “Which brand is cheapest?” use average numeric price by brand and explain that basis.
- Ask questions in everyday language and receive a calculated answer, a data finding, and practical ideas to consider.
- In Ask BizScope, see which numeric fields can be calculated and get clickable calculation examples generated from available measures and category fields. Chart requests belong in Visualize.
- Receive cautious improvement suggestions grounded in the selected data, such as blank fields to review, unusually concentrated totals, recorded profit margin, or zero/negative stock.
- Ask “Analyze this data and give suggestions” for a local overview of totals, group comparisons, data quality, and possible next checks.
- Analyze numeric columns with sum, average, median, minimum, maximum, and count, grouped by any other column.
- Visualize grouped results with bar, line, area, pie, and scatter charts.
- Ask BizScope for a chart or a recommended business comparison in everyday language. It matches the request to available columns and calculates chart values locally with Pandas. If the table does not contain the fields requested, it explains what is missing instead of guessing a number.
- Join two tables using a shared key such as `Product_ID`, and inspect match counts. A warning appears when join keys repeat in the related table.
- Prepare a downloadable working copy by trimming or changing text capitalization, finding and replacing exact text values, removing fully empty or duplicate rows, filling missing values using clear options, converting a column to number/date/text, renaming columns, and removing unneeded columns. The uploaded source is not modified; conversions that cannot be read are counted as missing and called out for review.
- After preparation, BizScope switches to a selectable prepared copy. Overview suggestions, charts, and analysis use the selected copy; the original stays available in the table selector.
- Suggested workflow: inspect tables, prepare the source fields and matching IDs, connect related tables, then prepare the joined copy if needed before visualizing and asking questions. Download when the result is ready.
- Download the current or cleaned table as CSV and download a Markdown analysis report.

## Answer quality and chart requests

Pandas performs the calculations; Gemini can choose from the app's supported operations and explain the returned result. The app validates chosen fields and shows the calculation table. When the requested measure or grouping is ambiguous, it asks for clarification instead of choosing the first numeric column. If Gemini is unavailable, BizScope does not substitute a guessed answer for an AI request.

Use the Visualize tab to see chart ideas based on the selected table, or build a bar, pie, line, area, histogram, or scatter chart by choosing fields. BizScope uses fields available in that table. If a required field is missing or ambiguous, choose another field or prepare the data first. Charts use local Pandas calculations and do not rely on Gemini to invent values.

## Optional AI assistant

Customers do not enter API keys. The site owner configures the key on the server. For local development, create `.streamlit/secrets.toml` with:

```toml
GEMINI_API_KEY = "paste-your-key-here"
```

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/api-keys). Restart Streamlit after adding the key. The secrets file is excluded by `.gitignore`; never commit it. An environment variable named `GEMINI_API_KEY` is also supported. Users must accept the in-app data-sharing notice before an AI request. Without a server key or internet access, the app falls back to simple local question matching. The Gemini integration uses Python's standard library, so it does not add another package to install.

For each AI-assisted question, BizScope sends the question and table column names/types to Gemini. Gemini chooses from a fixed set of supported calculations; Pandas performs the calculation locally. BizScope then sends the calculated summary values to Gemini for a plain-language explanation. It does not send the full uploaded rows. API access and usage limits are managed in your Google AI Studio project. Requests use Gemini's stateless Interactions API mode (`store: false`).

## Run on Windows

Open this folder in VS Code, then open a PowerShell terminal in the folder containing `app.py`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell blocks environment activation, use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Using multiple tables

Put each table in its own CSV, or place tables on separate sheets in one `.xlsx` workbook. Upload the files together. Choose a table in the sidebar. To analyze a transaction table together with a product or manager table, open **Combine tables**, select the two tables, and join on their shared ID column. After creating the joined table, select **Joined table** in the sidebar.

Keep one header row at the top of every table. Use stable keys (for example, one `Product_ID` per product) and check the match count after joining. Repeated keys on the related side can multiply transaction rows, so the app warns when it detects them.

## Supported analysis

The AI assistant can interpret a broad range of questions, but it is limited to supported operations and available columns. The exact calculation is shown in the app and is performed in Pandas. The local fallback uses simple matching and may need the question phrased more directly.

For example, a transaction table with `Product_ID` and numeric `Quantity` can answer quantity by product. Revenue analysis requires a numeric revenue/amount column, or a product table with prices that can be joined to transaction rows. A monthly trend requires a date column and a numeric measure.

## Project structure

```text
BizScope/
├── app.py
├── bizscope/
│   ├── __init__.py
│   ├── data.py
│   └── gemini.py
├── .streamlit/
│   └── config.toml
├── requirements.txt
└── README.md
```

Uploaded files are processed in the running app session. This starter app has no user accounts, database, or cloud storage. The optional Gemini connection is enabled only after the site owner configures a key and the user accepts the data-sharing notice. Exported reports are Markdown; PDF export can be added separately.
