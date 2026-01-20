import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, render_template, request, send_file
import pandas as pd
from topsis_vikas.topsis import topsis  # Import from our package
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app = Flask(__name__)
# Use /tmp for serverless environments (Vercel)
# Local fallback: use local directory if /tmp not relevant on Windows (though Mac/Linux have it)
# For Vercel, we MUST use /tmp
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['RESULT_FOLDER'] = '/tmp/results'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# Email Configuration - User must update these or set env vars
EMAIL_ADDRESS = os.environ.get('EMAIL_USER', 'your_email@gmail.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASS', 'your_app_password')

def send_email(to_email, subject, body, file_path):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    attachment = open(file_path, "rb")
    p = MIMEBase('application', 'octet-stream')
    p.set_payload((attachment).read())
    encoders.encode_base64(p)
    p.add_header('Content-Disposition', "attachment; filename= %s" % os.path.basename(file_path))
    msg.attach(p)

    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    text = msg.as_string()
    s.sendmail(EMAIL_ADDRESS, to_email, text)
    s.quit()

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return {"error": "No file uploaded"}, 400
    file = request.files['file']
    if file.filename == '':
        return {"error": "No file selected"}, 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
             # Logic similar to topsis check
            if filepath.endswith(".csv"):
                data = pd.read_csv(filepath)
            elif filepath.endswith(".xlsx"):
                data = pd.read_excel(filepath)
            else:
                return {"error": "Invalid file format"}, 400
            
            if data.shape[1] < 3:
                return {"error": "File must have at least 3 columns"}, 400
                
            # Columns from 2nd to last
            num_criteria = data.shape[1] - 1
            return {"num_criteria": num_criteria, "message": f"File has {num_criteria} criteria columns. Please enter {num_criteria} weights and impacts."}
            
        except Exception as e:
            return {"error": str(e)}, 500

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        
        weights = request.form['weights']
        impacts = request.form['impacts']
        email = request.form['email']
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # Save again (overwrite is fine) for processing
            file.save(filepath)
            
            result_filename = f"result_{filename}"
            result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)
            
            try:
                # Call Topsis
                topsis(filepath, weights, impacts, result_path)
                
                # Send Email
                try:
                    send_email(email, "Topsis Result", "Here is your Topsis result.", result_path)
                    email_status = "Email sent successfully!"
                except Exception as e:
                    email_status = f"Failed to send email: {e}. Check server logs/credentials."
                
                return f"Processing Complete. <a href='/download/{result_filename}'>Download Result</a><br>{email_status}"
            except Exception as e:
                return f"Error occurred: {str(e)}"

    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['RESULT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
