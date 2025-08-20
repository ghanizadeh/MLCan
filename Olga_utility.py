import streamlit as st
import pandas as pd
import re

# ==========================
# 1. Read .tab file into DataFrame
# ==========================
def read_tab_file(uploaded_file):
    content = uploaded_file.read().decode("utf-8")

    # --- Find the LAST COLUMNS= (...) block ---
    col_matches = re.findall(r"COLUMNS\s*=\s*\((.*?)\)", content, re.DOTALL)
    if not col_matches:
        raise ValueError("No COLUMNS header found in file")
    cols_text = col_matches[-1]  # ✅ use the last one
    cols = re.split(r"[\s,]+", cols_text.strip())  # split on space/comma

    # --- Extract PVTTABLE POINT rows (after last COLUMNS) ---
    # Only keep the content after the last "COLUMNS"
    content_after_cols = content[content.rfind("COLUMNS"):]
    data = re.findall(r"PVTTABLE POINT\s*=\s*\((.*?)\)", content_after_cols, re.DOTALL)

    rows = []
    for row in data:
        # split on commas, strip spaces/tabs
        values = [x.strip() for x in row.replace("\n", " ").split(",") if x.strip()]
        values = [float(x) for x in values]
        rows.append(values)

    # sanity check
    for i, r in enumerate(rows):
        if len(r) != len(cols):
            raise ValueError(f"Row {i} has {len(r)} values but expected {len(cols)}")

    df = pd.DataFrame(rows, columns=cols)
    return df, cols, content

# ==========================
# 2. Save DataFrame back to .tab format
# ==========================
def save_tab_file(df, cols, original_content):
    """
    Replace only PVTTABLE POINT = (...) blocks in the original file with updated values from df.
    """
    new_content = original_content

    # Regex to capture each PVTTABLE POINT block
    pattern = r"(PVTTABLE POINT\s*=\s*\()(.*?)(\))"

    matches = list(re.finditer(pattern, original_content, re.DOTALL))
    if len(matches) != len(df):
        raise ValueError(f"Row mismatch: file has {len(matches)} PVTTABLE POINTs, df has {len(df)} rows")

    for i, match in enumerate(matches):
        # Format row with same scientific style
        row = df.iloc[i].values
        formatted = ",".join([f"{val:.6E}" for val in row])
        # Replace only the numbers inside parentheses
        new_block = f"{match.group(1)}{formatted}{match.group(3)}"
        new_content = new_content.replace(match.group(0), new_block, 1)

    return new_content



# ==========================
# 3. Streamlit App
# ==========================
st.set_page_config(page_title="PVT Table Editor", layout="wide")
st.title("PVT Table Editor")

uploaded_file = st.file_uploader("Upload .tab File", type=["tab"])

if uploaded_file:
    df, columns, content = read_tab_file(uploaded_file)

    st.write("### Original Data Preview")
    st.dataframe(df)

    # Multiselect
    selected_cols = st.multiselect("Select columns to edit:", columns)

    new_values = {}
    for col in selected_cols:
        val = st.text_input(f"Enter new value for {col}:", value="")
        if val.strip():
            try:
                new_values[col] = float(val)
            except:
                st.error(f"Invalid number for {col}")

    if st.button("Apply Changes"):
        for col, val in new_values.items():
            df[col] = val
        st.success("Values updated!")

        st.write("### Updated Data")
        st.dataframe(df)

        # Export to .tab
        tab_text = save_tab_file(df, columns, content)

        st.download_button(
            "Download Updated .tab",
            data=tab_text,
            file_name="updated_pvt.tab",
            mime="text/plain"
        )

