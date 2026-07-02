import streamlit as st
from supabase import create_client, Client
import os
import base64
from email.message import EmailMessage
from dotenv import load_dotenv
from src.tools import get_gmail_service 

load_dotenv()

# Setup Data Connections
st.set_page_config(page_title="AI Email Command Center", layout="wide")

@st.cache_resource
def init_connection():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_connection()
gmail_service = get_gmail_service()

# Fetch Data
st.title("📬 AI Email Command Center")

# Fetch ALL emails (both pending and sent)
response = supabase.table("email_drafts").select("*").order("created_at", desc=True).execute()
all_emails = response.data

pending_emails = [e for e in all_emails if e['status'] == 'pending_review']
sent_emails = [e for e in all_emails if e['status'] == 'sent']

def create_raw_email(to_email, subject, body_text):
    message = EmailMessage()
    message.set_content(body_text)
    message['to'] = to_email
    message['subject'] = subject
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

# Create a table Interface
tab1, tab2 = st.tabs(["📝 Pending Reviews", "✅ Sent History"])

# Tab 1: Pending Reviews
with tab1:
    if not pending_emails:
        st.success("Inbox Zero! No pending drafts to review.")
    else:
        # Sidebar for selection
        st.sidebar.header("Pending Reviews")
        selected_index = st.sidebar.radio(
            "Select an email to review:", 
            range(len(pending_emails)), 
            format_func=lambda x: pending_emails[x]['sender_email'],
            key="pending_radio"
        )
        selected_email = pending_emails[selected_index]

        # Header
        st.subheader(f"Replying to: {selected_email['sender_email']}")
        
        # Display Intent and Urgency
        m1, m2, m3 = st.columns(3)
        m1.metric("Intent", str(selected_email.get('intent', 'N/A')).title())
        m2.metric("Urgency", str(selected_email.get('urgency', 'N/A')).title())
        m3.metric("Subject", selected_email['email_subject'][:30] + "...")

        # Collapsible box for the original customer email
        with st.expander("👀 View Original Customer Email", expanded=False):
            st.text(selected_email.get('email_content', 'No content available.'))

        # Editing Area
        st.markdown("### AI Draft Proposal")
        edited_body = st.text_area(
            "Review and edit the AI draft:", 
            value=selected_email['draft_body'], 
            height=300
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Edits (Don't Send)", use_container_width=True):
                with st.spinner("Updating..."):
                    raw_msg = create_raw_email(selected_email['sender_email'], selected_email['email_subject'], edited_body)
                    gmail_service.users().drafts().update(userId="me", id=selected_email['draft_id'], body={'message': {'raw': raw_msg}}).execute()
                    supabase.table("email_drafts").update({"draft_body": edited_body}).eq("id", selected_email['id']).execute()
                    st.success("Draft updated!")
                    st.rerun()

        with col2:
            if st.button("Send Email", type="primary", use_container_width=True):
                with st.spinner("Sending..."):
                    raw_msg = create_raw_email(selected_email['sender_email'], selected_email['email_subject'], edited_body)
                    gmail_service.users().drafts().update(userId="me", id=selected_email['draft_id'], body={'message': {'raw': raw_msg}}).execute()
                    gmail_service.users().drafts().send(userId="me", body={'id': selected_email['draft_id']}).execute()
                    supabase.table("email_drafts").update({"status": "sent"}).eq("id", selected_email['id']).execute()
                    st.success("Sent!")
                    st.rerun()

# Tab 2: Sent History
with tab2:
    if not sent_emails:
        st.info("No sent emails recorded yet.")
    else:
        st.sidebar.markdown("---")
        st.sidebar.header("Sent History")
        history_index = st.sidebar.radio(
            "Select an email to view:", 
            range(len(sent_emails)), 
            format_func=lambda x: sent_emails[x]['sender_email'],
            key="sent_radio"
        )
        history_email = sent_emails[history_index]
        
        st.subheader(f"Sent to: {history_email['sender_email']}")
        
        h1, h2 = st.columns(2)
        h1.metric("Intent", str(history_email.get('intent', 'N/A')).title())
        h2.metric("Urgency", str(history_email.get('urgency', 'N/A')).title())
        
        with st.expander("Customer's Original Message"):
            st.text(history_email.get('email_content', 'No content available.'))
            
        st.markdown("### What the AI Sent")
        st.text_area("Final Email:", value=history_email['draft_body'], height=300, disabled=True)