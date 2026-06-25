import os
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from langgraph.checkpoint.mongodb import MongoDBSaver

# Project Internal Imports
from src.state import EmailAgentState
from src.nodes import read_email, classify_intent, search_documentation, bug_tracking, draft_response, human_review, send_reply

# Create the graph
workflow = StateGraph(EmailAgentState)

# Add nodes with appropriate error handling
workflow.add_node("read_email", read_email)
workflow.add_node("classify_intent", classify_intent)

# Add retry policy for nodes that might have transient failures
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
workflow.add_edge("read_email", "classify_intent")
workflow.add_edge("send_reply", END)

mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(
    mongo_uri, 
    server_api=ServerApi('1'),
    )

checkpointer = MongoDBSaver(client)
    
app = workflow.compile(checkpointer=checkpointer)