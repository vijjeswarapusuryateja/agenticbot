import os
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
import logging
import re
from typing import List
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


#Initialize Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


#Load OpenAI Credentials
api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Initialize ChromaDB with Persistence
DB_PATH = "./vector_db"
chroma_client = chromadb.PersistentClient(path=DB_PATH)

# Define Custom ChromaDB Embedding Function
class OpenAIEmbeddingFunction:
    """Custom embedding function class for ChromaDB compatible with OpenAI."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        if isinstance(input, str):
            input = [input]

        try:
            response = client.embeddings.create(
                input=input,
                model="text-embedding-ada-002"
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return [[0.0] * 1536] * len(input)

# Use the Custom Embedding Function
embedding_function = OpenAIEmbeddingFunction()

# Define Unified Collection in ChromaDB
collection = chroma_client.get_or_create_collection(name="company_policies", embedding_function=embedding_function)

# Unified Knowledge Base (Single Dictionary)
KNOWLEDGE_BASE = {
    "leave policy": "Employees are entitled to 20 annual leaves per year. Unused leaves cannot be carried over. Sick leave requires a medical certificate if taken for more than 2 consecutive days.",
    "maternity leave": "Female employees are entitled to 26 weeks of paid maternity leave. Additional unpaid leave can be requested up to 16 weeks.",
    "paternity leave": "Male employees can avail up to 2 weeks of paid paternity leave.",
    "salary increments": "Annual salary increments are performance-based and reviewed every April. Employees with outstanding performance may receive additional bonuses.",
    "promotion criteria": "Promotions are based on performance reviews, leadership potential, and business needs. Employees can apply for internal job postings after 1 year in their current role.",
    "remote work policy": "Employees can work remotely up to 3 days a week. Fully remote positions require management approval.",
    "overtime policy": "Employees working beyond 40 hours per week are eligible for overtime pay or compensatory time off, subject to approval.",
    "health benefits": "Company provides full medical insurance to employees and dependents, covering hospitalization, consultation, and medications.",
    "retirement plan": "Employees are enrolled in a company-sponsored retirement plan with a 5% employer contribution match.",
    "password reset": "To reset your password, visit the IT portal and click 'Forgot Password'. If locked out, contact IT Support.",
    "vpn issue": "Ensure your VPN software is updated. If issues persist, restart your computer and reconnect.",
    "email access issue": "If you cannot access your email, reset your password via the email portal. If issues persist, check Outlook settings.",
    "software installation": "Submit a request through the IT Helpdesk for software installation. Approval from your manager may be required.",
    "printer not working": "Ensure the printer is powered on and connected. If issues persist, reinstall the drivers or contact IT support.",
    "incident reporting": "Employees must report security breaches within 24 hours to the IT Security Team.",
    "firewall rules": "Strict firewall rules are enforced to block unauthorized access to company systems.",
}

# Generate OpenAI Embeddings for Text
def get_embedding(text: str):
    """Fetch OpenAI embeddings with error handling."""
    if not text or not isinstance(text, str):  #Prevent invalid input
        logger.warning(f"Skipping embedding: Invalid text input - {text}")
        return None
    
    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=[text]  #Ensure input is always a list
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding for '{text}': {str(e)}")
        return None



# Function to Insert Policies into ChromaDB
def insert_policies():
    """Store all policies in a single ChromaDB collection."""
    logger.info("\nIndexing Policies into Unified Knowledge Base...")

    for key, value in KNOWLEDGE_BASE.items():
        embedding = get_embedding(value)
        if embedding is None:
            logger.warning(f"Skipping policy {key} due to embedding failure.")
            continue

        try:
            collection.add(
                ids=[key],
                embeddings=[embedding],
                metadatas=[{"policy": value}]
            )
            logger.info(f"Stored Policy: {key} → {value[:50]}...")
        except Exception as e:
            logger.error(f"Error inserting policy {key}: {str(e)}")


# Function to Query Policies
def query_policies(query: str) -> str:
    """Query VectorDB for policy information and summarize the best match."""
    
    logger.info(f"Searching Unified Knowledge Base for query: {query}")

    # Generate embedding for query
    query_embedding = get_embedding(query)
    if query_embedding is None:
        logger.warning(f"Embedding failed for query: {query}. Skipping search.")
        return "Error generating query embedding."

    # Step 1: Vector Search
    results = collection.query(query_embeddings=[query_embedding], n_results=3)

    # Check if valid results exist
    if results and results.get("metadatas", [[]])[0]:
        logger.info(f"🔍 Vector search results for query: {query}")

        filtered_policies = []
        for i, metadata in enumerate(results["metadatas"][0]):
            similarity = results.get("distances", [[]])[0][i]
            policy_text = metadata.get("policy", "")

            # Adjust similarity threshold
            if similarity < 0.5:  
                filtered_policies.append(policy_text)
                logger.info(f"   Match {i+1}: {policy_text[:50]}... (Score: {similarity})")
            else:
                logger.info(f"   Ignored Weak Match {i+1}: {policy_text[:50]}... (Score: {similarity})")

        if not filtered_policies:
            return "No relevant policy found."

        # Summarize if multiple results found
        if len(filtered_policies) == 1:
            return filtered_policies[0]
        else:
            summary = "\n\n".join([f"{policy}" for policy in filtered_policies])
            return f"I found multiple relevant policies:\n\n{summary}\n\nWould you like to refine your query?"

    return "No relevant policy found."


# Run This to Index Policies
if __name__ == "__main__":
    insert_policies()
    logger.info("All policies have been indexed successfully!")


    # TESTING QUERIES
    queries = [
        "What is my leave policy?",
        "How do I reset my password?",
        "What are the firewall security rules?",
        "Tell me about maternity leave benefits.",
        "I need help with VPN issues."
    ]

    for test_query in queries:
        response = query_policies(test_query)
        logger.info(f"Query: {test_query}\n Response: {response}\n")
