import os
import base64
import requests
from typing import Literal
from email.message import EmailMessage
from src.logger import setup_logger

from langgraph.types import Command, interrupt
from langgraph.graph import END
from langchain.messages import SystemMessage, HumanMessage

# Project Internal Imports
from src.state import EmailAgentState, EmailClassification
from src.config import llm, retriever
from src.tools import get_gmail_service
from src.utils import extract_body_from_gmail_payload
from src.prompts import SYSTEM_PROMPT

logger = setup_logger(__name__)

def read_email(state: EmailAgentState) -> dict:
    service = get_gmail_service()
    target_id = state.get('email_id')

    if not target_id:
        return {"messages": [HumanMessage(content="Error: No email ID found in state.")]}
    
    try:
        # Fetch the actual full message 
        msg = service.users().messages().get(userId="me", id=target_id, format='full').execute()
    
        # Extract headers (like 'From')
        headers = msg['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        sender = next(h['value'] for h in headers if h['name'] == 'From')
        full_body = extract_body_from_gmail_payload(msg['payload'])
    
        return {
            "email_content": full_body,
            "sender_email": sender,
            "email_subject": subject,
            "messages": [HumanMessage(content=f"Successfully fetched email from {sender}")]
        }
    except Exception as e:
        return {"messages": [HumanMessage(content=f"Error fetching email: {str(e)}")]}

def classify_intent(state: EmailAgentState) -> Command[Literal["search_documentation", "human_review", "draft_response", "bug_tracking"]]:
    """Use LLM to classify email intent and urgency, then route accordingly"""

    # Create structured LLM that returns EmailClassification dict
    structured_llm = llm.with_structured_output(EmailClassification)

    # Format the prompt on-demand, not stored in state
    classification_prompt = f"""
    Analyze this customer email and classify it:

    Email: {state['email_content']}
    From: {state['sender_email']}

    Provide classification including intent, urgency, topic, and summary.
    """

    # Get structured response directly as dict
    classification = structured_llm.invoke(classification_prompt)

    # Determine next node based on classification
    if classification['intent'] == 'billing' or classification['urgency'] == 'critical':
        goto = "human_review"
    elif classification['intent'] in ['question', 'feature']:
        goto = "search_documentation"
    elif classification['intent'] == 'bug':
        goto = "bug_tracking"
    else:
        goto = "draft_response"

    # Store classification as a single dict in state
    return Command(
        update={"classification": classification},
        goto=goto
    )

def search_documentation(state: EmailAgentState) -> Command[Literal["draft_response"]]:
    """Search knowledge base for relevant information"""

    # Build search query from classification
    classification = state.get('classification', {})
    query = f"{classification.get('intent', '')} {classification.get('topic', '')}"

    try:
        docs = retriever.invoke(query)
        search_results = [f"[DOCS]: {doc.page_content}" for doc in docs]
    except Exception as e:
        logger.error(f"Pinecone search failed: {e}")
        search_results = [f"[DOCS]: Search unavailable: {str(e)}"]

    return Command(
        update={"search_results": search_results},  # Store raw results or error
        goto="draft_response"
    )

def bug_tracking(state: EmailAgentState) -> Command[Literal["draft_response"]]:
    """Create a bug tracking ticket via GitHub API"""
    
    # Extract details from the current state
    classification = state.get('classification', {})
    email_content = state.get('email_content', '')
    sender = state.get('sender_email', 'Unknown User')

    issue_title = f"User Bug Report: {classification.get('summary', 'Issue detected')}"
    
    # We put the sender and original email in the body for the dev team
    issue_body = f"**Reported by:** {sender}\n\n**Original Email:**\n{email_content}"

    # Setup the API request parameters
    token = os.getenv("GITHUB_TOKEN") 
    repo_owner = "EzekielOluyale" 
    repo_name = "amusEcode-support-agent"
    
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    payload = {
        "title": issue_title,
        "body": issue_body,
        "labels": ["bug", "user-reported"]
    }

    try:
        # Send the POST request to create the ticket
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status() 
        
        # Extract the new Ticket ID from GitHub's response
        issue_data = response.json()
        ticket_id = issue_data.get("number")
        ticket_url = issue_data.get("html_url")
        
        logger.info(f"Created GitHub Issue #{ticket_id}")
        result_message = f"[BUG_TICKET]: I have created a bug ticket for our engineering team. Ticket #{ticket_id} (Link: {ticket_url})"
        
    except Exception as e:
        logger.error(f"Failed to create GitHub Issue: {e}")
        result_message = f"[BUG_TICKET]: I tried to automatically log this bug, but encountered an error: {str(e)}. Please notify the engineering team."

    return Command(
        update={
            "search_results": [result_message], 
        },
        goto="draft_response"
    )

def draft_response(state: EmailAgentState) -> Command[Literal["human_review", "send_reply"]]:
    """Generate response using context and route based on quality"""

    classification = state.get('classification', {})

    # Format context from raw state data on-demand
    context_sections = []

    if state.get('search_results'):
        # Format search results for the prompt
        formatted_docs = "\n".join([f"- {doc}" for doc in state['search_results']])
        context_sections.append(f"Relevant documentation:\n{formatted_docs}")

    if state.get('customer_history'):
        # Format customer data for the prompt
        context_sections.append(f"Customer tier: {state['customer_history'].get('tier', 'standard')}")

    # Build the prompt with formatted context
    draft_prompt = f"""
    Draft a response to this customer email:
    {state['email_content']}

    Email intent: {classification.get('intent', 'unknown')}
    Urgency level: {classification.get('urgency', 'unknown')}

    {chr(10).join(context_sections)}

    TASK INSTRUCTIONS:
    - Address their specific concern directly.
    - Use the provided documentation when relevant.
    - CRITICAL: If a [BUG_TICKET] is provided in the context above, you MUST explicitly include the Ticket ID and the Link in your response to the user.
    """

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=draft_prompt)
    ]

    response = llm.invoke(messages)

    # Determine if human review needed based on urgency and intent
    needs_review = (
        classification.get('urgency') in ['high', 'critical'] or
        classification.get('intent') == 'complex'
    )

    # Route to appropriate next node
    goto = "human_review" if needs_review else "send_reply"

    return Command(
        update={"draft_response": response.content},  # Store only the raw response
        goto=goto
    )

def human_review(state: EmailAgentState) -> dict:
    service = get_gmail_service()
    
    message = EmailMessage()
    message.set_content(state['draft_response'])
    
    message['to'] = state['sender_email']
    message['subject'] = f"Re: {state.get('email_subject', 'Support Request')}"
    
    if state.get('email_id'):
        message['In-Reply-To'] = state['email_id']
        message['References'] = state['email_id']
        
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    
    try:
        create_message = {
            'message': {
                'raw': encoded_message
            }
        }
        
        if state.get('thread_id'):
            create_message['message']['threadId'] = state.get('thread_id')
            
        draft = (
        service.users()
        .drafts()
        .create(userId="me", body=create_message)
        .execute()
    )
        
        logger.info(f"Gmail draft created successfully. Draft ID: {draft['id']}")
        return {
            "messages": [HumanMessage(content=f"Draft created for human review. ID: {draft['id']}")]
        }
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR creating draft: {e}")
        return {
            "messages": [HumanMessage(content=f"Error creating draft: {str(e)}")]
        }

def send_reply(state: EmailAgentState) -> dict:
    """Send the email response"""
    service = get_gmail_service()

    message = EmailMessage()
    message.set_content(state['draft_response'])
    
    message['to'] = state['sender_email']
    message['subject'] = f"Re: {state.get('email_subject', 'Support Request')}"

    message['In-Reply-To'] = state['email_id']
    message['References'] = state['email_id']

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        create_message = {'raw': encoded_message}
        if state.get('thread_id'):
            create_message['threadId'] = state.get('thread_id')
            
        # Send the message
        send_message = (
        service.users()
        .messages()
        .send(userId="me", body=create_message)
        .execute()
    )
        
        return {
            "messages": [HumanMessage(content=f"Email sent successfully! ID: {send_message['id']}")]
        }
        
    except Exception as e:
        return {
            "messages": [HumanMessage(content=f"Error sending email: {str(e)}")]
        }