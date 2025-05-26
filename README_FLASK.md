# PAN-GSTIN Mapper Flask Web Application

This Flask web application provides a user-friendly interface for the enhanced PAN-GSTIN mapper, allowing users to upload Excel/CSV files containing PAN numbers and process them to extract corresponding GSTINs from the GST portal.

## Features

- **File Upload**: Upload Excel (.xlsx, .xls) or CSV files containing PAN numbers
- **Parameter Configuration**: Set processing parameters (headless mode, test mode, processing limit, etc.)
- **Background Processing**: Process PAN-GSTIN mapping in the background
- **Real-time Progress Updates**: View progress and status of ongoing operations
- **Results Download**: Download the processed results file
- **Job History**: View and manage previous mapping operations

## Installation

### Prerequisites

- Python 3.6 or higher
- pip (Python package installer)
- All dependencies required by the enhanced PAN-GSTIN mapper

### Setup

1. Clone or download this repository to your local machine.

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Make sure the enhanced PAN-GSTIN mapper (`pan_gstin_mapper_enhanced.py`) is in the same directory as the Flask application.

## Usage

### Starting the Application

Run the Flask application:

```bash
python app.py
```

The application will start and be accessible at `http://localhost:5000` in your web browser.

### Using the Web Interface

1. **Home Page**:
   - Upload an Excel/CSV file containing PAN numbers
   - Configure processing parameters:
     - Headless Mode: Run browser in background without UI (recommended)
     - Test Mode: Process only the first PAN number with detailed logging
     - Processing Limit: Maximum number of PAN numbers to process
     - Resume from Checkpoint: Continue from last saved checkpoint if available
   - Click "Upload and Start Processing" to begin

2. **Results Page**:
   - View real-time progress of the mapping operation
   - See job details and status
   - Download the results file when processing is complete
   - The downloaded file will be a simplified CSV with only PAN_Reference and GSTIN columns

3. **History Page**:
   - View all previous mapping operations
   - Check their status and parameters
   - Download results from completed jobs
   - Remove jobs from history

## File Structure

```
/
├── app.py                  # Main Flask application
├── pan_gstin_mapper_enhanced.py  # Enhanced PAN-GSTIN mapper
├── static/                 # Static files
│   ├── css/                # CSS stylesheets
│   │   └── style.css       # Custom CSS
│   └── js/                 # JavaScript files
│       └── script.js       # Custom JavaScript
├── templates/              # HTML templates
│   ├── layout.html         # Base template
│   ├── index.html          # Home page template
│   ├── results.html        # Results page template
│   └── history.html        # History page template
├── uploads/                # Uploaded files (created automatically)
├── results/                # Results files (created automatically)
└── README_FLASK.md         # This README file
```

## Configuration

The application has several configuration options in the `app.py` file:

- `UPLOAD_FOLDER`: Directory for uploaded files (default: 'uploads')
- `RESULTS_FOLDER`: Directory for results files (default: 'results')
- `ALLOWED_EXTENSIONS`: Allowed file extensions (default: xlsx, xls, csv)
- `MAX_CONTENT_LENGTH`: Maximum upload file size (default: 16MB)

## Troubleshooting

### Common Issues

1. **File Upload Errors**:
   - Ensure the file is in a supported format (Excel or CSV)
   - Check that the file size is under 16MB
   - Verify that the file contains a column named "PAN" with valid PAN numbers

2. **Processing Errors**:
   - Check the Flask application logs (`flask_pan_gstin.log`)
   - Check the PAN-GSTIN mapper logs (`pan_gstin_mapper_enhanced.log`)
   - Ensure the Chrome WebDriver is properly installed and compatible with your Chrome version

3. **Browser Automation Issues**:
   - Try disabling headless mode for debugging
   - Check if the GST portal website structure has changed
   - Verify TrueCaptcha API credentials are valid

## Security Considerations

- This application is designed for local use or within a trusted network
- It does not implement authentication or advanced security features
- Sensitive information (like TrueCaptcha API credentials) should be properly secured
- Consider implementing additional security measures if deploying in a production environment

## GSTIN Details Retrieval Feature

This feature allows you to retrieve and store additional details for GSTINs, including:

- Trade Name
- Date of Registration
- HSN Codes

### Download Format

When you download results from the application, the file will be a simplified CSV containing only the essential GSTIN information. This makes it easier to work with the data without unnecessary columns. The CSV file includes only:

- PAN_Reference: The PAN number associated with the GSTIN
- GSTIN: The GSTIN number

This simplified format is ideal for:
- Importing into other systems
- Quick reference of PAN-GSTIN mappings
- Further processing with other tools

### Benefits

- **Enhanced Data**: Get more comprehensive information about each GSTIN
- **Better Decision Making**: Use trade names and registration dates for verification
- **Business Intelligence**: HSN codes provide insights into business activities
- **Batch Processing**: Update multiple GSTINs in a single operation

### How to Use

#### Viewing Details for a Single GSTIN

1. After processing PAN numbers, go to the Results page
2. In the GSTIN Information table, click on any GSTIN
3. A modal will appear showing detailed information:
   - Trade Name
   - Registration Date
   - HSN Codes (if available)

![GSTIN Details Modal](screenshots/results_page_ABACS5056L_1747827629.png)
*Figure 4: GSTIN Details Modal*

#### Batch Updating Multiple GSTINs

1. On the Results page, click the "Update GSTIN Details" button
2. In the modal that appears, click "Start Update Process"
3. The system will retrieve details for all GSTINs in the current job
4. Progress will be displayed in real-time
5. Once complete, you can download the updated Excel file

![Batch Update Process](screenshots/results_page_1747827114.png)
*Figure 5: Batch Update Process*

### Technical Implementation

The GSTIN details retrieval feature uses the following components:

- Backend API endpoint (`/gstin_details/<gstin>`) for retrieving details for a single GSTIN
- Batch processing endpoint (`/update_gstin_details`) for updating multiple GSTINs
- Enhanced mapper function `get_gstin_details()` that extracts data from the GST portal
- Excel update function `update_excel_with_gstin_details()` that stores the retrieved data

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- This application uses the enhanced PAN-GSTIN mapper for the core functionality
- Built with Flask, Bootstrap, and other open-source libraries

## Testing

The application includes a comprehensive test suite to verify its functionality. The test script `test_flask_app.py` tests all major components of the Flask application.

### Running Tests

To run the tests:

```bash
python test_flask_app.py
```

### Test Coverage

The test suite covers the following functionality:

1. **Basic Application Functionality**:
   - Application startup and home page rendering
   - File upload with various parameters
   - Results page display
   - Job status API
   - History page
   - File download
   - Job clearing

2. **Integration Testing**:
   - Integration with the enhanced PAN-GSTIN mapper
   - Parameter passing between Flask app and mapper

3. **Error Handling**:
   - Invalid file uploads
   - Missing files
   - Empty filenames

### Sample Test File

A sample test file `test_sample_pans.xlsx` is included for testing purposes. It contains the following test PAN numbers:

- ABCDE1234F (John Doe)
- PQRST5678G (Jane Smith)
- LMNOP9012H (Bob Johnson)

### Test Results

The test suite has been run and verified that the Flask application works correctly with the enhanced PAN-GSTIN mapper. All tests pass successfully, confirming that:

1. The application starts correctly and renders all pages
2. File upload works with proper parameter handling
3. The application integrates correctly with the enhanced PAN-GSTIN mapper
4. Results are displayed and can be downloaded
5. Job history is maintained and can be managed

![Home Page](screenshots/flask_home_page.png)
*Figure 1: Flask Application Home Page*

![Results Page](screenshots/flask_results_page.png)
*Figure 2: Results Page Showing Processing Status*

![History Page](screenshots/flask_history_page.png)
*Figure 3: Job History Page*