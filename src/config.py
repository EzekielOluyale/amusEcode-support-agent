import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("CRITICAL ERROR: No API Key found in environment variables.")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=api_key,
    vertexai=True
    )

# Vector Database & Retriever
embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004",
    google_api_key=api_key,
    vertexai=True
)

pc = Pinecone()
index = pc.Index('rag')
vectorstore = PineconeVectorStore(
    index=index, 
    embedding=embeddings
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 4}) 