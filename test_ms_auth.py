#!/usr/bin/env python3
import requests
import json
import sys

# Configuration values
config = {
    "MS_CLIENT_ID": "NO",
    "MS_CLIENT_SECRET": "NO",
    "MS_TENANT_ID": "NO",
    "MS_USER_EMAIL": "test356@dataserve.com.sa",
    "AUTO_INITIALIZE": True
}

# Email configuration - change these values as needed
email_config = {
    "recipient": "mohamed.issa@dataserve.com.sa",  # Change to a real recipient email address
    "subject": "Test Email from Python Script",
    "body": "This is a test email sent using the Microsoft Graph API."
}

def print_config():
    """Print configuration with masked sensitive data"""
    print("=== Microsoft Email Test ===")
    print("Testing with the following configuration:")
    for key, value in config.items():
        if key == "MS_CLIENT_SECRET":
            # Mask the client secret
            masked_value = f"{value[:5]}...{value[-5:]}"
            print(f"{key}: {masked_value}")
        else:
            print(f"{key}: {value}")
    
    print("\nEmail will be sent:")
    print(f"From: {config['MS_USER_EMAIL']}")
    print(f"To: {email_config['recipient']}")
    print(f"Subject: {email_config['subject']}")

def get_access_token():
    """Get access token using client credentials flow"""
    print("\n[1/3] Getting access token...")
    
    # Prepare the token request data
    token_request_data = {
        'client_id': config["MS_CLIENT_ID"],
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': config["MS_CLIENT_SECRET"],
        'grant_type': 'client_credentials'
    }
    
    # Token endpoint for the specified tenant
    token_endpoint = f"https://login.microsoftonline.com/{config['MS_TENANT_ID']}/oauth2/v2.0/token"
    
    try:
        # Send the request
        response = requests.post(token_endpoint, data=token_request_data)
        
        if response.status_code == 200:
            response_data = response.json()
            access_token = response_data.get('access_token')
            print("✅ Successfully obtained access token")
            return access_token
        else:
            print(f"❌ Failed to get access token. Status code: {response.status_code}")
            print("Error details:")
            print(json.dumps(response.json(), indent=2))
            return None
            
    except Exception as e:
        print(f"❌ Error getting access token: {str(e)}")
        return None

def send_email(access_token):
    """Send an email using the Microsoft Graph API"""
    if not access_token:
        print("❌ Cannot send email without access token")
        return False
    
    print("\n[2/3] Preparing to send email...")
    
    # Graph API endpoint for sending mail
    endpoint = f"https://graph.microsoft.com/v1.0/users/{config['MS_USER_EMAIL']}/sendMail"
    
    # Headers for the request
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Email message payload
    email_payload = {
        "message": {
            "subject": email_config['subject'],
            "body": {
                "contentType": "Text",
                "content": email_config['body']
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": email_config['recipient']
                    }
                }
            ]
        },
        "saveToSentItems": "true"
    }
    
    try:
        print(f"[3/3] Sending email via Graph API: {endpoint}")
        response = requests.post(endpoint, headers=headers, data=json.dumps(email_payload))
        
        # Check response status
        if response.status_code == 202 or response.status_code == 200:
            print("✅ Email sent successfully!")
            return True
        else:
            print(f"❌ Failed to send email. Status code: {response.status_code}")
            try:
                error_details = response.json()
                print("Error details:")
                print(json.dumps(error_details, indent=2))
                
                # Provide specific guidance for common errors
                if response.status_code == 403:
                    print("\nPermission issue detected. Make sure your application has the Mail.Send permission.")
                    print("You may need to:")
                    print("1. Go to Azure Portal > App Registrations > Select your app")
                    print("2. Go to API Permissions > Add permission > Microsoft Graph > Application permissions")
                    print("3. Add 'Mail.Send' permission")
                    print("4. Click 'Grant admin consent'")
                
                if "delegated" in str(error_details) or "delegate" in str(error_details):
                    print("\nIt appears you're trying to use application permissions for delegated operations.")
                    print("For sending mail as a specific user with application permissions,")
                    print("you need to ensure your app has Mail.Send application permission,")
                    print("not just delegated permissions.")
            except:
                print("Response:")
                print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False

def main():
    """Main function to run the email test"""
    print_config()
    
    # Step 1: Get access token
    access_token = get_access_token()
    if not access_token:
        print("\n=== Test failed at authentication stage ===")
        return 1
    
    # Step 2: Send email
    success = send_email(access_token)
    
    if success:
        print("\n=== Email test completed successfully ===")
        return 0
    else:
        print("\n=== Email test failed ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())