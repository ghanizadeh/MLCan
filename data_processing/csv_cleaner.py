import os
import re
import shutil
import traceback

import streamlit as st
import pandas as pd
from calibration import InputProcessor

def process_csv_folder(folder_path, log_fn):
    """Process all CSVs in folder_path, writing status messages via log_fn."""
    input_processor = InputProcessor()

    csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv')]
    log_fn(f"Found {len(csv_files)} CSV files to process in:\n  {folder_path}")

    # Prepare output folder
    root_name = os.path.basename(os.path.normpath(folder_path))
    processed_folder = os.path.join(folder_path, f"{root_name}_Processed_Data")
    os.makedirs(processed_folder, exist_ok=True)

    for file_name in csv_files:
        file_path = os.path.join(folder_path, file_name)
        log_fn(f"\n**Processing {file_name}**…")

        # 1) Try filename parse
        alicat_m = re.search(r'AliCat(\d+\.\d+)', file_name)
        vfd_m    = re.search(r'VFD(\d+\.\d+)', file_name)

        try:
            if alicat_m and vfd_m:
                alicat_val = float(alicat_m.group(1))
                vfd_val    = float(vfd_m.group(1))
            else:
                log_fn("\n  ✗ No AliCat/VFD in filename — falling back to file contents…")
                df = pd.read_csv(file_path)
                al_cols = [c for c in df.columns if re.search(r'AliCat', c, re.IGNORECASE)]
                vfd_cols= [c for c in df.columns if re.search(r'VFD', c, re.IGNORECASE)]
                if not al_cols or not vfd_cols:
                    log_fn("\n  ✗ Skipping — no AliCat or VFD in columns or filename")
                    continue
                alicat_val = df[al_cols[0]].iloc[0]
                vfd_val    = df[vfd_cols[0]].iloc[0]
                log_fn(f"\n  ✓ Found in columns: AliCat={alicat_val}, VFD={vfd_val}")

            # read & filter
            df = pd.read_csv(file_path)
            orig_rows = len(df)
            if re.search(r'A_(\d+\.\d+)', file_name):
                df = df[df['indicator'] == 1]
            else:
                df = df[df['indicator'] == 0]

            tol = 0.01
            df = df[
                (df['AliCat_Output'].sub(alicat_val).abs() < tol) &
                (df['VFD_Output'].sub(vfd_val).abs() < tol)
            ]

            # calibrate boards
            for col in [
                'Board1_I0','Board1_I1','Board1_I2','Board1_I3',
                'Board3_I0','Board3_I1','Board3_I2','Board3_I3'
            ]:
                board = int(col.split('_')[0].replace('Board',''))
                channel = col.split('_')[1]
                df[col] = df[col].apply(
                    lambda x: input_processor.scale_input(board, channel, x)[0]
                )

            # timestamp check
            error_flag = False
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')

                df['Elapsed_s'] = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds()
                neg = df['Elapsed_s'].diff().dropna() < 0
                if neg.any():
                    error_flag = True
                    idx = neg[neg].index.tolist()
                    log_fn(f"\n  ✗ Signal Error: {file_name}")
                    log_fn(f"\n  ✗ Decrease detected at rows: {idx}")
                else:
                    log_fn("\n  ✔ All timestamps strictly increasing")

            # save
            base, ext = os.path.splitext(file_name)
            suffix = "_Processed_Signal_Error" if error_flag else "_Processed"
            out_name = f"{base}{suffix}{ext}"
            out_path = os.path.join(processed_folder, out_name)
            df.to_csv(out_path, index=False)
            log_fn(f"\n  ✓ Complete: Kept {len(df)} / {orig_rows} rows → `{out_name}`")

        except Exception as e:
            base, ext = os.path.splitext(file_name)
            err_name = f"{base}_File_Error{ext}"
            err_path = os.path.join(processed_folder, err_name)
            shutil.copy2(file_path, err_path)
            log_fn(f"\n  ✗ Error: {e} → saved original as `{err_name}`")
            log_fn(traceback.format_exc())

    log_fn("\n All files processed!")

# --- Streamlit UI ---

st.title("CSV Cleaner & Signal Checker")
#st.write("Pick a folder of CSVs—this will process each file and show you every status message below.")

folder = st.text_input(
    "Folder path (Source Files)", 
    value=os.getcwd(),
    help="Enter the directory containing your CSV files."
)

if st.button("Run Processing"):
    log_area = st.empty()
    messages = []
    def log_fn(msg):
        messages.append(msg)
        log_area.markdown("\n".join(messages))

    if not os.path.isdir(folder):
        st.error(f"❌ `{folder}` is not a valid folder.")
    else:
        process_csv_folder(folder, log_fn)
