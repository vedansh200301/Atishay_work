#!/usr/bin/env python3
"""
Flask Web Application for PAN-GSTIN Mapper

This application provides a web interface for the enhanced PAN-GSTIN mapper,
allowing users to upload Excel/CSV files containing PAN numbers and process
them to extract corresponding GSTINs from the GST portal.
"""

import os
import time
import json
import uuid
import pandas as pd
import threading
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import logging
import random

# Import the enhanced PAN-GSTIN mapper
import pan_gstin_mapper_enhanced as mapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flask_pan_gstin.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# We're now passing the datetime directly to each template render call

# Configuration
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Global variables to track jobs
jobs = {}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_file_in_background(job_id, file_path, headless, test_mode, limit, resume):
    """Process the file in a background thread"""
    try:
        logger.info(f"Starting background processing for job {job_id}")
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['start_time'] = datetime.now().isoformat()
        
        # Call the enhanced PAN-GSTIN mapper
        mapper.process_pan_numbers(file_path, headless, test_mode, limit, resume)
        
        # Update job status
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['end_time'] = datetime.now().isoformat()
        jobs[job_id]['result_file'] = file_path
        
        logger.info(f"Background processing completed for job {job_id}")
        
        # Save updated jobs to file
        save_jobs_to_file()
    except Exception as e:
        logger.error(f"Error in background processing for job {job_id}: {e}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
        jobs[job_id]['end_time'] = datetime.now().isoformat()
        save_jobs_to_file()

def save_jobs_to_file():
    """Save jobs data to a JSON file"""
    try:
        with open('jobs.json', 'w') as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving jobs data: {e}")

def load_jobs_from_file():
    """Load jobs data from a JSON file"""
    global jobs
    try:
        if os.path.exists('jobs.json'):
            with open('jobs.json', 'r') as f:
                jobs = json.load(f)
    except Exception as e:
        logger.error(f"Error loading jobs data: {e}")
        jobs = {}

@app.route('/')
def home():
    """Home page with file upload form"""
    return render_template('index.html', now=datetime.now())

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start processing"""
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Secure the filename and save the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(file_path)
        
        # Get parameters from form
        headless = 'headless' in request.form
        test_mode = 'test_mode' in request.form
        resume = 'resume' in request.form
        limit = request.form.get('limit', '')
        limit = int(limit) if limit and limit.isdigit() else None
        
        # Create a job entry
        jobs[job_id] = {
            'id': job_id,
            'filename': filename,
            'file_path': file_path,
            'status': 'queued',
            'created_at': datetime.now().isoformat(),
            'parameters': {
                'headless': headless,
                'test_mode': test_mode,
                'limit': limit,
                'resume': resume
            }
        }
        
        # Save jobs to file
        save_jobs_to_file()
        
        # Start processing in background
        thread = threading.Thread(
            target=process_file_in_background,
            args=(job_id, file_path, headless, test_mode, limit, resume)
        )
        thread.daemon = True
        thread.start()
        
        # Redirect to results page
        return redirect(url_for('results', job_id=job_id))
    
    flash('Invalid file type. Please upload an Excel or CSV file.')
    return redirect(url_for('home'))

@app.route('/results/<job_id>')
def results(job_id):
    """Results page showing progress and final results"""
    if job_id not in jobs:
        flash('Job not found')
        return redirect(url_for('home'))
    
    return render_template('results.html', job=jobs[job_id], now=datetime.now())

@app.route('/job_status/<job_id>')
def job_status(job_id):
    """API endpoint to get job status"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    # If job is processing, check for progress
    if jobs[job_id]['status'] == 'processing':
        # Try to get progress from checkpoint file
        try:
            if os.path.exists(mapper.CHECKPOINT_FILE):
                with open(mapper.CHECKPOINT_FILE, 'r') as f:
                    checkpoint_data = json.load(f)
                    processed_count = len(checkpoint_data.get('processed_pans', []))
                    jobs[job_id]['progress'] = {
                        'processed_count': processed_count,
                        'timestamp': checkpoint_data.get('timestamp')
                    }
        except Exception as e:
            logger.error(f"Error reading checkpoint file: {e}")
    
    return jsonify(jobs[job_id])

def prepare_gstin_only_file(original_file_path):
    """
    Create a new Excel or CSV file with PAN_Reference, GSTIN, and GSTIN Status columns
    from the GSTIN sheet of the original file.
    
    Args:
        original_file_path: Path to the original Excel file with both sheets
        
    Returns:
        str: Path to the new file with PAN_Reference, GSTIN, and GSTIN Status columns
    """
    try:
        logger.info(f"Preparing simplified GSTIN file from {original_file_path}")
        
        # Check if the file exists
        if not os.path.exists(original_file_path):
            logger.error(f"Original file not found: {original_file_path}")
            return None
            
        # Check if it's a CSV file
        file_ext = os.path.splitext(original_file_path)[1].lower()
        is_csv = file_ext == '.csv'
        
        # Read the GSTIN data
        try:
            if is_csv:
                gstin_df = pd.read_csv(original_file_path)
                logger.info(f"Read CSV file with {len(gstin_df)} rows")
            else:
                gstin_df = pd.read_excel(original_file_path, sheet_name=mapper.GSTIN_SHEET_NAME, engine='openpyxl')
                logger.info(f"Read GSTIN sheet with {len(gstin_df)} rows")
        except Exception as e:
            logger.error(f"Error reading GSTIN data: {e}")
            return None
        
        # Filter to keep PAN_Reference, GSTIN, and GSTIN Status columns
        if "PAN_Reference" in gstin_df.columns and "GSTIN" in gstin_df.columns and "GSTIN Status" in gstin_df.columns:
            simplified_df = gstin_df[["PAN_Reference", "GSTIN", "GSTIN Status"]]
            logger.info(f"Filtered to keep PAN_Reference, GSTIN, and GSTIN Status columns")
        elif "PAN_Reference" in gstin_df.columns and "GSTIN" in gstin_df.columns:
            simplified_df = gstin_df[["PAN_Reference", "GSTIN"]]
            logger.info(f"GSTIN Status column not found, keeping only PAN_Reference and GSTIN columns")
        else:
            logger.warning(f"Required columns not found, keeping all columns")
            simplified_df = gstin_df
            
        # Create a temporary file for the simplified data
        temp_dir = os.path.join(app.config['RESULTS_FOLDER'], 'temp')
        os.makedirs(temp_dir, exist_ok=True, mode=0o777)  # Add mode parameter for full permissions
        
        # Generate a unique filename
        filename = os.path.basename(original_file_path)
        base_name = os.path.splitext(filename)[0]
        
        # Save as CSV by default for simplicity
        simplified_path = os.path.abspath(os.path.join(temp_dir, f"{base_name}_simplified_{int(time.time())}.csv"))
        
        # Save the simplified data
        simplified_df.to_csv(simplified_path, index=False)
        logger.info(f"Created simplified file at {simplified_path}")
        
        # Check if the file was created and has content
        if os.path.exists(simplified_path):
            file_size = os.path.getsize(simplified_path)
            logger.info(f"Created file size: {file_size} bytes")
            if file_size == 0:
                logger.warning("Warning: Created file is empty!")
        else:
            logger.error(f"Error: File was not created at {simplified_path}")
        
        return simplified_path
        
    except Exception as e:
        logger.error(f"Error preparing GSTIN-only file: {e}")
        return None

@app.route('/download/<job_id>')
def download_results(job_id):
    """Download the results file with only the GSTIN sheet"""
    if job_id not in jobs or 'result_file' not in jobs[job_id]:
        flash('Results file not found')
        return redirect(url_for('home'))
    
    original_file = jobs[job_id]['result_file']
    
    # Prepare a file with only the GSTIN sheet
    gstin_only_file = prepare_gstin_only_file(original_file)
    
    if gstin_only_file:
        # Get the original filename but add "_simplified" before the extension
        original_filename = os.path.basename(original_file)
        base_name = os.path.splitext(original_filename)[0]
        download_filename = f"{base_name}_simplified.csv"
        
        return send_file(gstin_only_file, as_attachment=True, download_name=download_filename)
    else:
        # Fall back to the original file if there was an error
        logger.warning(f"Falling back to original file for download: {original_file}")
        return send_file(original_file, as_attachment=True)

@app.route('/history')
def history():
    """History page showing previous mapping operations"""
    return render_template('history.html', jobs=jobs, now=datetime.now())

@app.route('/clear_job/<job_id>', methods=['POST'])
def clear_job(job_id):
    """Remove a job from history"""
    if job_id in jobs:
        # If there's a file associated with this job, we might want to delete it
        # Uncomment the following lines to delete the file
        # if 'file_path' in jobs[job_id] and os.path.exists(jobs[job_id]['file_path']):
        #     os.remove(jobs[job_id]['file_path'])
        
        del jobs[job_id]
        save_jobs_to_file()
        flash('Job removed from history')
    
    return redirect(url_for('history'))

@app.route('/gstin_details/<gstin>')
def gstin_details(gstin):
    """API endpoint to get GSTIN details and update Excel file"""
    try:
        logger.info(f"Received request for GSTIN details: {gstin}")
        
        # Validate GSTIN format
        if not gstin or len(gstin) != 15:
            logger.error(f"Invalid GSTIN format: {gstin}")
            return jsonify({
                'error': 'Invalid GSTIN format',
                'gstin': gstin
            }), 400
        
        # Get GSTIN details using the enhanced mapper
        details = mapper.get_gstin_details(gstin)
        
        # Check if there was an error
        if 'error' in details:
            logger.error(f"Error getting GSTIN details: {details['error']}")
            return jsonify(details), 404 if details['error'] == 'No records found' else 500
        
        # Find the most recent Excel file to update
        excel_file = None
        for job_id, job in jobs.items():
            if job['status'] == 'completed' and 'result_file' in job:
                if excel_file is None or os.path.getmtime(job['result_file']) > os.path.getmtime(excel_file):
                    excel_file = job['result_file']
        
        # Update Excel file with GSTIN details if a file was found
        if excel_file and os.path.exists(excel_file):
            logger.info(f"Updating Excel file {excel_file} with details for GSTIN: {gstin}")
            update_success = mapper.update_excel_with_gstin_details(excel_file, gstin, details)
            if update_success:
                details['excel_updated'] = True
                details['excel_file'] = os.path.basename(excel_file)
                logger.info(f"Successfully updated Excel file with GSTIN details")
            else:
                details['excel_updated'] = False
                details['excel_update_error'] = "Failed to update Excel file"
                logger.warning(f"Failed to update Excel file with GSTIN details")
        else:
            details['excel_updated'] = False
            details['excel_update_error'] = "No suitable Excel file found"
            logger.warning(f"No suitable Excel file found for updating GSTIN details")
        
        # Return the details as JSON
        logger.info(f"Successfully retrieved GSTIN details for {gstin}")
        return jsonify(details)
        
    except Exception as e:
        logger.error(f"Unexpected error in GSTIN details endpoint: {e}")
        return jsonify({
            'error': str(e),
            'gstin': gstin
        }), 500

@app.route('/update_gstin_details', methods=['POST'])
def update_gstin_details():
    """API endpoint to update Excel file with details for multiple GSTINs"""
    try:
        # Get the list of GSTINs from the request
        data = request.get_json()
        if not data or 'gstins' not in data or not isinstance(data['gstins'], list):
            return jsonify({
                'error': 'Invalid request. Expected JSON with "gstins" list'
            }), 400
            
        gstins = data['gstins']
        logger.info(f"Received request to update details for {len(gstins)} GSTINs")
        
        # Validate GSTINs
        valid_gstins = []
        invalid_gstins = []
        for gstin in gstins:
            if gstin and len(gstin) == 15:
                valid_gstins.append(gstin)
            else:
                invalid_gstins.append(gstin)
                
        if not valid_gstins:
            return jsonify({
                'error': 'No valid GSTINs provided',
                'invalid_gstins': invalid_gstins
            }), 400
            
        # Find the most recent Excel file to update
        excel_file = None
        for job_id, job in jobs.items():
            if job['status'] == 'completed' and 'result_file' in job:
                if excel_file is None or os.path.getmtime(job['result_file']) > os.path.getmtime(excel_file):
                    excel_file = job['result_file']
        
        if not excel_file or not os.path.exists(excel_file):
            return jsonify({
                'error': 'No suitable Excel file found for updating',
                'valid_gstins': valid_gstins,
                'invalid_gstins': invalid_gstins
            }), 404
            
        # Create a job for batch update
        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            'id': job_id,
            'type': 'batch_gstin_update',
            'status': 'processing',
            'created_at': datetime.now().isoformat(),
            'start_time': datetime.now().isoformat(),
            'gstins': valid_gstins,
            'excel_file': excel_file,
            'progress': {
                'total': len(valid_gstins),
                'processed': 0,
                'successful': 0,
                'failed': 0
            },
            'results': []
        }
        save_jobs_to_file()
        
        # Start processing in background
        thread = threading.Thread(
            target=process_batch_gstin_update,
            args=(job_id, valid_gstins, excel_file)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'processing',
            'message': f'Started batch update for {len(valid_gstins)} GSTINs',
            'valid_gstins': valid_gstins,
            'invalid_gstins': invalid_gstins
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in update_gstin_details endpoint: {e}")
        return jsonify({
            'error': str(e)
        }), 500

def process_batch_gstin_update(job_id, gstins, excel_file):
    """Process batch GSTIN update in background"""
    try:
        logger.info(f"Starting batch GSTIN update for job {job_id} with {len(gstins)} GSTINs")
        
        for i, gstin in enumerate(gstins):
            try:
                # Update progress
                jobs[job_id]['progress']['processed'] = i + 1
                
                # Get GSTIN details
                logger.info(f"Processing GSTIN {i+1}/{len(gstins)}: {gstin}")
                details = mapper.get_gstin_details(gstin)
                
                # Check if there was an error
                if 'error' in details:
                    logger.warning(f"Error getting details for GSTIN {gstin}: {details['error']}")
                    jobs[job_id]['progress']['failed'] += 1
                    jobs[job_id]['results'].append({
                        'gstin': gstin,
                        'success': False,
                        'error': details['error']
                    })
                    continue
                
                # Update Excel file with GSTIN details
                update_success = mapper.update_excel_with_gstin_details(excel_file, gstin, details)
                
                if update_success:
                    logger.info(f"Successfully updated Excel file with details for GSTIN {gstin}")
                    jobs[job_id]['progress']['successful'] += 1
                    jobs[job_id]['results'].append({
                        'gstin': gstin,
                        'success': True,
                        'details': details
                    })
                else:
                    logger.warning(f"Failed to update Excel file with details for GSTIN {gstin}")
                    jobs[job_id]['progress']['failed'] += 1
                    jobs[job_id]['results'].append({
                        'gstin': gstin,
                        'success': False,
                        'error': 'Failed to update Excel file'
                    })
                
                # Save jobs to file after each GSTIN
                save_jobs_to_file()
                
                # Add a small delay to avoid overwhelming the GST portal
                time.sleep(random.uniform(1, 3))  # Using random module for delay
                
            except Exception as e:
                logger.error(f"Error processing GSTIN {gstin}: {e}")
                jobs[job_id]['progress']['failed'] += 1
                jobs[job_id]['results'].append({
                    'gstin': gstin,
                    'success': False,
                    'error': str(e)
                })
                save_jobs_to_file()
        
        # Update job status
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['end_time'] = datetime.now().isoformat()
        save_jobs_to_file()
        
        logger.info(f"Completed batch GSTIN update for job {job_id}")
        
    except Exception as e:
        logger.error(f"Error in batch GSTIN update for job {job_id}: {e}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
        jobs[job_id]['end_time'] = datetime.now().isoformat()
        save_jobs_to_file()

@app.route('/batch_update_status/<job_id>')
def batch_update_status(job_id):
    """API endpoint to get batch update job status"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    if jobs[job_id]['type'] != 'batch_gstin_update':
        return jsonify({'error': 'Not a batch update job'}), 400
    
    return jsonify(jobs[job_id])

if __name__ == '__main__':
    # Load existing jobs data
    load_jobs_from_file()
    
    # Create necessary directories
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    os.makedirs('screenshots', exist_ok=True)
    
    # Determine if running in Docker
    in_docker = os.environ.get('DOCKER_CONTAINER', False)
    
    # Run the Flask app
    app.run(
        debug=os.environ.get('FLASK_ENV') == 'development',
        host='0.0.0.0',  # Bind to all interfaces for Docker
        port=int(os.environ.get('PORT', 9001))  # Default to port 9001
    )