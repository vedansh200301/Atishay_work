# GSTIN Details Retrieval System

This system automates the process of retrieving GSTIN (Goods and Services Tax Identification Number) details from multiple sources, including the GST portal and SignalX. It provides a web interface for uploading files, processing them, and downloading enriched results.

## Project Overview

The system follows a three-step process:

1. **PAN to GSTIN Mapping**: Extracts GSTINs for each PAN number from the GST portal
2. **SignalX Data Enrichment**: Retrieves additional details (Trade Name, Registration Date, HSN Codes) from SignalX
3. **Consolidated Results**: Provides a downloadable Excel file with all the enriched data

## Key Features

## Features

- **Web Interface**: User-friendly Flask web application for file upload and processing
- **Automated Processing**: Handles the entire workflow from PAN to enriched GSTIN data
- **Captcha Solving**: Uses TrueCaptcha API to automatically solve captchas
- **Data Enrichment**: Retrieves comprehensive GSTIN details from SignalX
- **Real-time Progress**: Shows processing status and updates in real-time
- **Error Handling**: Robust error handling and recovery mechanisms
- **Downloadable Results**: Provides enriched Excel files for download

## Components

- **app.py**: Main Flask web application
- **pan_gstin_mapper_enhanced.py**: Core module for PAN to GSTIN mapping
- **ultimate.py**: Module for retrieving additional GSTIN details from SignalX
- **templates/**: HTML templates for the web interface
- **static/**: CSS and JavaScript files for the web interface

## Requirements

- Python 3.6+
- Chrome browser
- Required Python packages (see requirements.txt):
  - Flask
  - pandas
  - openpyxl
  - selenium
  - requests
  - Werkzeug

## Installation

### Standard Installation

1. Clone this repository:
   ```
   git clone https://github.com/vedansh200301/Atishay_work.git
   cd Atishay_work
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Make sure Chrome browser is installed (Chrome WebDriver will be automatically managed by the script)

4. Create necessary directories:
   ```
   mkdir -p uploads results screenshots
   ```

### Docker Installation

1. Clone this repository:
   ```
   git clone https://github.com/vedansh200301/Atishay_work.git
   cd Atishay_work
   ```

2. Build and run with Docker Compose:
   ```
   docker-compose up -d
   ```

3. The application will be available at http://localhost:5000

## Usage

### Running with Python

1. Start the Flask application:
   ```
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

### Running with Docker

1. The application should be running after the Docker installation steps
2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

### Using the Application

1. Upload an Excel file containing PAN numbers

2. Configure processing parameters:
   - Headless Mode: Run browser in background
   - Test Mode: Process only a few PANs for testing
   - Processing Limit: Maximum number of PANs to process
   - Resume: Continue from last checkpoint

3. Click "Upload and Start Processing"

4. Monitor the progress on the results page

5. When processing completes, download the enriched file

## Process Flow

The system follows this automated process flow:

1. User uploads an Excel file with PAN numbers
2. The file is processed by pan_gstin_mapper_enhanced.py to extract GSTINs
3. The output is automatically fed to ultimate.py for SignalX data enrichment
4. The final enriched file is made available for download
5. The user is shown a "Process completed" message

## Documentation

For more detailed information, refer to these documentation files:

- [Flask Application Guide](README_FLASK.md)
- [GSTIN Details Guide](GSTIN_DETAILS_GUIDE.md)

## Troubleshooting

### Standard Installation

- **File Upload Issues**: Ensure the file is in Excel (.xlsx, .xls) or CSV format
- **Processing Errors**: Check the logs (flask_pan_gstin.log, pan_gstin_mapper_enhanced.log)
- **Browser Automation Issues**: Try disabling headless mode for debugging
- **Captcha Problems**: Verify TrueCaptcha API credentials are valid
- **SignalX Timeouts**: The system will automatically retry with increased timeouts

### Docker Installation

- **Container Not Starting**: Check Docker logs with `docker-compose logs`
- **Permission Issues**: Ensure the volumes have correct permissions
- **Browser Issues**: The Docker container includes Chrome and ChromeDriver
- **Port Conflicts**: If port 5000 is in use, modify the port mapping in docker-compose.yml

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Result Handling

The script extracts and saves search results back to the Excel file:

1. For each PAN number, the script will add the following columns to the Excel file:
   - `Result`: Contains "No records found" or error messages
   - `GSTIN`: The GSTIN number if found
   - `GSTIN Status`: The status of the GSTIN (e.g., "Active")
   - `State`: The state associated with the GSTIN

2. The Excel file is updated after each PAN number is processed, so you can see the progress even if the script is interrupted.

## GSTIN Details Retrieval

The tool can retrieve additional details for each GSTIN beyond the basic registration status:

1. **Trade Name**: The registered business name associated with the GSTIN
2. **Date of Registration**: When the GSTIN was registered with GST authorities
3. **HSN Codes**: Product/service categories the business is registered for

These additional details enhance the tool's functionality by:
- Providing more comprehensive business verification
- Enabling better entity matching and due diligence
- Offering insights into business activities through HSN codes

For more detailed information about this feature, refer to the [GSTIN_DETAILS_GUIDE.md](GSTIN_DETAILS_GUIDE.md) file.

## Logging

All activities are logged to:
- Console output
- `pan_automation.log` file

The log file contains detailed information about each step of the process, including:
- Excel file reading and writing
- PAN number validation
- Browser interactions
- Captcha handling attempts
- Search result extraction
- Errors and recovery attempts

## Troubleshooting

- If the script fails to start, ensure all dependencies are installed
- If the browser doesn't open, check your Chrome installation
- If PANs aren't being read correctly, verify your Excel file format
- If captcha handling consistently fails, check the screenshots in the `screenshots` directory
- If results aren't being saved correctly, check the Excel file permissions
- Check the log file for detailed error messages and debugging information

## TrueCaptcha API Troubleshooting

If you're having issues with the TrueCaptcha API:

1. Check if the API endpoint is accessible
2. Verify your API credentials are correct
3. Make sure the captcha image is clear and readable
4. Try running the `test_new_truecaptcha.py` script to test the API directly

## Usage Instructions

1. Prepare your Excel file with PAN numbers in a column named 'PAN NO.'
2. Run the final version of the script:
   ```
   python3 pan_automation_final.py
   ```
3. Follow the interactive prompts to configure:
   - Number of PAN numbers to process
   - Starting row
   - Headless mode option
4. The script will process each PAN number and save the results back to the Excel file
5. Check the Excel file for the results after the script completes

## Utility Scripts

This package includes additional utility scripts to help with setup and testing:

### 1. examine_excel.py

A simple script to examine the structure of your Excel file:

```
python3 examine_excel.py
```

This will display information about the Excel file, including:
- Number of rows and columns
- Column names
- Sample PAN numbers

### 2. test_new_truecaptcha.py

A tool to test the TrueCaptcha API with a captcha image:

```
python3 test_new_truecaptcha.py captcha.png
```

This script will:
1. Use your TrueCaptcha API credentials
2. Send the captcha image to the API
3. Display the API response and solution