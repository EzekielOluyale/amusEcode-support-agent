import time
import signal
import sys
import os
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import sentry_sdk

# This ensures even if the app crashes during setup, Sentry reports it.
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    send_default_pii=True,
    enable_logs=True,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
)

# Project Internal Imports
from src.logger import setup_logger
from src.tools import get_gmail_service
from src.graph import app

# Load environment variables
load_dotenv()

logger = setup_logger(__name__)

def run_amusEcode_email_watcher():
    logger.info("Starting automated email watcher...")
    
    try:
        service = get_gmail_service()
        results = service.users().messages().list(userId="me", q="is:unread label:INBOX").execute()
        messages = results.get("messages", [])
    except HttpError as e:
        logger.error(f"Failed to connect to Gmail API during discovery: {e}")
        return 

    if not messages:
        logger.info("Inbox is clear. No new emails to process.")
        return

    logger.info(f"Found {len(messages)} new email(s). Initiating agent workflows...")

    for msg in messages:
        email_id = msg['id']
        thread_id = msg.get('threadId')
        logger.info(f"--- Processing Email ID: {email_id} ---")
        
        try:
            initial_state = {
                "email_id": email_id,
                "thread_id": thread_id
            }
            
            config = {"configurable": {"thread_id": f"thread_{thread_id}"}}
            
            # Run the AI workflow
            final_state = app.invoke(initial_state, config=config)
            
            # Log the classification results
            full_classification = final_state.get('classification', {})
            logger.info(f"Agent finished successfully. Classification: {full_classification}")
            
            # Mark the email as read ONLY if it succeeded
            service.users().messages().batchModify(
                userId="me", 
                body={'ids': [email_id], 'removeLabelIds': ['UNREAD']}
            ).execute()
            logger.info(f"Marked Email {email_id} as Read completely.")

        except Exception as e:
            # Isolate errors so one bad email doesn't crash the whole system
            logger.exception(f"CRITICAL ERROR processing Email ID {email_id}: {str(e)}")

if __name__ == "__main__":
    logger.info("Email Agent Cron Task started.")
    
    try:
        # Run the watcher exactly ONCE
        run_amusEcode_email_watcher()
        logger.info("Email Agent Cron Task completed successfully.")
        
    except Exception as e:
        # If the entire process fails critically, log it and raise it 
        # so the server scheduler (Render) registers it as a failed job run.
        logger.error(f"Cron Task failed with a critical error: {e}")
        raise e