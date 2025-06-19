import streamlit as st
import pandas as pd
import os
import csv
import requests
from datetime import datetime

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def process_csv(file_path: str) -> str:
    df = pd.read_csv(file_path)

    if 'chain_info.chain' in df.columns:
        df = df[~df['chain_info.chain'].astype(str).str.upper().eq('TRUE')]

    base_columns = {
        'LinkedIn': 'linkedin',
        'Name': 'name_for_emails',
        'Website': 'site',
        'Type': 'type',
        'City': 'city',
        'Zip': 'postal_code',
        'State': 'state'
    }

    email_blocks = [
        {
            'Email': 'email_1',
            'Phone': 'email_1_phone',
            'Full Name': 'email_1_full_name',
            'First Name': 'email_1_first_name',
            'Last Name': 'email_1_last_name'
        },
        {
            'Email': 'email_2',
            'Phone': 'email_2_phone',
            'Full Name': 'email_2_full_name',
            'First Name': 'email_2_first_name',
            'Last Name': 'email_2_last_name'
        },
        {
            'Email': 'email_3',
            'Phone': 'email_3_phone',
            'Full Name': 'email_3_full_name',
            'First Name': 'email_3_first_name',
            'Last Name': 'email_3_last_name'
        }
    ]

    all_rows = []
    for _, row in df.iterrows():
        base = {k: row.get(v, "") for k, v in base_columns.items()}
        for block in email_blocks:
            contact = {k: row.get(v, "") for k, v in block.items()}
            if contact['Email']:
                combined = {**base, **contact}
                all_rows.append(combined)

    output_df = pd.DataFrame(all_rows)

    output_df = output_df[[
        'LinkedIn', 'Name', 'Website', 'Type', 'City', 'Zip', 'State',
        'Email', 'Phone', 'Full Name', 'First Name', 'Last Name'
    ]]
    output_df.rename(columns={'Name': 'Company Name'}, inplace=True)

    output_df = output_df[~output_df['Company Name'].str.lower().eq('unknown')]
    output_df = output_df[~output_df['First Name'].str.lower().eq('unknown')]

    block_keywords = [
        '.gov', '.ca', '.org', 'legal', 'law', 'home depot', 'lowes',
        'cvs', 'walgreens', 'pfizer', 'petco', 'roto rooter', 'salvation'
    ]
    pattern = '|'.join(block_keywords)

    output_df = output_df[output_df['Email'].notna()]
    output_df = output_df[output_df['Email'].str.strip() != ""]
    output_df = output_df[~output_df['Email'].str.lower().str.contains(pattern, na=False)]

    output_df['First Name'] = (
        output_df['First Name']
        .fillna('')
        .astype(str)
        .str.strip()
        .str.replace(r',$', '', regex=True)
        .str.replace(r'\?', '', regex=True)
        .replace('nan', '')
    )
    output_df.loc[output_df['First Name'].str.len() == 1, 'First Name'] = ""

    processed_path = file_path.replace(".csv", "_processed.csv")
    output_df.to_csv(processed_path, index=False)
    return processed_path

def push_csv_to_clay(file_path: str, webhook_url: str):
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        success_count = 0
        for row in reader:
            try:
                res = requests.post(webhook_url, json=row, timeout=10)
                res.raise_for_status()
                success_count += 1
            except Exception as e:
                st.error(f"Row failed: {row}\nError: {e}")
        return success_count

def load_processed_files():
    files = []
    for filename in sorted(os.listdir(UPLOAD_DIR), key=lambda f: os.path.getmtime(os.path.join(UPLOAD_DIR, f)), reverse=True):
        if filename.endswith("_processed.csv"):
            path = os.path.join(UPLOAD_DIR, filename)
            row_count = sum(1 for _ in open(path)) - 1
            modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            files.append({"name": filename, "rows": row_count, "modified": modified, "path": path})
    return files

def delete_file(path):
    os.remove(path)

st.set_page_config(page_title="Munera Capital CSV Processor", layout="wide")
st.image(os.path.join(os.path.dirname(__file__), "munera_logo.png"), width=200)

st.title("📤 Upload & Process CSV Files")

file_name = st.text_input("Enter a name for this file (required):")
uploaded_file = st.file_uploader("Upload your Outscraper CSV file", type="csv")

if uploaded_file and file_name:
    original_path = os.path.join(UPLOAD_DIR, f"{file_name}.csv")
    with open(original_path, "wb") as f:
        f.write(uploaded_file.read())
    st.success(f"Saved as {file_name}.csv")

    if st.button("✅ Process File"):
        processed_path = process_csv(original_path)
        st.success(f"File processed and saved as {os.path.basename(processed_path)}")
elif uploaded_file and not file_name:
    st.warning("⚠️ Please enter a name before uploading.")

st.markdown("---")
st.subheader("🔍 Processed Files")
search_term = st.text_input("Search by file name or row count")

files = load_processed_files()
if search_term:
    files = [f for f in files if search_term.lower() in f["name"].lower() or search_term in str(f["rows"])]

for f in files:
    col1, col2, col3, col4 = st.columns([3, 2, 3, 1])
    col1.write(f"📄 **{f['name']}**")
    col2.write(f"{f['rows']} rows")
    col3.write(f"🕒 {f['modified']}")
    with col4:
        if st.button("🗑️", key=f['name'] + "_delete_confirm"):
            confirm = st.radio(f"Are you sure you want to delete {f['name']}?", ["No", "Yes"], index=0, key=f['name'] + "_confirm")
            if confirm == "Yes":
                delete_file(f['path'])
                st.success(f"🗑️ {f['name']} deleted.")
                st.stop()

    with st.expander("📥 Download / Push to Clay", expanded=False):
        with open(f['path'], "rb") as file_data:
            st.download_button(
                label="📎 Download CSV",
                data=file_data,
                file_name=f['name'],
                mime='text/csv'
            )

        webhook_url = st.text_input(f"Enter Clay Webhook URL for {f['name']}", key=f['name'] + "_webhook")
        if st.button(f"Push {f['name']} to Clay", key=f['name'] + "_push"):
            if webhook_url:
                count = push_csv_to_clay(f['path'], webhook_url)
                st.success(f"✅ {count} rows pushed to Clay!")
            else:
                st.warning("Please provide a webhook URL before pushing.")
