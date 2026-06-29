from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore

# Load environment variables globally
load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    vertexai=True,
    temperature=0
    )

# Vector Database & Retriever
embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004",
    vertexai=True
)

pc = Pinecone()
index = pc.Index('rag')
vectorstore = PineconeVectorStore(
    index=index, 
    embedding=embeddings
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 4}) 