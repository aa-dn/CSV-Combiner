import streamlit as st
import pandas as pd

st.set_page_config(page_title="CSV Combiner", layout="wide")
st.title("CSV Combiner")
st.write("Combine CSV files with different layouts — map columns from each file into shared output categories, then download.")

# ── Category definitions ───────────────────────────────────────────────────────
CATEGORIES = [
    {"key": "date",      "label": "Date",      "synonyms": ["date","Date","DATE","created_at","created","timestamp","published","published_at","pub_date","datetime","publication_date","publishedAt","Published Date"]},
    {"key": "url",       "label": "URL",        "synonyms": ["url","URL","Url","link","Link","href","source_url","webpage","web_url","article_url","page_url"]},
    {"key": "full text", "label": "Full Text",  "synonyms": ["full text","Full Text","fulltext","full_text","text","Text","body","Body","content","Content","article","article_body","description","Description"]},
    {"key": "author",    "label": "Author",     "synonyms": ["author","Author","authors","Authors","byline","Byline","writer","creator","by","Author Name"]},
    {"key": "title",     "label": "Title",      "synonyms": ["title","Title","headline","Headline","heading","Heading","name","Name","subject","Subject"]},
    {"key": "source",    "label": "Source",     "synonyms": ["source","Source","publication","publisher","Publisher","outlet","domain","site","publication_name","Source Name"]},
    {"key": "language",  "label": "Language",   "synonyms": ["language","Language","lang","locale","Locale"]},
    {"key": "category",  "label": "Category",   "synonyms": ["category","Category","categories","Categories","tag","tags","Tags","topic","Topic","section","Section","type","Type"]},
    {"key": "sentiment", "label": "Sentiment",  "synonyms": ["sentiment","Sentiment","tone","Tone","polarity","emotion","score"]},
    {"key": "country",   "label": "Country",    "synonyms": ["country","Country","nation","Nation","region","geography","location","geo"]},
    {"key": "id",        "label": "ID",         "synonyms": ["id","ID","Id","identifier","uid","uuid","_id","article_id","doc_id"]},
    {"key": "summary",   "label": "Summary",    "synonyms": ["summary","Summary","abstract","Abstract","excerpt","Excerpt","snippet","description","teaser","lead"]},
]
DEFAULT_KEYS = ["date", "url", "full text"]
CAT_MAP = {c["key"]: c for c in CATEGORIES}


def find_best_match(category_key, file_cols):
    """Return the best matching column name from file_cols for a given category."""
    if not file_cols:
        return ""
    cat = CAT_MAP.get(category_key)
    if not cat:
        return ""
    for syn in cat["synonyms"]:
        if syn in file_cols:
            return syn
    lower_cols = {c.lower(): c for c in file_cols}
    for syn in cat["synonyms"]:
        if syn.lower() in lower_cols:
            return lower_cols[syn.lower()]
    for col in file_cols:
        if category_key.lower() in col.lower():
            return col
    return ""


def read_df(file, skip_rows, header_rows):
    header_arg = list(range(header_rows)) if header_rows > 1 else (0 if header_rows == 1 else None)
    file.seek(0)
    try:
        return pd.read_csv(file, skiprows=skip_rows, header=header_arg)
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, skiprows=skip_rows, header=header_arg, encoding="latin-1")


def flat_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        return list(df.columns.get_level_values(-1))
    return list(df.columns)


# ── Upload ─────────────────────────────────────────────────────────────────────
uploaded_files = st.file_uploader("Upload CSV files", type="csv", accept_multiple_files=True)
if not uploaded_files:
    st.info("Upload two or more CSV files to get started.")
    st.stop()
if len(uploaded_files) < 2:
    st.warning("Upload at least two CSV files to combine.")
    st.stop()

# ── Step 1: Configure headers ──────────────────────────────────────────────────
st.divider()
st.subheader("Step 1 — Configure headers")
st.caption("**Skip rows** are ignored entirely. **Header rows** contain column names used to auto-populate dropdowns in Step 2.")

file_configs, all_file_cols = {}, {}
for f in uploaded_files:
    key = f.name
    skip_key = f"skip_{key}"
    heads_key = f"heads_{key}"

    # Initialize session state defaults before widget render
    if skip_key not in st.session_state:
        st.session_state[skip_key] = 0
    if heads_key not in st.session_state:
        st.session_state[heads_key] = 1

    with st.expander(f"**{f.name}**  ({f.size/1024:.1f} KB)", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Rows to skip", min_value=0, key=skip_key)
        with c2:
            st.number_input("Header rows", min_value=0, key=heads_key)

        cfg = {"skip_rows": int(st.session_state[skip_key]), "header_rows": int(st.session_state[heads_key])}
        file_configs[key] = cfg
        try:
            df_tmp = read_df(f, cfg["skip_rows"], cfg["header_rows"])
            cols = flat_columns(df_tmp)
            all_file_cols[key] = cols
            df_tmp.columns = cols
            detected = ", ".join(cols[:8]) + ("…" if len(cols) > 8 else "")
            st.caption(f"Preview — first 20 rows  |  {len(cols)} columns: {detected}")
            st.dataframe(df_tmp.head(20), use_container_width=True)
        except Exception as e:
            all_file_cols[key] = []
            st.error(f"Could not read: {e}")

# ── Step 2: Map columns ────────────────────────────────────────────────────────
st.divider()
st.subheader("Step 2 — Map columns to output categories")
st.caption(
    "Three output columns are pre-loaded. For each, the best matching source column in each file is auto-selected. "
    "Adjust any dropdown, rename the output column, or add more categories below."
)

any_headers = any(len(v) > 0 for v in all_file_cols.values())
if not any_headers:
    st.warning("No header rows detected. Set Header rows > 0 in Step 1 to enable column mapping.")
    st.stop()

# Session state for mapping IDs
if "mapping_ids" not in st.session_state:
    st.session_state.mapping_ids = []
    st.session_state.next_mid = 0

# Seed defaults on first load
if not st.session_state.mapping_ids:
    for cat_key in DEFAULT_KEYS:
        mid = st.session_state.next_mid
        st.session_state.next_mid += 1
        st.session_state.mapping_ids.append(mid)
        st.session_state[f"mname_{mid}"] = cat_key
        st.session_state[f"mcat_{mid}"] = cat_key
        for j, f in enumerate(uploaded_files):
            best = find_best_match(cat_key, all_file_cols.get(f.name, []))
            st.session_state[f"msrc_{mid}_{j}"] = best if best else "(skip)"

to_remove = None

for mid in list(st.session_state.mapping_ids):
    cat_key = st.session_state.get(f"mcat_{mid}", "")
    cat_info = CAT_MAP.get(cat_key)
    badge_label = cat_info["label"].upper() if cat_info else "CUSTOM"

    # Ensure mname key exists
    if f"mname_{mid}" not in st.session_state:
        st.session_state[f"mname_{mid}"] = cat_key

    with st.container(border=True):
        h1, h2, h3 = st.columns([1, 4, 1])
        with h1:
            st.markdown(f"**{badge_label}**")
        with h2:
            st.text_input("Output column name", key=f"mname_{mid}", label_visibility="collapsed", placeholder="output column name")
        with h3:
            if st.button("Remove", key=f"mdel_{mid}"):
                to_remove = mid

        n = len(uploaded_files)
        per_row = min(n, 4)
        for row_start in range(0, n, per_row):
            row_files = uploaded_files[row_start: row_start + per_row]
            cols_ui = st.columns(len(row_files))
            for ci, f in enumerate(row_files):
                fi = row_start + ci
                options = ["(skip)"] + all_file_cols.get(f.name, [])
                short = f.name[:20] + "…" if len(f.name) > 20 else f.name
                src_key = f"msrc_{mid}_{fi}"

                # Initialize with best match if not yet set
                if src_key not in st.session_state:
                    best = find_best_match(cat_key, all_file_cols.get(f.name, []))
                    st.session_state[src_key] = best if best else "(skip)"

                # Ensure current value is still valid
                if st.session_state[src_key] not in options:
                    st.session_state[src_key] = "(skip)"

                with cols_ui[ci]:
                    st.selectbox(short, options, key=src_key)

if to_remove is not None:
    if len(st.session_state.mapping_ids) > 1:
        st.session_state.mapping_ids.remove(to_remove)
    st.rerun()

# Add category section
st.write("")
used_keys = [st.session_state.get(f"mcat_{mid}", "") for mid in st.session_state.mapping_ids]
available_cats = [c for c in CATEGORIES if c["key"] not in used_keys]

if available_cats:
    add_col1, add_col2 = st.columns([3, 1])
    with add_col1:
        chosen = st.selectbox(
            "Add category",
            options=[c["key"] for c in available_cats],
            format_func=lambda k: CAT_MAP[k]["label"],
            key="add_cat_select",
            label_visibility="collapsed",
        )
    with add_col2:
        if st.button("+ Add category"):
            mid = st.session_state.next_mid
            st.session_state.next_mid += 1
            st.session_state.mapping_ids.append(mid)
            st.session_state[f"mcat_{mid}"] = chosen
            st.session_state[f"mname_{mid}"] = chosen
            for j, f in enumerate(uploaded_files):
                best = find_best_match(chosen, all_file_cols.get(f.name, []))
                st.session_state[f"msrc_{mid}_{j}"] = best if best else "(skip)"
            st.rerun()
else:
    st.caption("All available categories have been added.")

# ── Step 3: Combine ────────────────────────────────────────────────────────────
st.divider()
st.subheader("Step 3 — Combine & download")

if "output_filename" not in st.session_state:
    st.session_state["output_filename"] = "combined.csv"

st.text_input("Output filename", key="output_filename")


def get_mappings():
    result = []
    for mid in st.session_state.mapping_ids:
        name = st.session_state.get(f"mname_{mid}", "").strip()
        sources = {}
        for j, f in enumerate(uploaded_files):
            src = st.session_state.get(f"msrc_{mid}_{j}", "(skip)")
            sources[f.name] = "" if src == "(skip)" else src
        result.append({"output_name": name, "sources": sources, "mid": mid})
    return result


mappings = get_mappings()
valid = [m for m in mappings if m["output_name"]]

# Summary table
if valid:
    rows = []
    for m in valid:
        row = {"Output column": m["output_name"]}
        for f in uploaded_files:
            short = f.name[:18] + "…" if len(f.name) > 18 else f.name
            row[short] = m["sources"].get(f.name) or "(skip)"
        rows.append(row)
    st.caption("Mapping summary:")
    st.dataframe(pd.DataFrame(rows).set_index("Output column"), use_container_width=True)

if not valid:
    st.warning("All output columns need a name to continue.")

if st.button("Combine & Download", disabled=not valid):
    dfs, errors = [], []
    ref_cols = [m["output_name"] for m in valid]

    for f in uploaded_files:
        cfg = file_configs[f.name]
        try:
            df = read_df(f, cfg["skip_rows"], cfg["header_rows"])
            df.columns = flat_columns(df)
            out = {}
            for m in valid:
                src = m["sources"].get(f.name, "")
                out[m["output_name"]] = df[src].values if src and src in df.columns else ""
            dfs.append((f.name, pd.DataFrame(out)))
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    for err in errors:
        st.error(err)

    if dfs:
        combined = pd.concat([df for _, df in dfs], ignore_index=True)
        st.subheader("Row counts")
        for name, df in dfs:
            st.write(f"- **{name}**: {len(df):,} rows")
        st.write(f"**Total: {len(combined):,} rows — {len(ref_cols)} output column{'s' if len(ref_cols)!=1 else ''}**")

        fname = st.session_state["output_filename"].strip() or "combined.csv"
        if not fname.lower().endswith(".csv"):
            fname += ".csv"
        st.download_button(
            "Download combined CSV",
            data=combined.to_csv(index=False).encode("utf-8-sig"),
            file_name=fname,
            mime="text/csv",
        )
