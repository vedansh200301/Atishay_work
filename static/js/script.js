/**
 * PAN-GSTIN Mapper Web Interface
 * Custom JavaScript functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Format all date fields with the 'format-date' class
    formatDates();
    
    // Initialize tooltips
    initializeTooltips();
    
    // Add file input validation
    setupFileValidation();
    
    // Add form validation
    setupFormValidation();
    
    // Setup GSTIN detail links
    setupGstinLinks();
    
    // Setup batch update functionality
    setupBatchUpdate();
});

/**
 * Format dates to be more readable
 */
function formatDates() {
    document.querySelectorAll('[data-date]').forEach(el => {
        const dateStr = el.getAttribute('data-date');
        if (dateStr) {
            try {
                const date = new Date(dateStr);
                el.textContent = date.toLocaleString();
            } catch (e) {
                console.error('Error formatting date:', e);
            }
        }
    });
}

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Setup file input validation
 */
function setupFileValidation() {
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Check file extension
                const fileName = file.name;
                const fileExt = fileName.split('.').pop().toLowerCase();
                const allowedExts = ['xlsx', 'xls', 'csv'];
                
                if (!allowedExts.includes(fileExt)) {
                    alert('Invalid file type. Please upload an Excel (.xlsx, .xls) or CSV file.');
                    fileInput.value = '';
                    return;
                }
                
                // Check file size (max 16MB)
                const maxSize = 16 * 1024 * 1024; // 16MB in bytes
                if (file.size > maxSize) {
                    alert('File is too large. Maximum file size is 16MB.');
                    fileInput.value = '';
                    return;
                }
            }
        });
    }
}

/**
 * Setup form validation
 */
function setupFormValidation() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const fileInput = document.getElementById('file');
            if (fileInput && fileInput.files.length === 0) {
                e.preventDefault();
                alert('Please select a file to upload.');
                return;
            }
            
            // Add a loading state to the submit button
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
        });
    }
}

/**
 * Update job status and progress
 * @param {string} jobId - The ID of the job to update
 */
function updateJobStatus(jobId) {
    fetch(`/job_status/${jobId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Update status elements based on the response
            updateStatusElements(data);
            
            // Continue polling if job is still in progress
            if (data.status === 'processing' || data.status === 'queued') {
                setTimeout(() => updateJobStatus(jobId), 5000);
            }
        })
        .catch(error => {
            console.error('Error fetching job status:', error);
            // Retry after a delay
            setTimeout(() => updateJobStatus(jobId), 10000);
        });
}

/**
 * Update status elements based on job data
 * @param {Object} data - The job data
 */
function updateStatusElements(data) {
    // Update status badge
    const statusBadge = document.getElementById('job-status');
    if (statusBadge) {
        statusBadge.textContent = capitalizeFirstLetter(data.status);
        
        // Update badge class
        statusBadge.className = 'badge';
        if (data.status === 'completed') {
            statusBadge.classList.add('bg-success');
        } else if (data.status === 'failed') {
            statusBadge.classList.add('bg-danger');
        } else if (data.status === 'processing') {
            statusBadge.classList.add('bg-primary');
        } else {
            statusBadge.classList.add('bg-secondary');
        }
    }
    
    // Update sections visibility
    updateSectionVisibility(data.status);
    
    // Update progress if available
    if (data.progress) {
        updateProgressIndicators(data.progress);
    }
    
    // Update timestamps
    updateTimestamps(data);
}

/**
 * Update section visibility based on job status
 * @param {string} status - The job status
 */
function updateSectionVisibility(status) {
    const progressSection = document.getElementById('progress-section');
    const resultSection = document.getElementById('result-section');
    const errorSection = document.getElementById('error-section');
    const queuedSection = document.getElementById('queued-section');
    
    if (progressSection) progressSection.classList.toggle('d-none', status !== 'processing');
    if (resultSection) resultSection.classList.toggle('d-none', status !== 'completed');
    if (errorSection) errorSection.classList.toggle('d-none', status !== 'failed');
    if (queuedSection) queuedSection.classList.toggle('d-none', status !== 'queued');
}

/**
 * Update progress indicators
 * @param {Object} progress - The progress data
 */
function updateProgressIndicators(progress) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    
    if (progressBar && progressText) {
        if (progress.processed_count) {
            progressText.textContent = `Processed ${progress.processed_count} PAN numbers`;
            
            // If we have total count, show percentage
            if (progress.total_count) {
                const percent = Math.round((progress.processed_count / progress.total_count) * 100);
                progressBar.style.width = `${percent}%`;
                progressBar.setAttribute('aria-valuenow', percent);
                progressBar.textContent = `${percent}%`;
            } else {
                // Otherwise show indeterminate progress
                progressBar.style.width = '100%';
                progressBar.textContent = 'Processing...';
            }
        }
    }
}

/**
 * Update timestamps
 * @param {Object} data - The job data
 */
function updateTimestamps(data) {
    // Update start time
    if (data.start_time) {
        const startTimeEl = document.getElementById('start-time');
        if (startTimeEl) {
            startTimeEl.textContent = formatDate(data.start_time);
        }
    }
    
    // Update end time
    if (data.end_time) {
        const endTimeEl = document.getElementById('end-time');
        if (endTimeEl) {
            endTimeEl.textContent = formatDate(data.end_time);
        }
    }
}

/**
 * Format a date string
 * @param {string} dateStr - The date string to format
 * @returns {string} The formatted date string
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        return date.toLocaleString();
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateStr;
    }
}

/**
 * Capitalize the first letter of a string
 * @param {string} string - The string to capitalize
 * @returns {string} The capitalized string
 */
function capitalizeFirstLetter(string) {
    if (!string) return '';
    return string.charAt(0).toUpperCase() + string.slice(1);
}

/**
 * Setup GSTIN detail links to show modal with details
 */
function setupGstinLinks() {
    // Get all GSTIN links
    const gstinLinks = document.querySelectorAll('.gstin-link');
    
    // Initialize the modal
    const gstinModal = new bootstrap.Modal(document.getElementById('gstinDetailsModal'), {
        backdrop: 'static'
    });
    
    // Add click event to each GSTIN link
    gstinLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const gstin = this.getAttribute('data-gstin');
            showGstinDetails(gstin, gstinModal);
        });
    });
}

/**
 * Show GSTIN details in modal
 * @param {string} gstin - The GSTIN to fetch details for
 * @param {bootstrap.Modal} modal - The Bootstrap modal instance
 */
function showGstinDetails(gstin, modal) {
    // Reset modal state
    resetGstinModal();
    
    // Show the modal
    modal.show();
    
    // Show loading state
    document.getElementById('gstin-loading').classList.remove('d-none');
    
    // Fetch GSTIN details
    fetchGstinDetails(gstin)
        .then(data => {
            // Hide loading state
            document.getElementById('gstin-loading').classList.add('d-none');
            
            // Show details
            displayGstinDetails(gstin, data);
        })
        .catch(error => {
            // Hide loading state
            document.getElementById('gstin-loading').classList.add('d-none');
            
            // Show error
            const errorElement = document.getElementById('gstin-error');
            const errorMessageElement = document.getElementById('gstin-error-message');
            
            errorElement.classList.remove('d-none');
            errorMessageElement.textContent = `Failed to fetch details for GSTIN ${gstin}: ${error.message}`;
            
            console.error('Error fetching GSTIN details:', error);
        });
}

/**
 * Reset the GSTIN modal to its initial state
 */
function resetGstinModal() {
    // Hide all sections
    document.getElementById('gstin-loading').classList.add('d-none');
    document.getElementById('gstin-error').classList.add('d-none');
    document.getElementById('gstin-details').classList.add('d-none');
    
    // Clear previous data
    document.getElementById('modal-gstin').textContent = '';
    document.getElementById('modal-trade-name').textContent = '';
    document.getElementById('modal-reg-date').textContent = '';
    document.getElementById('modal-hsn-codes').innerHTML = '';
}

/**
 * Fetch GSTIN details from the server
 * @param {string} gstin - The GSTIN to fetch details for
 * @returns {Promise<Object>} - Promise resolving to GSTIN details
 */
function fetchGstinDetails(gstin) {
    return fetch(`/gstin_details/${gstin}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        });
}

/**
 * Display GSTIN details in the modal
 * @param {string} gstin - The GSTIN
 * @param {Object} data - The GSTIN details data
 */
function displayGstinDetails(gstin, data) {
    // Show details section
    const detailsSection = document.getElementById('gstin-details');
    detailsSection.classList.remove('d-none');
    
    // Populate basic details
    document.getElementById('modal-gstin').textContent = gstin;
    document.getElementById('modal-trade-name').textContent = data.trade_name || 'Not available';
    document.getElementById('modal-reg-date').textContent = data.registration_date ? formatDate(data.registration_date) : 'Not available';
    
    // Populate HSN codes
    const hsnTableBody = document.getElementById('modal-hsn-codes');
    hsnTableBody.innerHTML = '';
    
    if (data.hsn_codes && data.hsn_codes.length > 0) {
        data.hsn_codes.forEach(hsn => {
            const row = document.createElement('tr');
            
            const codeCell = document.createElement('td');
            codeCell.textContent = hsn.code;
            row.appendChild(codeCell);
            
            const descCell = document.createElement('td');
            descCell.textContent = hsn.description || 'No description available';
            row.appendChild(descCell);
            
            hsnTableBody.appendChild(row);
        });
    } else {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 2;
        cell.textContent = 'No HSN codes available';
        cell.className = 'text-center';
        row.appendChild(cell);
        hsnTableBody.appendChild(row);
    }
    
    /**
     * Setup batch update functionality
     */
    function setupBatchUpdate() {
        // Get the update button and modal elements
        const updateBtn = document.getElementById('update-gstin-details-btn');
        const batchUpdateModal = new bootstrap.Modal(document.getElementById('batchUpdateModal'), {
            backdrop: 'static'
        });
        
        // Add click event to the update button
        if (updateBtn) {
            updateBtn.addEventListener('click', function() {
                // Show the modal
                batchUpdateModal.show();
                
                // Reset modal state
                resetBatchUpdateModal();
            });
        }
        
        // Add click event to the start batch update button
        const startBatchUpdateBtn = document.getElementById('start-batch-update-btn');
        if (startBatchUpdateBtn) {
            startBatchUpdateBtn.addEventListener('click', function() {
                startBatchUpdate();
            });
        }
    }
    
    /**
     * Reset the batch update modal to its initial state
     */
    function resetBatchUpdateModal() {
        // Show initial section, hide others
        document.getElementById('batch-update-initial').classList.remove('d-none');
        document.getElementById('batch-update-loading').classList.add('d-none');
        document.getElementById('batch-update-progress').classList.add('d-none');
        document.getElementById('batch-update-complete').classList.add('d-none');
        document.getElementById('batch-update-error').classList.add('d-none');
        
        // Reset progress bar
        const progressBar = document.getElementById('batch-progress-bar');
        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
            progressBar.textContent = '0%';
        }
        
        // Reset counters
        document.getElementById('batch-total-count').textContent = '0';
        document.getElementById('batch-success-count').textContent = '0';
        document.getElementById('batch-failed-count').textContent = '0';
        document.getElementById('batch-complete-total').textContent = '0';
        document.getElementById('batch-complete-success').textContent = '0';
        document.getElementById('batch-complete-failed').textContent = '0';
    }
    
    /**
     * Start the batch update process
     */
    function startBatchUpdate() {
        // Show loading section
        document.getElementById('batch-update-initial').classList.add('d-none');
        document.getElementById('batch-update-loading').classList.remove('d-none');
        
        // Collect all GSTINs from the table
        const gstinLinks = document.querySelectorAll('.gstin-link');
        const gstins = Array.from(gstinLinks).map(link => link.getAttribute('data-gstin'));
        
        if (gstins.length === 0) {
            showBatchUpdateError('No GSTINs found in the current job.');
            return;
        }
        
        // Send request to start batch update
        fetch('/update_gstin_details', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ gstins: gstins }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showBatchUpdateError(data.error);
                return;
            }
            
            // Show progress section
            document.getElementById('batch-update-loading').classList.add('d-none');
            document.getElementById('batch-update-progress').classList.remove('d-none');
            
            // Update total count
            document.getElementById('batch-total-count').textContent = data.valid_gstins.length;
            
            // Start polling for job status
            pollBatchUpdateStatus(data.job_id);
        })
        .catch(error => {
            console.error('Error starting batch update:', error);
            showBatchUpdateError(error.message);
        });
    }
    
    /**
     * Poll for batch update job status
     * @param {string} jobId - The ID of the batch update job
     */
    function pollBatchUpdateStatus(jobId) {
        fetch(`/batch_update_status/${jobId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showBatchUpdateError(data.error);
                    return;
                }
                
                // Update progress
                updateBatchProgress(data);
                
                // Continue polling if job is still in progress
                if (data.status === 'processing') {
                    setTimeout(() => pollBatchUpdateStatus(jobId), 5000);
                } else if (data.status === 'completed') {
                    showBatchUpdateComplete(data);
                } else if (data.status === 'failed') {
                    showBatchUpdateError(data.error || 'Batch update failed');
                }
            })
            .catch(error => {
                console.error('Error polling batch update status:', error);
                // Don't show error yet, retry a few times
                setTimeout(() => pollBatchUpdateStatus(jobId), 10000);
            });
    }
    
    /**
     * Update batch progress indicators
     * @param {Object} data - The job data
     */
    function updateBatchProgress(data) {
        if (!data.progress) return;
        
        const { total, processed, successful, failed } = data.progress;
        
        // Update counters
        document.getElementById('batch-total-count').textContent = total;
        document.getElementById('batch-success-count').textContent = successful;
        document.getElementById('batch-failed-count').textContent = failed;
        
        // Update progress bar
        if (total > 0) {
            const percent = Math.round((processed / total) * 100);
            const progressBar = document.getElementById('batch-progress-bar');
            progressBar.style.width = `${percent}%`;
            progressBar.setAttribute('aria-valuenow', percent);
            progressBar.textContent = `${percent}%`;
        }
        
        // Update status message
        if (processed < total) {
            document.getElementById('batch-status-message').textContent =
                `Processing GSTIN ${processed} of ${total}...`;
        } else {
            document.getElementById('batch-status-message').textContent =
                `Completed processing ${total} GSTINs.`;
        }
    }
    
    /**
     * Show batch update complete section
     * @param {Object} data - The job data
     */
    function showBatchUpdateComplete(data) {
        // Hide progress section
        document.getElementById('batch-update-progress').classList.add('d-none');
        
        // Show complete section
        document.getElementById('batch-update-complete').classList.remove('d-none');
        
        // Update final counters
        if (data.progress) {
            document.getElementById('batch-complete-total').textContent = data.progress.total;
            document.getElementById('batch-complete-success').textContent = data.progress.successful;
            document.getElementById('batch-complete-failed').textContent = data.progress.failed;
        }
    }
    
    /**
     * Show batch update error section
     * @param {string} errorMessage - The error message to display
     */
    function showBatchUpdateError(errorMessage) {
        // Hide all other sections
        document.getElementById('batch-update-initial').classList.add('d-none');
        document.getElementById('batch-update-loading').classList.add('d-none');
        document.getElementById('batch-update-progress').classList.add('d-none');
        document.getElementById('batch-update-complete').classList.add('d-none');
        
        // Show error section
        document.getElementById('batch-update-error').classList.remove('d-none');
        
        // Set error message
        document.getElementById('batch-error-message').textContent = errorMessage;
    }
}