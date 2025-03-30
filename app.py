import os
import logging
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import pandas as pd
import io
from werkzeug.utils import secure_filename
from data_processor import DataProcessor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure upload settings
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'doc', 'docx', 'txt'}
UPLOAD_FOLDER = '/tmp/data_cleaner_uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generate a unique filename to prevent collisions
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Store file info in session
        session['uploaded_file'] = {
            'path': file_path,
            'original_name': original_filename,
            'extension': file_extension
        }
        
        try:
            # Initialize the data processor and process the file
            processor = DataProcessor()
            processor.load_file(file_path, file_extension)
            
            # Get file statistics before cleaning
            stats_before = processor.get_stats()
            
            # Clean the data
            processor.clean_data()
            
            # Get file statistics after cleaning
            stats_after = processor.get_stats()
            
            # Save processed data temporarily
            processed_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"processed_{unique_filename}")
            processor.save_file(processed_file_path)
            
            # Store processed file info in session
            session['processed_file'] = {
                'path': processed_file_path,
                'original_name': f"cleaned_{original_filename}",
                'stats_before': stats_before,
                'stats_after': stats_after,
                'corrections': processor.get_corrections(),
                'removed_rows': processor.get_removed_rows()
            }
            
            return redirect(url_for('results'))
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            flash(f'Error processing file: {str(e)}', 'danger')
            return redirect(url_for('index'))
    else:
        flash(f'File type not allowed. Please upload one of the following: {", ".join(ALLOWED_EXTENSIONS)}', 'danger')
        return redirect(request.url)

@app.route('/results')
def results():
    if 'processed_file' not in session:
        flash('No processed file found. Please upload a file first.', 'warning')
        return redirect(url_for('index'))
    
    return render_template(
        'results.html',
        filename=session['processed_file']['original_name'],
        stats_before=session['processed_file']['stats_before'],
        stats_after=session['processed_file']['stats_after'],
        corrections=session['processed_file']['corrections'],
        removed_rows=session['processed_file']['removed_rows']
    )

@app.route('/download')
def download():
    if 'processed_file' not in session:
        flash('No processed file found. Please upload a file first.', 'warning')
        return redirect(url_for('index'))
    
    file_path = session['processed_file']['path']
    return send_file(
        file_path,
        as_attachment=True,
        download_name=session['processed_file']['original_name']
    )

@app.route('/reset')
def reset():
    # Clean up session and temporary files
    if 'uploaded_file' in session and os.path.exists(session['uploaded_file']['path']):
        try:
            os.remove(session['uploaded_file']['path'])
        except Exception as e:
            logger.error(f"Error removing uploaded file: {str(e)}")
    
    if 'processed_file' in session and os.path.exists(session['processed_file']['path']):
        try:
            os.remove(session['processed_file']['path'])
        except Exception as e:
            logger.error(f"Error removing processed file: {str(e)}")
    
    # Clear session
    session.pop('uploaded_file', None)
    session.pop('processed_file', None)
    
    flash('Reset complete. You can upload a new file.', 'success')
    return redirect(url_for('index'))

# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large. Maximum allowed size is 16MB.', 'danger')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_server_error(error):
    flash('Server error occurred. Please try again later.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
