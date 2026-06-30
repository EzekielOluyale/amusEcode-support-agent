from typing import TypedDict, Literal

# Define the structure for email classification
class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str

class EmailAgentState(TypedDict):
    # Raw email data
    email_content: str | None
    email_subject: str | None
    sender_email: str
    email_id: str

    # Context & Threading
    sender_firstname: str | None  
    sender_lastname: str | None   
    message_id: str | None
    thread_id: str | None

    # Classification result
    classification: EmailClassification | None
            
    # Raw search/API results
    search_results: list[str] | None  
    customer_history: dict | None  

    # Generated content
    draft_response: str | None
    messages: list[str] | None