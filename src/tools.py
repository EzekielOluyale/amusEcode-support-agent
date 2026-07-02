import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
    
    creds = Credentials(
        token=None,  
        refresh_token=os.getenv("GMAIL_REFRESH_TOKEN"),
        client_id=os.getenv("GMAIL_CLIENT_ID"),
        client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
        token_uri=os.getenv("GMAIL_TOKEN_URI"),
        scopes=SCOPES
    )
    
    if not creds.token or creds.expired:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)