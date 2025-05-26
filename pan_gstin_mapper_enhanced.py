#!/usr/bin/env python3
"""
Enhanced PAN to GSTIN Mapper

This script automates the process of extracting multiple GSTINs for each PAN number
from the GST portal and saving them to a two-sheet Excel file.

Enhancements:
1. Two-sheet approach:
   - Sheet 1: Unique PAN entries with metadata
   - Sheet 2: All GSTINs with references to their corresponding PAN
2. Batch processing to reduce file read/write operations
3. Incremental update system that only writes to Excel once at the end
4. Comprehensive validation of Excel structure before processing
5. Checkpoint system to track progress and allow resuming from interruptions
6. Refactored code with smaller, focused functions
7. Configuration section for easy customization

Steps:
1. Take input for PAN numbers from an Excel file
2. For each PAN number, extract all GSTINs from the GST portal
3. Update the Excel file with all GSTINs corresponding to each PAN
"""

# ===== CONFIGURATION SECTION =====
# File paths and directories
SCREENSHOT_DIR = "screenshots"
CHECKPOINT_FILE = "pan_gstin_checkpoint.json"

# URLs and endpoints
GST_PORTAL_URL = "https://services.gst.gov.in/services/searchtpbypan"
GST_GSTIN_SEARCH_URL = "https://services.gst.gov.in/services/searchtp"

# TrueCaptcha API credentials
TRUECAPTCHA_ACCOUNTS = [
    {
        "userid": "nityamkathuria@registerkaro.co.in",
        "apikey": "EHfymf49KxooX6UPw5Lz"
    },
    {
        "userid": "vedanshrk",
        "apikey": "cmpVOJlCk8Vb0ezBEQuL"
    }
]

# Excel sheet configuration
PAN_SHEET_NAME = "PAN_Data"
GSTIN_SHEET_NAME = "GSTIN_Data"

# PAN sheet columns
PAN_SHEET_COLUMNS = [
    "PAN", 
    "Name", 
    "Email", 
    "Phone", 
    "Address", 
    "GSTIN_Count", 
    "Last_Updated", 
    "Status"
]

# GSTIN sheet columns
GSTIN_SHEET_COLUMNS = [
    "PAN_Reference",
    "GSTIN",
    "GSTIN_Status",
    "State",
    "Trade_Name",
    "Registration_Date",
    "HSN_Codes",
    "Last_Updated"
]
# ===== END CONFIGURATION SECTION =====

import pandas as pd
import time
import os
import random
import sys
import base64
import requests
import logging
import re
import io
import argparse
import json
import datetime
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pan_gstin_mapper_enhanced.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variables
# ===== EXCEL HANDLING FUNCTIONS =====

def validate_excel_structure(file_path):
    """
    Validate the Excel file structure and create necessary sheets if they don't exist.
    Also handles conversion from old single-sheet format to new two-sheet format.
    
    Args:
        file_path: Path to the Excel file
        
    Returns:
        tuple: (is_valid, error_message, DataFrame for PAN sheet, DataFrame for GSTIN sheet)
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}", None, None
            
        # Check if file is accessible
        try:
            with open(file_path, 'rb') as f:
                pass
        except PermissionError:
            return False, f"Permission denied when accessing file: {file_path}", None, None
        except Exception as e:
            return False, f"Error accessing file: {e}", None, None
            
        # Check file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in ['.xlsx', '.xls']:
            return False, f"Invalid file format: {file_ext}. Only Excel files (.xlsx, .xls) are supported.", None, None
            
        # Try to read the file
        try:
            # Check if the file has the required sheets
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            # Check if we need to convert from old format to new format
            is_old_format = PAN_SHEET_NAME not in sheet_names or GSTIN_SHEET_NAME not in sheet_names
            
            if is_old_format:
                logger.info(f"Detected old format Excel file. Converting to new two-sheet format...")
                
                # Read the old format data (assuming it's in the first sheet)
                old_df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
                logger.info(f"Read old format data with {len(old_df)} rows")
                
                # Check if the old format has a PAN column (case-insensitive)
                pan_column = None
                for col in old_df.columns:
                    if col.upper() == "PAN" or "PAN" in col.upper() or col.upper() in ["PAN_NUMBER", "PANNUMBER", "PAN_NO", "PANNO"]:
                        pan_column = col
                        logger.info(f"Found PAN column in old format: '{pan_column}'")
                        break
                
                if pan_column is None:
                    return False, "Could not find PAN column in the old format file", None, None
                
                # Create new DataFrames for the two-sheet structure
                pan_df = pd.DataFrame(columns=PAN_SHEET_COLUMNS)
                gstin_df = pd.DataFrame(columns=GSTIN_SHEET_COLUMNS)
                
                # Extract unique PAN entries for the PAN_Data sheet
                unique_pans = {}
                for i, row in old_df.iterrows():
                    pan = row[pan_column]
                    if pd.notna(pan):
                        pan = str(pan).strip().upper()
                        if len(pan) == 10 and pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha():
                            if pan not in unique_pans:
                                new_row = {col: "" for col in PAN_SHEET_COLUMNS}
                                new_row["PAN"] = pan
                                
                                # Copy other relevant columns if they exist
                                for col in ["Name", "Email", "Phone", "Address"]:
                                    if col in old_df.columns:
                                        new_row[col] = row[col]
                                    elif col.lower() in old_df.columns:
                                        new_row[col] = row[col.lower()]
                                    elif col.upper() in old_df.columns:
                                        new_row[col] = row[col.upper()]
                                
                                unique_pans[pan] = len(pan_df)
                                pan_df = pd.concat([pan_df, pd.DataFrame([new_row])], ignore_index=True)
                
                # Extract GSTIN entries for the GSTIN_Data sheet
                gstin_column = None
                for col in old_df.columns:
                    if col.upper() == "GSTIN" or "GSTIN" in col.upper() or col.upper() in ["GST", "GST_NUMBER", "GSTNUMBER", "GST_NO", "GSTNO"]:
                        gstin_column = col
                        logger.info(f"Found GSTIN column in old format: '{gstin_column}'")
                        break
                
                if gstin_column is not None:
                    for i, row in old_df.iterrows():
                        pan = row[pan_column] if pd.notna(row[pan_column]) else ""
                        pan = str(pan).strip().upper()
                        
                        gstin = row[gstin_column] if pd.notna(row[gstin_column]) else ""
                        gstin = str(gstin).strip().upper()
                        
                        if len(pan) == 10 and len(gstin) == 15:
                            new_row = {
                                "PAN_Reference": pan,
                                "GSTIN": gstin,
                                "GSTIN_Status": row.get("GSTIN Status", "") if pd.notna(row.get("GSTIN Status", "")) else "",
                                "State": row.get("State", "") if pd.notna(row.get("State", "")) else "",
                                "Last_Updated": datetime.datetime.now().isoformat()
                            }
                            gstin_df = pd.concat([gstin_df, pd.DataFrame([new_row])], ignore_index=True)
                
                logger.info(f"Converted old format to new format: {len(pan_df)} unique PANs and {len(gstin_df)} GSTINs")
                
                # Save the new format back to the file
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    pan_df.to_excel(writer, sheet_name=PAN_SHEET_NAME, index=False)
                    gstin_df.to_excel(writer, sheet_name=GSTIN_SHEET_NAME, index=False)
                
                logger.info(f"Saved new two-sheet format to {file_path}")
                
            else:
                # File already has the required sheets, just read them
                pan_df = pd.read_excel(file_path, sheet_name=PAN_SHEET_NAME, engine='openpyxl')
                logger.info(f"Found existing PAN sheet with {len(pan_df)} rows")
                
                gstin_df = pd.read_excel(file_path, sheet_name=GSTIN_SHEET_NAME, engine='openpyxl')
                logger.info(f"Found existing GSTIN sheet with {len(gstin_df)} rows")
            
            # Validate PAN sheet columns
            for col in PAN_SHEET_COLUMNS:
                if col not in pan_df.columns:
                    pan_df[col] = ""
                    logger.info(f"Added missing column '{col}' to PAN sheet")
                    
            # Validate GSTIN sheet columns
            for col in GSTIN_SHEET_COLUMNS:
                if col not in gstin_df.columns:
                    gstin_df[col] = ""
                    logger.info(f"Added missing column '{col}' to GSTIN sheet")
            
            # Check if PAN column exists and has valid values (case-insensitive)
            pan_column_found = False
            for col in pan_df.columns:
                if col.upper() == "PAN":
                    pan_column_found = True
                    if pan_df[col].isna().all():
                        return False, "PAN column is empty in the PAN sheet", pan_df, gstin_df
                    break
            
            if not pan_column_found:
                return False, "PAN column is missing in the PAN sheet", pan_df, gstin_df
                
            # Validate PAN format in PAN sheet
            invalid_pans = []
            for i, pan in enumerate(pan_df["PAN"]):
                if pd.notna(pan):
                    pan_str = str(pan).strip().upper()
                    if not (len(pan_str) == 10 and pan_str[:5].isalpha() and pan_str[5:9].isdigit() and pan_str[9].isalpha()):
                        invalid_pans.append((i, pan_str))
                        if len(invalid_pans) <= 5:  # Limit logging to first 5 invalid PANs
                            logger.warning(f"Invalid PAN format at row {i+2}: {pan_str}")
                            
            if invalid_pans:
                logger.warning(f"Found {len(invalid_pans)} invalid PAN entries in the PAN sheet")
                
            return True, "", pan_df, gstin_df
            
        except Exception as e:
            return False, f"Error reading Excel file: {e}", None, None
            
    except Exception as e:
        return False, f"Unexpected error during validation: {e}", None, None


def extract_pan_data(pan_df):
    """
    Extract PAN data from the PAN sheet.
    
    Args:
        pan_df: DataFrame containing PAN data
        
    Returns:
        tuple: (list of unique PAN numbers, dictionary mapping PAN to row index)
    """
    # Get PAN numbers
    pan_numbers = []
    pan_to_index = {}
    
    for i, row in pan_df.iterrows():
        pan = row["PAN"]
        if pd.notna(pan):
            pan = str(pan).strip().upper()
            if len(pan) == 10 and pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha():
                if pan not in pan_to_index:
                    pan_numbers.append(pan)
                    pan_to_index[pan] = i
                    
    logger.info(f"Extracted {len(pan_numbers)} unique valid PAN numbers")
    return pan_numbers, pan_to_index


def load_checkpoint():
    """
    Load checkpoint data from file.
    
    Returns:
        dict: Checkpoint data or empty dict if no checkpoint exists
    """
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoint_data = json.load(f)
                logger.info(f"Loaded checkpoint data for {len(checkpoint_data.get('processed_pans', []))} processed PANs")
                return checkpoint_data
        except Exception as e:
            logger.error(f"Error loading checkpoint file: {e}")
            return {"processed_pans": [], "results": {}}
    else:
        logger.info("No checkpoint file found, starting fresh")
        return {"processed_pans": [], "results": {}}


def save_checkpoint(processed_pans, results):
    """
    Save checkpoint data to file.
    
    Args:
        processed_pans: List of processed PAN numbers
        results: Dictionary mapping PAN to GSTIN results
    """
    checkpoint_data = {
        "processed_pans": processed_pans,
        "results": results,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    try:
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        logger.info(f"Saved checkpoint with {len(processed_pans)} processed PANs")
    except Exception as e:
        logger.error(f"Error saving checkpoint file: {e}")


def update_excel_with_results(file_path, pan_df, gstin_df, results_dict):
    """
    Update the Excel file with results using the two-sheet approach.
    
    Args:
        file_path: Path to the Excel file
        pan_df: DataFrame for the PAN sheet
        gstin_df: DataFrame for the GSTIN sheet
        results_dict: Dictionary mapping PAN to GSTIN results
        
    Returns:
        tuple: (updated pan_df, updated gstin_df)
    """
    try:
        # Create a backup of the file first
        backup_path = f"{os.path.splitext(file_path)[0]}_backup{os.path.splitext(file_path)[1]}"
        with pd.ExcelWriter(backup_path, engine='openpyxl') as writer:
            pan_df.to_excel(writer, sheet_name=PAN_SHEET_NAME, index=False)
            gstin_df.to_excel(writer, sheet_name=GSTIN_SHEET_NAME, index=False)
        logger.info(f"Created backup of file at {backup_path}")
        
        # Get current timestamp
        current_time = datetime.datetime.now().isoformat()
        
        # Update PAN sheet with GSTIN counts
        for pan, results in results_dict.items():
            # Find the row index for this PAN
            pan_rows = pan_df[pan_df["PAN"] == pan].index.tolist()
            if pan_rows:
                row_idx = pan_rows[0]
                
                # Count valid GSTINs
                gstin_count = sum(1 for r in results if "GSTIN" in r and len(r["GSTIN"]) == 15)
                
                # Update the PAN sheet
                pan_df.at[row_idx, "GSTIN_Count"] = gstin_count
                pan_df.at[row_idx, "Last_Updated"] = current_time
                
                if gstin_count > 0:
                    pan_df.at[row_idx, "Status"] = "Success"
                elif "No records found" in str(results):
                    pan_df.at[row_idx, "Status"] = "No GSTINs found"
                elif any("Error" in str(r.get("Result", "")) for r in results):
                    error_msg = next((r.get("Result", "") for r in results if "Error" in str(r.get("Result", ""))), "Error")
                    pan_df.at[row_idx, "Status"] = error_msg
                else:
                    pan_df.at[row_idx, "Status"] = "Unknown"
                    
                logger.info(f"Updated PAN sheet for {pan} with {gstin_count} GSTINs")
        
        # Add new rows to GSTIN sheet
        new_gstin_rows = []
        for pan, results in results_dict.items():
            for result in results:
                if "GSTIN" in result and len(result["GSTIN"]) == 15:
                    new_gstin_rows.append({
                        "PAN_Reference": pan,
                        "GSTIN": result["GSTIN"],
                        "GSTIN_Status": result.get("GSTIN Status", ""),
                        "State": result.get("State", ""),
                        "Trade_Name": result.get("Trade_Name", ""),
                        "Registration_Date": result.get("Registration_Date", ""),
                        "HSN_Codes": result.get("HSN_Codes", ""),
                        "Last_Updated": current_time
                    })
        
        # Create a DataFrame from the new GSTIN rows
        if new_gstin_rows:
            new_gstin_df = pd.DataFrame(new_gstin_rows)
            
            # Check for duplicates in the GSTIN sheet
            if not gstin_df.empty:
                # Create a set of existing GSTINs for faster lookup
                existing_gstins = set(gstin_df["GSTIN"].dropna())
                
                # Filter out GSTINs that already exist
                new_gstin_df = new_gstin_df[~new_gstin_df["GSTIN"].isin(existing_gstins)]
                
            # Append new GSTINs to the GSTIN sheet
            gstin_df = pd.concat([gstin_df, new_gstin_df], ignore_index=True)
            logger.info(f"Added {len(new_gstin_df)} new GSTIN entries to GSTIN sheet")
        
        # Save the updated DataFrames back to the file
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            pan_df.to_excel(writer, sheet_name=PAN_SHEET_NAME, index=False)
            gstin_df.to_excel(writer, sheet_name=GSTIN_SHEET_NAME, index=False)
        logger.info(f"Saved updated Excel file with {len(pan_df)} PAN entries and {len(gstin_df)} GSTIN entries")
        
        return pan_df, gstin_df
        
    except Exception as e:
        logger.error(f"Error updating Excel file: {e}")
        raise
TEST_MODE = False

# Function to update Excel file with GSTIN details
def update_excel_with_gstin_details(file_path, gstin, details):
    """
    Update the Excel file with GSTIN details.
    
    Args:
        file_path: Path to the Excel file
        gstin: The GSTIN to update
        details: Dictionary containing GSTIN details (Trade name, Date of registration, HSN)
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    logger.info(f"Updating Excel file with details for GSTIN: {gstin}")
    logger.info(f"File path: {file_path}")
    logger.info(f"Details received: {json.dumps(details, indent=2)}")
    
    try:
        # Check file extension to determine if it's CSV or Excel
        file_ext = os.path.splitext(file_path)[1].lower()
        is_csv = file_ext == '.csv'
        
        logger.info(f"File type detected: {'CSV' if is_csv else 'Excel'}")
        
        if is_csv:
            # Handle CSV file
            logger.info("Processing as CSV file")
            try:
                # Read the CSV file
                df = pd.read_csv(file_path)
                logger.info(f"CSV file read successfully with {len(df)} rows")
                
                # Find rows with matching GSTIN
                matching_rows = df[df["GSTIN"] == gstin].index.tolist()
                
                if not matching_rows:
                    logger.warning(f"GSTIN {gstin} not found in the CSV file")
                    return False
                
                # Update each matching row
                for row_idx in matching_rows:
                    logger.info(f"Updating row {row_idx} with GSTIN {gstin}")
                    
                    # Update Trade Name
                    if "trade_name" in details and details["trade_name"]:
                        df.at[row_idx, "Trade_Name"] = details["trade_name"]
                        logger.info(f"Updated Trade_Name to: {details['trade_name']}")
                    else:
                        logger.warning("No trade_name found in details")
                    
                    # Update Registration Date
                    if "registration_date" in details and details["registration_date"]:
                        df.at[row_idx, "Registration_Date"] = details["registration_date"]
                        logger.info(f"Updated Registration_Date to: {details['registration_date']}")
                    else:
                        logger.warning("No registration_date found in details")
                    
                    # Update HSN Codes
                    if "hsn_codes" in details and details["hsn_codes"]:
                        hsn_codes_str = ", ".join(details["hsn_codes"])
                        df.at[row_idx, "HSN_Codes"] = hsn_codes_str
                        logger.info(f"Updated HSN_Codes to: {hsn_codes_str}")
                    else:
                        logger.warning("No hsn_codes found in details")
                
                # Check if columns exist, if not add them
                for col in ["Trade_Name", "Registration_Date", "HSN_Codes"]:
                    if col not in df.columns:
                        logger.warning(f"Column {col} not found in CSV, adding it")
                        df[col] = ""
                
                # Save the updated CSV
                df.to_csv(file_path, index=False)
                logger.info(f"CSV file saved successfully with updates")
                return True
                
            except Exception as e:
                logger.error(f"Error updating CSV file: {e}")
                return False
        else:
            # Handle Excel file
            logger.info("Processing as Excel file")
            # Validate Excel structure first
            is_valid, error_message, pan_df, gstin_df = validate_excel_structure(file_path)
            
            if not is_valid:
                logger.error(f"Invalid Excel structure: {error_message}")
                return False
                
            # Check if the GSTIN exists in the GSTIN sheet
            gstin_rows = gstin_df[gstin_df["GSTIN"] == gstin].index.tolist()
            
            if not gstin_rows:
                logger.warning(f"GSTIN {gstin} not found in the Excel file")
                return False
                
            # Get the row index for this GSTIN
            row_idx = gstin_rows[0]
            logger.info(f"Found GSTIN at row index {row_idx}")
            
            # Update the GSTIN details
            current_time = datetime.datetime.now().isoformat()
            
            # Update Trade Name
            if "trade_name" in details and details["trade_name"]:
                gstin_df.at[row_idx, "Trade_Name"] = details["trade_name"]
                logger.info(f"Updated Trade_Name to: {details['trade_name']}")
            else:
                logger.warning("No trade_name found in details")
                
            # Update Registration Date
            if "registration_date" in details and details["registration_date"]:
                gstin_df.at[row_idx, "Registration_Date"] = details["registration_date"]
                logger.info(f"Updated Registration_Date to: {details['registration_date']}")
            else:
                logger.warning("No registration_date found in details")
                
            # Update HSN Codes
            if "hsn_codes" in details and details["hsn_codes"]:
                # Convert list to string for storage in Excel
                hsn_codes_str = ", ".join(details["hsn_codes"])
                gstin_df.at[row_idx, "HSN_Codes"] = hsn_codes_str
                logger.info(f"Updated HSN_Codes to: {hsn_codes_str}")
            else:
                logger.warning("No hsn_codes found in details")
            
        # Update Last_Updated timestamp
        gstin_df.at[row_idx, "Last_Updated"] = current_time
        
        # Log the DataFrame state before saving
        logger.info(f"DataFrame before saving: {gstin_df.loc[row_idx].to_dict()}")
        gstin_df.at[row_idx, "Last_Updated"] = current_time
        logger.info(f"Updated Last_Updated to: {current_time}")
        gstin_df.at[row_idx, "Last_Updated"] = current_time
        
        # Save the updated DataFrames back to the file
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            pan_df.to_excel(writer, sheet_name=PAN_SHEET_NAME, index=False)
            gstin_df.to_excel(writer, sheet_name=GSTIN_SHEET_NAME, index=False)
            
        logger.info(f"Successfully updated Excel file with details for GSTIN: {gstin}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating Excel file with GSTIN details: {e}")
        return False

# Create screenshots directory if it doesn't exist
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

# Processing parameters
BATCH_SIZE = 10  # Number of PANs to process before writing to file
MAX_RETRIES = 5  # Maximum number of retries for captcha solving
DELAY_BETWEEN_REQUESTS = (1, 3)  # Random delay range between requests (min, max)
# ===== CAPTCHA HANDLING FUNCTIONS =====

def solve_captcha_with_truecaptcha(captcha_path, account_index=0):
    """
    Solve captcha using TrueCaptcha API with a file path.
    Enhanced with better image validation and processing.
    
    Args:
        captcha_path: Path to the captcha image file
        account_index: Index of the TrueCaptcha account to use
        
    Returns:
        str: The captcha solution or None if failed
    """
    account = TRUECAPTCHA_ACCOUNTS[account_index]
    userid = account["userid"]
    apikey = account["apikey"]
    
    try:
        # Check if file exists and is readable
        if not os.path.exists(captcha_path):
            logger.error(f"File does not exist: {captcha_path}")
            return None
            
        file_size = os.path.getsize(captcha_path)
        if file_size == 0:
            logger.error(f"File is empty: {captcha_path}")
            return None
            
        # Skip small files that are likely not valid images
        if file_size < 1000:
            logger.warning(f"File is too small, might not be a valid image: {captcha_path} (size: {file_size} bytes)")
            return None
            
        logger.info(f"Reading file: {captcha_path} (size: {file_size} bytes)")
        
        # Verify the file is a valid image and check dimensions
        try:
            with open(captcha_path, "rb") as image_file:
                image_data = image_file.read()
                img = Image.open(io.BytesIO(image_data))
                width, height = img.size
                logger.info(f"Image dimensions: {width}x{height}")
                
                # Check if image dimensions are reasonable for a captcha
                if width <= 2 or height <= 2:
                    logger.warning(f"Image dimensions too small: {width}x{height}")
                    return None
                    
                # Check if image is mostly blank/white (common for loading images)
                # Convert to grayscale and check pixel values
                img_gray = img.convert('L')
                pixels = list(img_gray.getdata())
                avg_pixel_value = sum(pixels) / len(pixels) if pixels else 0
                
                # If average pixel value is very high (close to white), image might be blank
                if avg_pixel_value > 240:  # 255 is white
                    logger.warning(f"Image appears to be mostly blank (avg pixel value: {avg_pixel_value})")
                    return None
                    
                logger.info("File is a valid image with reasonable dimensions")
        except Exception as e:
            logger.error(f"File is not a valid image: {e}")
            return None
        
        # Read the file again for API submission
        with open(captcha_path, "rb") as image_file:
            image_data = image_file.read()
            logger.info(f"Read {len(image_data)} bytes from file")
            
            encoded_string = base64.b64encode(image_data).decode('ascii')
            logger.info(f"Base64 encoded string length: {len(encoded_string)}")
            
            url = 'https://api.apitruecaptcha.org/one/gettext'

            data = {
                'userid': userid,
                'apikey': apikey,
                'data': encoded_string,
                'numeric': 1,  # Specify that we expect numeric result
                'len_min': 6,  # Minimum length
                'len_max': 6   # Maximum length
            }
            
            logger.info(f"Sending captcha file to TrueCaptcha API using account: {userid}")
            
            # Log detailed request data in test mode
            if TEST_MODE:
                # Don't log the full base64 string to avoid huge logs
                safe_data = data.copy()
                if 'data' in safe_data:
                    safe_data['data'] = f"[Base64 encoded image, length: {len(safe_data['data'])}]"
                logger.debug(f"TrueCaptcha API request data: {safe_data}")
            
            # Add exponential backoff retry for API request
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # Add delay for retries
                    if retry > 0:
                        backoff_time = 2 ** retry
                        logger.info(f"Retry {retry}/{max_retries-1}, waiting {backoff_time} seconds")
                        time.sleep(backoff_time)
                    
                    response = requests.post(url=url, json=data, timeout=15)
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"API response: {result}")
                        
                        if 'result' in result:
                            captcha_text = result['result']
                            captcha_text = re.sub(r'[^0-9]', '', captcha_text)
                            if len(captcha_text) == 6:
                                logger.info(f"Captcha solved: {captcha_text}")
                                return captcha_text
                            else:
                                logger.warning(f"Captcha solution '{captcha_text}' is not 6 digits")
                        
                        # Check if it's a usage limit error
                        if 'error_message' in result and "above free usage limit" in result['error_message']:
                            logger.warning(f"Account {userid} has reached usage limit")
                            break  # No need to retry with the same account
                        
                        # If we got a response but no valid result, try again
                        if retry < max_retries - 1:
                            logger.warning("Invalid API response, retrying...")
                            continue
                        
                        return None
                    else:
                        logger.warning(f"TrueCaptcha API request failed with status code: {response.status_code}")
                        logger.warning(f"Response content: {response.text}")
                        
                        # If it's a server error, retry
                        if response.status_code >= 500 and retry < max_retries - 1:
                            logger.warning("Server error, retrying...")
                            continue
                        
                        return None
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request exception: {e}")
                    if retry < max_retries - 1:
                        logger.warning("Network error, retrying...")
                        continue
                    return None
            
            return None
    except Exception as e:
        logger.error(f"Error solving captcha with file: {e}")
        return None


def handle_captcha(driver, max_retries=5):
    """
    Handle captcha on the GST website with improved image loading detection.
    
    Args:
        driver: Selenium WebDriver instance
        max_retries: Maximum number of retries
        
    Returns:
        bool: True if captcha was handled successfully, False otherwise
    """
    wait = WebDriverWait(driver, 10)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Captcha handling attempt {attempt+1}/{max_retries}")
            
            # Check if captcha input field is present
            captcha_input = wait.until(
                EC.presence_of_element_located((By.ID, "fo-captcha"))
            )
            
            logger.info("Captcha input field found")
            
            # Find the captcha image element with ID "imgCaptcha"
            logger.info("Looking for captcha image element with ID 'imgCaptcha'...")
            captcha_element = wait.until(
                EC.presence_of_element_located((By.ID, "imgCaptcha"))
            )
            
            # Log the HTML of the captcha image element
            captcha_html = captcha_element.get_attribute('outerHTML')
            logger.info(f"Captcha image element HTML: {captcha_html}")
            
            # Check if the captcha image has the "captcha-loading" class
            captcha_class = captcha_element.get_attribute('class')
            if captcha_class and "captcha-loading" in captcha_class:
                logger.info("Captcha image is still loading, waiting for it to complete...")
                
                # Wait for the "captcha-loading" class to disappear (max 10 seconds)
                try:
                    WebDriverWait(driver, 10).until_not(
                        lambda d: "captcha-loading" in d.find_element(By.ID, "imgCaptcha").get_attribute('class')
                    )
                    logger.info("Captcha image finished loading")
                except TimeoutException:
                    logger.warning("Timed out waiting for captcha image to load, proceeding anyway")
                
                # Refresh the element reference after waiting
                captcha_element = driver.find_element(By.ID, "imgCaptcha")
            
            # Log whether the element was found successfully
            if captcha_element:
                logger.info("Captcha image element found successfully")
                
                # Log the dimensions and other properties of the captcha image
                size = captcha_element.size
                location = captcha_element.location
                src = captcha_element.get_attribute('src')
                
                logger.info(f"Captcha image dimensions: {size}")
                logger.info(f"Captcha image location: {location}")
                logger.info(f"Captcha image src: {src}")
            else:
                logger.error("Captcha image element not found")
                return False
            
            # Try multiple approaches to capture the captcha image
            
            # Approach 1: Direct screenshot
            captcha_path = os.path.join(SCREENSHOT_DIR, f"captcha_direct_{int(time.time())}.png")
            captcha_element.screenshot(captcha_path)
            logger.info(f"Saved captcha screenshot to {captcha_path}")
            
            # Check if the screenshot is valid and has reasonable dimensions
            try:
                img = Image.open(captcha_path)
                width, height = img.size
                logger.info(f"Captcha image dimensions: {{'width': {width}, 'height': {height}}}")
                
                # If image is too small, try alternative approaches
                if width <= 2 or height <= 2 or os.path.getsize(captcha_path) < 1000:
                    logger.warning(f"Captcha image is too small ({width}x{height}), trying alternative approach")
                    
                    # Approach 2: Download the image directly from the src URL
                    captcha_src = captcha_element.get_attribute('src')
                    
                    # Get the full URL if it's a relative URL
                    if captcha_src.startswith('/'):
                        base_url = driver.current_url
                        base_domain = '/'.join(base_url.split('/')[:3])  # Get https://domain.com part
                        captcha_src = base_domain + captcha_src
                    
                    # Add a random parameter to force a fresh captcha
                    if '?' in captcha_src:
                        captcha_src += f"&refresh={random.random()}"
                    else:
                        captcha_src += f"?refresh={random.random()}"
                    
                    logger.info(f"Downloading captcha directly from URL: {captcha_src}")
                    
                    # Use a session with headers to mimic a browser
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': driver.current_url,
                    })
                    
                    response = session.get(captcha_src, timeout=10)
                    if response.status_code == 200:
                        download_path = os.path.join(SCREENSHOT_DIR, f"captcha_download_{int(time.time())}.png")
                        with open(download_path, "wb") as f:
                            f.write(response.content)
                        logger.info(f"Saved downloaded captcha to {download_path}")
                        
                        # Use the downloaded image instead
                        captcha_path = download_path
                        
                        # Verify the downloaded image
                        img = Image.open(captcha_path)
                        width, height = img.size
                        logger.info(f"Downloaded captcha dimensions: {{'width': {width}, 'height': {height}}}")
                    else:
                        logger.warning(f"Failed to download captcha image: {response.status_code}")
            except Exception as e:
                logger.warning(f"Error checking captcha image: {e}")
            
            # Try to solve the captcha with TrueCaptcha API
            # Try each account
            for account_index in range(len(TRUECAPTCHA_ACCOUNTS)):
                captcha_text = solve_captcha_with_truecaptcha(captcha_path, account_index)
                
                if captcha_text:
                    # Enter the captcha solution
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)
                    logger.info(f"Entered captcha solution: {captcha_text}")
                    
                    # Click the search button
                    search_button = wait.until(
                        EC.element_to_be_clickable((By.ID, "lotsearch"))
                    )
                    search_button.click()
                    logger.info("Clicked search button")
                    
                    # Wait for results to load
                    time.sleep(3)
                    
                    # Check if we've moved to the results page
                    results_elements = driver.find_elements(By.CSS_SELECTOR, "table.table.tbl.inv.exp.table-bordered.ng-table")
                    no_records_text = "No records found" in driver.page_source
                    
                    if results_elements or no_records_text:
                        logger.info("Captcha solved successfully - results page detected")
                        return True
                    else:
                        # Check if we're still on the captcha page
                        if driver.find_elements(By.ID, "fo-captcha"):
                            logger.warning("Captcha solution was incorrect, trying another account")
                            continue
                        else:
                            # We're on some other page, assume success
                            logger.info("Captcha page no longer visible, assuming success")
                            return True
            
            # If TrueCaptcha API failed with both accounts, try again with a new captcha
            logger.warning("All TrueCaptcha accounts failed to solve the captcha, trying again with a new captcha")
            
            # Try refreshing the page to get a new captcha
            logger.info("Refreshing page to get a new captcha")
            driver.refresh()
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error during captcha handling attempt {attempt+1}: {e}")
            
            if attempt < max_retries - 1:
                logger.info("Refreshing page and retrying...")
                try:
                    driver.refresh()
                    time.sleep(2)
                except:
                    logger.error("Failed to refresh page")
                    return False
            else:
                logger.error("Maximum retry attempts reached")
                return False
    
    logger.error("Failed to handle captcha after multiple attempts")
    return False
# ===== SEARCH RESULTS EXTRACTION =====

def extract_search_results(driver):
    """
    Extract search results from the page.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        list: List of dictionaries containing the search results
    """
    try:
        # Take a screenshot of the results page for debugging
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"results_page_{int(time.time())}.png")
        driver.save_screenshot(screenshot_path)
        logger.info(f"Saved results page screenshot to {screenshot_path}")
        
        # Log the HTML content of the results page for debugging
        html_content = driver.page_source
        if TEST_MODE:
            logger.debug(f"Results page HTML content: {html_content[:1000]}...")  # Log first 1000 chars to avoid huge logs
            
            # Save the full HTML to a file in test mode
            html_path = os.path.join(SCREENSHOT_DIR, f"results_page_html_{int(time.time())}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Saved full HTML content to {html_path}")
        
        # Check if "No records found" message is present
        if "No records found" in html_content:
            logger.info("No records found message detected")
            return [{"Result": "No records found"}]
        
        # Wait for the results table to load with increased timeout
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.tbl.inv.exp.table-bordered.ng-table"))
            )
            logger.info("Results table found")
        except Exception as e:
            logger.warning(f"Results table not found: {e}")
            return [{"Result": "Error: Results table not found"}]
        
        # Try different selectors to find the table
        tables = driver.find_elements(By.CSS_SELECTOR, "table.table.tbl.inv.exp.table-bordered.ng-table")
        if not tables:
            tables = driver.find_elements(By.CSS_SELECTOR, "table.table")
            if not tables:
                logger.warning("No tables found on the page")
                return [{"Result": "Error: No tables found on the page"}]
            else:
                logger.info(f"Found {len(tables)} tables with generic selector")
        else:
            logger.info(f"Found {len(tables)} tables with specific selector")
        
        # Get all rows from all tables
        results = []
        for table_idx, table in enumerate(tables):
            logger.info(f"Processing table {table_idx+1}/{len(tables)}")
            
            # Get table headers to understand the column structure
            headers = []
            try:
                header_cells = table.find_elements(By.CSS_SELECTOR, "thead th")
                headers = [cell.text.strip() for cell in header_cells]
                logger.info(f"Table headers: {headers}")
            except Exception as e:
                logger.warning(f"Could not extract table headers: {e}")
            
            # Get all rows
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            logger.info(f"Found {len(rows)} rows in table {table_idx+1}")
            
            if not rows:
                logger.warning(f"No rows found in table {table_idx+1}")
                continue
            
            # Process each row
            for row_idx, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 4:
                        # Log all cell values for debugging
                        cell_values = [cell.text.strip() for cell in cells]
                        logger.info(f"Row {row_idx+1} cells: {cell_values}")
                        
                        # Extract data based on column position
                        gstin = cells[1].text.strip()
                        status = cells[2].text.strip()
                        state = cells[3].text.strip()
                        
                        # Validate GSTIN format (should be 15 characters)
                        if len(gstin) != 15:
                            logger.warning(f"Invalid GSTIN format: {gstin}")
                        
                        results.append({
                            "GSTIN": gstin,
                            "GSTIN Status": status,
                            "State": state
                        })
                        logger.info(f"Added result: GSTIN={gstin}, Status={status}, State={state}")
                except Exception as e:
                    logger.error(f"Error extracting data from row {row_idx+1}: {e}")
        
        if results:
            logger.info(f"Extracted {len(results)} results in total")
            return results  # Return all results, not just the first one
        else:
            logger.warning("No results extracted from any table")
            return [{"Result": "Error: No results extracted"}]
            
    except Exception as e:
        logger.error(f"Error extracting search results: {e}")
        return [{"Result": f"Error: {str(e)}"}]


# ===== MAIN PROCESSING FUNCTION =====

def process_pan_numbers(file_path, headless=False, test_mode=False, limit=None, resume=False):
    """
    Process PAN numbers from an Excel file and extract GSTINs from the GST portal.
    Enhanced with batch processing, checkpoints, and two-sheet approach.
    
    Args:
        file_path: Path to the Excel file
        headless: Whether to run the browser in headless mode
        test_mode: Whether to run in test mode (process only one PAN)
        limit: Maximum number of unique PAN numbers to process (default: None = process all)
        resume: Whether to resume from a checkpoint
    """
    global TEST_MODE
    TEST_MODE = test_mode
    
    if test_mode:
        logger.setLevel(logging.DEBUG)
        logger.info("Running in TEST MODE - will process only one PAN number with detailed logging")
    
    # Validate Excel file structure
    valid, error_message, pan_df, gstin_df = validate_excel_structure(file_path)
    if not valid:
        logger.error(f"Excel validation failed: {error_message}")
        print(f"\nERROR: Excel validation failed: {error_message}")
        return
    
    # Extract PAN data
    pan_numbers, pan_to_index = extract_pan_data(pan_df)
    if not pan_numbers:
        logger.error("No valid PAN numbers found in the file.")
        print("\nERROR: No valid PAN numbers found in the file.")
        return
    
    # Load checkpoint if resuming
    processed_pans = []
    results_dict = {}
    
    if resume:
        checkpoint_data = load_checkpoint()
        processed_pans = checkpoint_data.get("processed_pans", [])
        results_dict = checkpoint_data.get("results", {})
        
        # Filter out already processed PANs
        pan_numbers = [pan for pan in pan_numbers if pan not in processed_pans]
        logger.info(f"Resuming from checkpoint. {len(processed_pans)} PANs already processed, {len(pan_numbers)} remaining.")
    
    # In test mode, only process the first PAN
    if test_mode and len(pan_numbers) > 1:
        first_pan = pan_numbers[0]
        pan_numbers = [first_pan]
        logger.info(f"TEST MODE: Processing only the first PAN number: {first_pan}")
    
    # Limit the number of PANs to process
    if limit is not None and len(pan_numbers) > limit:
        original_count = len(pan_numbers)
        pan_numbers = pan_numbers[:limit]
        logger.info(f"Limiting processing to the first {limit} PAN numbers out of {original_count} total unique PANs")
    
    if not pan_numbers:
        logger.info("No PANs to process. All PANs have already been processed.")
        print("\nNo PANs to process. All PANs have already been processed.")
        
        # Update Excel file with existing results
        if results_dict:
            update_excel_with_results(file_path, pan_df, gstin_df, results_dict)
        return
    
    logger.info(f"Starting processing of {len(pan_numbers)} PAN numbers")
    print(f"\nProcessing {len(pan_numbers)} PAN numbers...")
    
    # Set up Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize the browser
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.implicitly_wait(10)
        logger.info("Chrome driver initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Chrome driver: {e}")
        print(f"\nERROR: Failed to initialize Chrome driver: {e}")
        return
    
    try:
        # Navigate to the GST portal
        driver.get(GST_PORTAL_URL)
        # Wait for the page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "for_gstin"))
        )
        logger.info("Navigated to GST website")
        
        # Process PANs in batches
        batch_count = 0
        current_batch = []
        batch_results = {}
        
        for i, pan in enumerate(pan_numbers):
            try:
                logger.info(f"Processing PAN {i+1}/{len(pan_numbers)}: {pan}")
                print(f"Processing PAN {i+1}/{len(pan_numbers)}: {pan}")
                
                # Check if browser is still responsive
                try:
                    current_url = driver.current_url
                except Exception as e:
                    logger.error(f"Browser connection lost: {e}")
                    logger.info("Restarting browser...")
                    
                    # Restart the browser
                    try:
                        driver.quit()
                    except:
                        pass
                    
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
                    driver.implicitly_wait(10)
                    logger.info("Browser restarted")
                    
                    # Navigate to the GST website again
                    driver.get(GST_PORTAL_URL)
                    logger.info("Navigated to GST website after restart")
                
                # Clear any existing value and enter the PAN
                pan_input = driver.find_element(By.ID, "for_gstin")
                pan_input.clear()
                pan_input.send_keys(pan)
                logger.info(f"Entered PAN: {pan}")
                
                # Handle captcha
                logger.info("Starting captcha handling process...")
                if handle_captcha(driver, max_retries=MAX_RETRIES):
                    logger.info("Captcha solved successfully")
                    
                    # Wait for results to load
                    time.sleep(5)
                    
                    # Take a screenshot of the results page
                    screenshot_path = os.path.join(SCREENSHOT_DIR, f"results_page_{pan}_{int(time.time())}.png")
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"Saved results page screenshot to {screenshot_path}")
                    
                    # Extract search results
                    results = extract_search_results(driver)
                    
                    # Log the results
                    if TEST_MODE:
                        logger.debug(f"Detailed search results for PAN {pan}:")
                        for idx, result in enumerate(results):
                            logger.debug(f"  Result {idx+1}: {json.dumps(result, indent=2)}")
                    else:
                        logger.info(f"Search results: {results}")
                    
                    # Log the number of GSTINs found
                    gstin_count = sum(1 for r in results if "GSTIN" in r)
                    logger.info(f"Found {gstin_count} GSTINs for PAN {pan}")
                    
                    # Add to batch results
                    batch_results[pan] = results
                    current_batch.append(pan)
                    
                    # Add to overall results
                    results_dict[pan] = results
                    processed_pans.append(pan)
                    
                else:
                    logger.error(f"Failed to solve captcha for PAN {pan}")
                    batch_results[pan] = [{"Result": "Error: Failed to solve captcha"}]
                    current_batch.append(pan)
                    
                    # Add to overall results
                    results_dict[pan] = [{"Result": "Error: Failed to solve captcha"}]
                    processed_pans.append(pan)
                
                # Check if we've reached the batch size or the end of the list
                batch_count += 1
                if batch_count >= BATCH_SIZE or i == len(pan_numbers) - 1:
                    logger.info(f"Completed batch of {len(current_batch)} PANs")
                    
                    # Save checkpoint
                    save_checkpoint(processed_pans, results_dict)
                    
                    # Reset batch
                    batch_count = 0
                    current_batch = []
                    batch_results = {}
                
                # Add a small delay between requests to avoid overloading the server
                delay = random.uniform(DELAY_BETWEEN_REQUESTS[0], DELAY_BETWEEN_REQUESTS[1])
                time.sleep(delay)
                
                # Navigate back or refresh to get to the form again
                driver.refresh()
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing PAN {pan}: {e}")
                
                # Add error result to batch
                batch_results[pan] = [{"Result": f"Error: {str(e)}"}]
                current_batch.append(pan)
                
                # Add to overall results
                results_dict[pan] = [{"Result": f"Error: {str(e)}"}]
                processed_pans.append(pan)
                
                # Try to recover by refreshing the page
                try:
                    driver.refresh()
                    time.sleep(2)
                except:
                    logger.error("Failed to refresh page after error")
                    
                    # If we can't recover, restart the browser
                    try:
                        driver.quit()
                        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
                        driver.get(GST_PORTAL_URL)
                        logger.info("Restarted browser after error")
                    except Exception as e2:
                        logger.error(f"Failed to restart browser: {e2}")
                        break
        
        # Update Excel file with all results
        update_excel_with_results(file_path, pan_df, gstin_df, results_dict)
        
        logger.info(f"Processing complete. Successfully processed {len(processed_pans)} PAN numbers.")
        print(f"\nProcessing complete. Successfully processed {len(processed_pans)} PAN numbers.")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nERROR: Unexpected error: {e}")
    
    finally:
        # Close the browser
        try:
            driver.quit()
            logger.info("Browser closed")
        except:
            pass
        
        # Final update to Excel file if there are any results
        if results_dict:
            try:
                update_excel_with_results(file_path, pan_df, gstin_df, results_dict)
                logger.info("Final update to Excel file completed")
            except Exception as e:
                logger.error(f"Error during final Excel update: {e}")
                print(f"\nERROR: Failed to update Excel file: {e}")
        
        print(f"\nProcessing complete. Results have been saved to the file.")
        print(f"File location: {file_path}")
# ===== GSTIN DETAILS FUNCTIONS =====

def get_gstin_details(gstin):
    """
    Get details for a specific GSTIN from the GST portal.
    
    Args:
        gstin: The GSTIN to search for
        
    Returns:
        dict: Dictionary containing GSTIN details (Trade name, Date of registration, HSN)
              or error information
    """
    logger.info(f"Getting details for GSTIN: {gstin}")
    
    # Validate GSTIN format
    if not gstin or len(gstin) != 15:
        logger.error(f"Invalid GSTIN format: {gstin}")
        return {"error": "Invalid GSTIN format", "gstin": gstin}
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize the browser
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.implicitly_wait(10)
        logger.info("Chrome driver initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Chrome driver: {e}")
        return {"error": f"Failed to initialize Chrome driver: {str(e)}", "gstin": gstin}
    
    try:
        # Navigate to the GST portal
        driver.get(GST_GSTIN_SEARCH_URL)
        # Wait for the page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "for_gstin"))
        )
        logger.info("Navigated to GST GSTIN search website")
        
        # Clear any existing value and enter the GSTIN
        gstin_input = driver.find_element(By.ID, "for_gstin")
        gstin_input.clear()
        gstin_input.send_keys(gstin)
        logger.info(f"Entered GSTIN: {gstin}")
        
        # Handle captcha
        logger.info("Starting captcha handling process...")
        if handle_captcha(driver, max_retries=MAX_RETRIES):
            logger.info("Captcha solved successfully")
            
            # Wait for results to load
            time.sleep(5)
            
            # Take a screenshot of the results page
            screenshot_path = os.path.join(SCREENSHOT_DIR, f"results_page_{gstin}_{int(time.time())}.png")
            driver.save_screenshot(screenshot_path)
            logger.info(f"Saved results page screenshot to {screenshot_path}")
            
            # Extract GSTIN details
            details = extract_gstin_details(driver, gstin)
            
            # Log the details
            logger.info(f"GSTIN details: {details}")
            
            return details
        else:
            logger.error(f"Failed to solve captcha for GSTIN {gstin}")
            return {"error": "Failed to solve captcha", "gstin": gstin}
            
    except Exception as e:
        logger.error(f"Error getting details for GSTIN {gstin}: {e}")
        return {"error": str(e), "gstin": gstin}
    finally:
        # Close the browser
        try:
            driver.quit()
            logger.info("Browser closed")
        except:
            pass

def extract_gstin_details(driver, gstin):
    """
    Extract GSTIN details from the results page.
    
    Args:
        driver: Selenium WebDriver instance
        gstin: The GSTIN being searched
        
    Returns:
        dict: Dictionary containing GSTIN details
    """
    try:
        # Take a screenshot of the results page for debugging
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"gstin_details_{gstin}_{int(time.time())}.png")
        driver.save_screenshot(screenshot_path)
        logger.info(f"Saved GSTIN details page screenshot to {screenshot_path}")
        
        # Check if "No records found" message is present
        if "No records found" in driver.page_source:
            logger.info("No records found message detected")
            return {"error": "No records found", "gstin": gstin}
        
        # Initialize details dictionary
        details = {
            "gstin": gstin,
            "trade_name": "",
            "registration_date": "",
            "hsn_codes": [],
            # Add fields for Excel update
            "Trade_Name": "",
            "Registration_Date": "",
            "HSN_Codes": ""
        }
        
        # Extract trade name
        try:
            trade_name_element = driver.find_element(By.XPATH, "//td[contains(text(), 'Trade Name')]/following-sibling::td")
            trade_name = trade_name_element.text.strip()
            details["trade_name"] = trade_name
            details["Trade_Name"] = trade_name
            logger.info(f"Extracted trade name: {trade_name}")
        except Exception as e:
            logger.warning(f"Could not extract trade name: {e}")
        
        # Extract registration date
        try:
            reg_date_element = driver.find_element(By.XPATH, "//td[contains(text(), 'Date of Registration')]/following-sibling::td")
            reg_date = reg_date_element.text.strip()
            details["registration_date"] = reg_date
            details["Registration_Date"] = reg_date
            logger.info(f"Extracted registration date: {reg_date}")
        except Exception as e:
            logger.warning(f"Could not extract registration date: {e}")
        
        # Extract HSN codes
        try:
            hsn_elements = driver.find_elements(By.XPATH, "//td[contains(text(), 'HSN')]/following-sibling::td")
            if hsn_elements:
                for element in hsn_elements:
                    hsn_code = element.text.strip()
                    if hsn_code and hsn_code not in details["hsn_codes"]:
                        details["hsn_codes"].append(hsn_code)
                logger.info(f"Extracted HSN codes: {details['hsn_codes']}")
            else:
                # Try alternative approach for HSN codes
                hsn_table = driver.find_element(By.XPATH, "//table[contains(@class, 'table') and .//th[contains(text(), 'HSN')]]")
                if hsn_table:
                    rows = hsn_table.find_elements(By.TAG_NAME, "tr")
                    for row in rows[1:]:  # Skip header row
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if cells and len(cells) > 0:
                            hsn_code = cells[0].text.strip()
                            if hsn_code and hsn_code not in details["hsn_codes"]:
                                details["hsn_codes"].append(hsn_code)
                    logger.info(f"Extracted HSN codes (alternative): {details['hsn_codes']}")
        except Exception as e:
            logger.warning(f"Could not extract HSN codes: {e}")
        
        # Convert HSN codes list to string for Excel storage
        if details["hsn_codes"]:
            details["HSN_Codes"] = ", ".join(details["hsn_codes"])
        
        return details
    except Exception as e:
        logger.error(f"Error extracting GSTIN details: {e}")
        return {"error": str(e), "gstin": gstin}

# ===== MAIN FUNCTION =====

def main():
    """Main entry point for the script."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Enhanced PAN to GSTIN Mapper")
    parser.add_argument("--file", "-f", help="Path to the Excel file containing PAN numbers")
    parser.add_argument("--headless", "-hl", action="store_true", help="Run in headless mode (no browser UI)")
    parser.add_argument("--test", "-t", action="store_true", help="Run in test mode (process only one PAN with detailed logging)")
    parser.add_argument("--limit", "-l", type=int, help="Maximum number of unique PAN numbers to process")
    parser.add_argument("--resume", "-r", action="store_true", help="Resume from checkpoint")
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no arguments provided, use interactive mode
    if len(sys.argv) == 1:
        print("=" * 70)
        print("                ENHANCED PAN TO GSTIN MAPPER                ")
        print("=" * 70)
        print("This script automates the process of extracting GSTINs for PAN numbers")
        print("from the GST portal and saving them to a two-sheet Excel file.")
        print("=" * 70)
        
        # Ask for the file path
        print("\nEnter the path to the Excel file containing PAN numbers:")
        file_path = input("Path: ").strip()
        
        if not file_path:
            print("Error: No file path provided.")
            return
        
        # Ask for headless mode
        headless_input = input("\nRun in headless mode (no browser UI)? (y/n) [default=n]: ").strip().lower()
        headless = headless_input == 'y'
        
        # Ask for test mode
        test_input = input("\nRun in test mode (process only one PAN)? (y/n) [default=n]: ").strip().lower()
        test_mode = test_input == 'y'
        
        # Ask for limit
        limit_input = input("\nEnter the maximum number of PAN numbers to process [default=all]: ").strip()
        limit = int(limit_input) if limit_input and limit_input.isdigit() else None
        
        # Ask for resume
        resume_input = input("\nResume from checkpoint? (y/n) [default=n]: ").strip().lower()
        resume = resume_input == 'y'
    else:
        # Use command-line arguments
        file_path = args.file
        headless = args.headless
        test_mode = args.test
        limit = args.limit
        resume = args.resume
        
        if not file_path:
            print("Error: No file path provided. Use --file or -f to specify the file path.")
            return
    
    print("\nStarting Enhanced PAN to GSTIN mapping process...")
    if test_mode:
        print("RUNNING IN TEST MODE - Will process only one PAN number with detailed logging")
    elif limit:
        print(f"Will process up to {limit} unique PAN numbers")
    else:
        print("Will process all unique PAN numbers")
        
    if resume:
        print("Resuming from checkpoint")
    
    process_pan_numbers(file_path, headless, test_mode, limit, resume)


if __name__ == "__main__":
    main()