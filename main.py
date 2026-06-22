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

# Global flag for shutdown
is_shutting_down = False

def signal_handler(sig, frame):
    """Catches Ctrl+C or server termination signals to shut down safely."""
    global is_shutting_down
    logger.warning("\nShutdown signal received! Finishing current tasks before exiting...")
    is_shutting_down = True

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
        # Check if we should stop before processing the next email
        if is_shutting_down:
            logger.warning("Aborting loop due to shutdown. Unprocessed emails will remain UNREAD.")
            break 

        email_id = msg['id']
        thread_id = msg.get('threadId')
        logger.info(f"--- Processing Email ID: {email_id} ---")
        
        try:
            initial_state = {
                "email_id": email_id,
                "thread_id": thread_id
            }
            
            config = {"configurable": {"thread_id": f"thread_{email_id}"}}
            
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
    # Register the graceful shutdown signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load interval from .env, default to 300 if not found
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 300))
    
    logger.info("Email Agent Service Engine launched successfully. Press Ctrl+C to stop.")
    
    # The Infinite Polling Loop
    while not is_shutting_down:
        run_amusEcode_email_watcher()
        
        # Sleep in small chunks so we can interrupt the sleep if shutting down
        logger.info(f"Sleeping for {POLL_INTERVAL_SECONDS} seconds before next run...")
        for _ in range(POLL_INTERVAL_SECONDS):
            if is_shutting_down:
                break
            time.sleep(1)
            
    logger.info("Service Engine completely shut down.")