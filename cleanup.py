#!/usr/bin/env python3
"""
Cleanup Script for PAN-GSTIN Mapper Application

This script removes unnecessary files from the project directory,
keeping only the essential files needed for the application to function.
"""

import os
import shutil
import glob

def cleanup_files():
    """Remove unnecessary files from the project directory"""
    print("Starting cleanup process...")
    
    # Files to keep (essential files)
    essential_files = [
        'app.py',
        'pan_gstin_mapper_enhanced.py',
        'requirements.txt',
        'README.md',
        'README_FLASK.md',
        'GSTIN_DETAILS_GUIDE.md',
        'cleanup.py'  # Keep this script
    ]
    
    # Directories to keep
    essential_dirs = [
        'static',
        'templates',
        'uploads',
        'results'
    ]
    
    # Get all files in the current directory
    all_files = [f for f in os.listdir('.') if os.path.isfile(f)]
    
    # Remove non-essential files
    for file in all_files:
        if file not in essential_files and not any(file.startswith(prefix) for prefix in ['.git', '.vscode']):
            try:
                os.remove(file)
                print(f"Removed file: {file}")
            except Exception as e:
                print(f"Error removing {file}: {e}")
    
    # Clean up log files
    for log_file in glob.glob('*.log'):
        try:
            os.remove(log_file)
            print(f"Removed log file: {log_file}")
        except Exception as e:
            print(f"Error removing {log_file}: {e}")
    
    # Clean up screenshots directory
    if os.path.exists('screenshots') and os.path.isdir('screenshots'):
        try:
            shutil.rmtree('screenshots')
            print("Removed screenshots directory")
            # Recreate empty directory
            os.makedirs('screenshots', exist_ok=True)
            print("Created empty screenshots directory")
        except Exception as e:
            print(f"Error cleaning screenshots directory: {e}")
    
    # Clean up backup Excel files in uploads directory
    if os.path.exists('uploads') and os.path.isdir('uploads'):
        for backup_file in glob.glob('uploads/*_backup*.xlsx'):
            try:
                os.remove(backup_file)
                print(f"Removed backup file: {backup_file}")
            except Exception as e:
                print(f"Error removing {backup_file}: {e}")
    
    print("Cleanup process completed!")

if __name__ == "__main__":
    # Ask for confirmation before proceeding
    confirm = input("This will remove unnecessary files from the project directory. Continue? (y/n): ")
    if confirm.lower() == 'y':
        cleanup_files()
    else:
        print("Cleanup cancelled.")