import base64

def extract_body_from_gmail_payload(payload):
    """Recursively search through the Gmail payload to find the plain text body."""
    body = ""
    
    # Sometimes the body is directly in 'body'
    if 'body' in payload and 'data' in payload['body']:
        # Base64 decode the text
        data = payload['body']['data']
        # URL-safe base64 decode
        body = base64.urlsafe_b64decode(data).decode('utf-8')
    
    # If the email is multipart (has attachments or HTML + Plaintext), the body is nested in 'parts'
    elif 'parts' in payload:
        for part in payload['parts']:
            # We specifically look for 'text/plain' to avoid messy HTML
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break # We found the text, exit loop
    
    return body