import os
import certifi
import time
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ServerSelectionTimeoutError
from langgraph.checkpoint.mongodb import MongoDBSaver

# Project Internal Imports
from src.logger import setup_logger
from src.state import EmailAgentState
from src.nodes import read_email, check_crm, classify_intent, search_documentation, bug_tracking, draft_response, human_review, send_reply

logger = setup_logger(__name__)

# Create the graph
workflow = StateGraph(EmailAgentState)

# Add nodes with appropriate error handling
workflow.add_node("read_email", read_email)
workflow.add_node("classify_intent", classify_intent)

# Add retry policy for nodes that might have transient failures
workflow.add_node(
    "check_crm",
    check_crm,
    retry_policy=RetryPolicy(max_attempts=3)
)

workflow.add_node(
    "search_documentation",
    search_documentation,
    retry_policy=RetryPolicy(max_attempts=3)
)
workflow.add_node("bug_tracking", bug_tracking)
workflow.add_node("draft_response", draft_response)
workflow.add_node("human_review", human_review)
workflow.add_node("send_reply", send_reply)

# Add only the essential edges
workflow.add_edge(START, "read_email")
workflow.add_edge("read_email", "check_crm")
workflow.add_edge("check_crm", "classify_intent")
workflow.add_edge("send_reply", END)

mongo_uri = os.getenv("MONGO_URI")

if not mongo_uri:
    logger.critical("MONGO_URI environment variable is completely missing!")
    raise ValueError("CRITICAL: Application cannot start without a valid database connection string.")

# Retry logic for SSL handshake issues
max_retries = 3
retry_delay = 2
client = None

for attempt in range(max_retries):
    try:
        logger.info(f"Initiating MongoDB cluster handshake (Attempt {attempt + 1}/{max_retries})...")
        client = MongoClient(
            mongo_uri,
            server_api=ServerApi('1'),
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,  # Increase timeout from 20s to 30s
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=True
        )
        # Verify connection
        client.admin.command('ping')
        logger.info("MongoDB cluster connection verified successfully.")
        break
    except ServerSelectionTimeoutError as e:
        # Calculate Exponential Backoff: Attempt 0 = 2s, Attempt 1 = 4s, Attempt 2 = 8s
        current_delay = retry_delay * (2 ** attempt)

        if attempt < max_retries - 1:
            logger.warning(
                f"Network socket timeout on attempt {attempt + 1}. "
                f"Retrying in {current_delay}s... Details: {e}"
            )
            time.sleep(retry_delay)
        else:
            raise

checkpointer = MongoDBSaver(client)
    
app = workflow.compile(checkpointer=checkpointer)