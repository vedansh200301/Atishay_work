import time
import pandas as pd
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# -----------------------
# Step 1: Set up logging
# -----------------------
logging.basicConfig(
    filename="gst_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())


# -----------------------------------
# Step 2: Initialize Selenium Driver
# -----------------------------------
def setup_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # Speed optimizations
    options.add_argument('--disable-images')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-ipc-flooding-protection')
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(10)  # Reduced from 30
        driver.implicitly_wait(2)  # Add implicit wait
        logger.info("Chrome WebDriver launched successfully.")
        return driver
    except Exception as e:
        logger.error(f"Failed to launch ChromeDriver: {e}")
        raise


# ------------------------------------------------
# Step 3: Extract GSTIN Data from SignalX Website
# ------------------------------------------------
def extract_info_by_gstin(driver, gstin):
    logger.info(f"Processing GSTIN: {gstin}")
    try:
        driver.get("https://signalx.ai/gst-verification-2/")

        wait = WebDriverWait(driver, 8)  # Reduced from 20

        # Enter GSTIN
        input_box = wait.until(EC.presence_of_element_located((By.ID, "gstinField")))
        input_box.clear()
        input_box.send_keys(gstin)

        # Click button - simplified since we know the correct selector
        check_button = wait.until(EC.element_to_be_clickable((By.ID, "checkDetailsButton")))
        check_button.click()

        # Wait for results and extract data
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//h6[contains(text(),'Effective Date of registration')]/following-sibling::p")
        ))

        trade_name = driver.find_element(By.XPATH, "//h6[contains(text(),'Trade Name')]/following-sibling::p").text.strip()
        reg_date = driver.find_element(By.XPATH, "//h6[contains(text(),'Effective Date of registration')]/following-sibling::p").text.strip()
        hsn_elements = driver.find_elements(By.XPATH, "//table//tbody//tr/td[1]")
        hsn_codes = ', '.join([el.text.strip() for el in hsn_elements if el.text.strip()])

        logger.info(f"Extracted data for {gstin}")
        return gstin, trade_name, reg_date, hsn_codes

    except TimeoutException:
        logger.error(f"Timeout occurred while processing GSTIN: {gstin}")
    except WebDriverException as e:
        logger.error(f"WebDriver error for GSTIN {gstin}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error for GSTIN {gstin}: {e}")

    return gstin, "", "", ""


# --------------------------------------------
# Step 4: Process Excel File and Write Output
# --------------------------------------------
def update_excel_with_gst_details(input_excel, output_excel):
    logger.info(f"Reading input file: {input_excel}")
    df = pd.read_excel(input_excel)

    gstins = df['GSTIN'].dropna().astype(str).str.strip().tolist()
    logger.info(f"Total GSTINs found: {len(gstins)}")

    # Single driver instance for all GSTINs
    driver = setup_driver()
    
    results = []
    for idx, gstin in enumerate(gstins, 1):
        logger.info(f"Processing {idx}/{len(gstins)}: {gstin}")
        result = extract_info_by_gstin(driver, gstin)
        results.append(result)

    driver.quit()
    logger.info("WebDriver closed.")

    logger.info("Merging results into dataframe...")
    result_df = pd.DataFrame(results, columns=['GSTIN', 'Trade_Name', 'Registration_Date', 'HSN_Codes'])
    df = df.drop(columns=['Trade_Name', 'Registration_Date', 'HSN_Codes'], errors='ignore')
    df = df.merge(result_df, on='GSTIN', how='left')
    df['Last_Updated'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')

    logger.info(f"Saving to output file: {output_excel}")
    df.to_excel(output_excel, index=False)
    logger.info("Excel file saved successfully.")


# -----------------------
# Step 5: Run the Script
# -----------------------
if __name__ == "__main__":
    update_excel_with_gst_details("nn.xlsx", "updated_output.xlsx")
