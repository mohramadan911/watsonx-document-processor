import msal
import requests
import base64
import logging
import os
import tempfile
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MSGraphClient:
    """Microsoft Graph API Client for sending emails"""
    
    def __init__(self, client_id, client_secret, tenant_id, user_email):
        """Initialize the Microsoft Graph API client"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.user_email = user_email
        self.access_token = None
        self.scopes = ['https://graph.microsoft.com/.default']
    
    def get_token(self):
        """Get Microsoft Graph API access token"""
        try:
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                client_credential=self.client_secret
            )
            result = app.acquire_token_for_client(scopes=self.scopes)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("Successfully obtained Microsoft Graph API token")
                return True
            else:
                logger.error(f"Failed to obtain token: {result.get('error')}: {result.get('error_description')}")
                return False
        except Exception as e:
            logger.error(f"Error getting Microsoft Graph token: {str(e)}")
            return False
    
    def send_email(self, to_email, subject, body, attachments=None, cc_email=None, bcc_email=None):
        """Send email using Microsoft Graph API"""
        if not self.access_token and not self.get_token():
            return False
        
        try:
            to_recipients = [{"emailAddress": {"address": to_email}}]
            cc_recipients = [{"emailAddress": {"address": cc_email}}] if cc_email else []
            bcc_recipients = [{"emailAddress": {"address": bcc_email}}] if bcc_email else []
            
            email_message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body
                    },
                    "toRecipients": to_recipients,
                    "ccRecipients": cc_recipients,
                    "bccRecipients": bcc_recipients
                },
                "saveToSentItems": "true"
            }
            
            if attachments:
                email_message["message"]["attachments"] = self._prepare_attachments(attachments)
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"https://graph.microsoft.com/v1.0/users/{self.user_email}/sendMail",
                headers=headers,
                json=email_message
            )
            
            if response.status_code == 202:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def _prepare_attachments(self, attachments):
        """Prepare email attachments"""
        attachment_list = []
        for attachment_path in attachments:
            if not os.path.exists(attachment_path):
                logger.warning(f"Attachment file not found: {attachment_path}")
                continue
            
            with open(attachment_path, "rb") as attachment_file:
                encoded_content = base64.b64encode(attachment_file.read()).decode("utf-8")
            
            attachment_list.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": os.path.basename(attachment_path),
                "contentType": "application/octet-stream",
                "contentBytes": encoded_content
            })
        return attachment_list
    
    def create_email_with_summary(self, to_email, document_name, summary, pdf_path=None, recommendations=None, classification=None):
        """Create and send an email with document summary and any available insights
        
        Args:
            to_email (str): Recipient email address
            document_name (str): Name of the document
            summary (str): Summary of the document
            pdf_path (str, optional): Path to the PDF file to attach
            recommendations (str, optional): Recommendations based on the document
            classification (dict, optional): Classification information for the document
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = f"Document Analysis: {document_name}"
        summary_html = summary.replace("\n", "<br>") if summary else ""
        
        # Start building the email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333333;">
            <h2>Document Analysis: {document_name}</h2>
            <p style="color: #666666;">Processed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
        """
        
        # Add summary section if available
        if summary:
            body += f"""
            <h3>Executive Summary</h3>
            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                {summary_html}
            </div>
            """
        
        # Add recommendations section if available
        if recommendations:
            recommendations_html = recommendations.replace("\n", "<br>")
            body += f"""
            <h3>Recommendations</h3>
            <div style="background-color: #f0f7ff; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                {recommendations_html}
            </div>
            """
        
        # Add classification section if available
        if classification and classification.get("success", False):
            category = classification.get("category", "Unknown")
            confidence = classification.get("confidence", 0)
            reasoning = classification.get("reasoning", "")
            folder = classification.get("folder", "")
            
            reasoning_html = reasoning.replace("\n", "<br>")
            
            body += f"""
            <h3>Document Classification</h3>
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                <p><strong>Category:</strong> {category}</p>
                <p><strong>Confidence:</strong> {confidence:.2f}</p>
                <p><strong>Folder:</strong> {folder}</p>
                <p><strong>Reasoning:</strong><br> {reasoning_html}</p>
            </div>
            """
        
        # Add additional actions section based on what's missing
        missing_actions = []
        if not summary:
            missing_actions.append("summarize")
        if not recommendations:
            missing_actions.append("get recommendations for")
        if not classification:
            missing_actions.append("classify")
        
        if missing_actions:
            actions_text = ", ".join(missing_actions[:-1])
            if len(missing_actions) > 1:
                actions_text += f", or {missing_actions[-1]}"
            else:
                actions_text = missing_actions[0]
            
            body += f"""
            <div style="background-color: #fffdf0; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #ffd700;">
                <p><strong>Additional insights available:</strong> You can also {actions_text} this document using the WatsonX PDF Agent.</p>
            </div>
            """
        
        # Close the email
        body += f"""
            <hr>
            <p style="color: #666666; font-size: 0.9em;">This analysis was generated automatically by the WatsonX PDF Agent.</p>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, body, [pdf_path] if pdf_path else None)
