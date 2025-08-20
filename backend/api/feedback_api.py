from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, ValidationError
from typing import Optional
import requests
import json
import os
from datetime import datetime
import logging

router = APIRouter()
log_handle = logging.getLogger(__name__)

class FeedbackRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phoneNumber: Optional[str] = None
    subject: str
    feedback: str
    captchaToken: str

def verify_recaptcha(token: str, remote_ip: str = None) -> bool:
    """Verify reCAPTCHA token with Google's verification API"""
    secret_key = os.getenv('RECAPTCHA_SECRET_KEY')
    if not secret_key:
        log_handle.warning("RECAPTCHA_SECRET_KEY not configured")
        return True  # Allow in development if not configured
    
    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': secret_key,
                'response': token,
                'remoteip': remote_ip
            },
            timeout=10
        )
        result = response.json()
        return result.get('success', False)
    except Exception as e:
        log_handle.error(f"reCAPTCHA verification error: {str(e)}")
        return False

def send_feedback_email(feedback_data: dict) -> bool:
    """Send feedback email using Brevo API"""
    brevo_api_key = os.getenv('BREVO_API_KEY')
    log_handle.info(f"Brevo API key: {brevo_api_key}")
    if not brevo_api_key:
        log_handle.error("BREVO_API_KEY not configured")
        return False
    
    # Brevo API endpoint
    url = "https://api.sendinblue.com/v3/smtp/email"
    
    # Email template
    email_content = f"""
    New Feedback Submission - Aagam Khoj
    
    From: {feedback_data['name']}
    Email: {feedback_data.get('email', 'Not provided')}
    Phone: {feedback_data.get('phoneNumber', 'Not provided')}
    Subject: {feedback_data['subject']}
    
    Message:
    {feedback_data['feedback']}
    
    Submitted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    payload = {
        "sender": {
            "name": "Aagam Khoj Feedback",
            "email": os.getenv('FEEDBACK_FROM_EMAIL', 'noreply@aagamkhoj.com')
        },
        "to": [
            {
                "email": os.getenv('FEEDBACK_TO_EMAIL', 'feedback@aagamkhoj.com'),
                "name": "Aagam Khoj Team"
            }
        ],
        "subject": f"Feedback: {feedback_data['subject']}",
        "textContent": email_content,
        "htmlContent": email_content.replace('\n', '<br>')
    }
    
    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 201:
            log_handle.info("Feedback email sent successfully")
            return True
        else:
            log_handle.error(f"Brevo API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_handle.error(f"Error sending feedback email: {str(e)}")
        return False

@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, request: Request):
    """Handle feedback form submission"""
    try:
        # Get client IP for reCAPTCHA verification
        client_ip = request.client.host
        if hasattr(request, 'headers'):
            client_ip = request.headers.get('x-forwarded-for', client_ip)
            if ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
        
        # Verify reCAPTCHA
        if not verify_recaptcha(feedback.captchaToken, client_ip):
            raise HTTPException(status_code=400, detail="Invalid CAPTCHA")
        
        # Prepare feedback data
        feedback_data = {
            'name': feedback.name.strip(),
            'email': feedback.email.strip() if feedback.email else None,
            'phoneNumber': feedback.phoneNumber.strip() if feedback.phoneNumber else None,
            'subject': feedback.subject.strip(),
            'feedback': feedback.feedback.strip()
        }
        
        # Validate required fields
        if not feedback_data['name'] or not feedback_data['subject'] or not feedback_data['feedback']:
            raise HTTPException(status_code=400, detail="Required fields are missing")
        
        # Send email
        if send_feedback_email(feedback_data):
            log_handle.info(f"Feedback submitted by {feedback_data['name']} - {feedback_data['subject']}")
            return {"message": "Feedback submitted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send feedback email")
            
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        log_handle.error(f"Error processing feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")