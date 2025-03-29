import logging
import json
import os
from fastapi import FastAPI
from pydantic import BaseModel
from crewai import Agent, Task, Crew, LLM
from openai import OpenAI
import vector_db 
import time
import asyncio
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

#Load OpenAI Credentials
api_key = os.getenv("OPENAI_API_KEY")




#Initialize Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

#Initialize FastAPI
app = FastAPI(title="Evabot AI Agentic Framework", version="3.2")

#File for storing tickets (simulating a backend)
TICKET_FILE = "tickets.json"

#Initialize app state for storing recent queries and clarification attempts
if not hasattr(app.state, "recent_queries"):
    app.state.recent_queries = {}  # Stores last 5 queries per session
if not hasattr(app.state, "clarification_attempts"):
    app.state.clarification_attempts = {}  # Track clarification attempts per session



#Initialize OpenAI client
client = OpenAI(api_key=api_key)


#Define LLM Instance
llm = LLM(
    model="gpt-4o",
    api_key=api_key
)


#Define FastAPI Request Models
class QueryRequest(BaseModel):
    query: str
    session_id: str = "default_session"  # Used to track multiple queries from the same user

class TicketRequest(BaseModel):
    issue_summary: str
    issue_category: str

#Supervisor Agent (Query Refinement)**
supervisor_agent = Agent(
    role="Supervisor Agent",
    goal="Ensure the user's query is specific and well-defined.",
    backstory="You help refine vague queries to ensure the best possible response.",
    llm=llm
)

supervisor_task = Task(
    description="You refine vague queries before retrieval. "
                "Rephrase the query into a more specific form or ask ONE targeted clarifying question. "
                "Return either:\n"
                "- A refined query\n"
                "- A single clarification question (if needed)\n"
                "- The same query (if already clear)\n\n"
                "Recent queries for context:\n{recent_queries}",
    agent=supervisor_agent,
    expected_output="A refined query or a specific clarification question."
)

#Policy Retrieval Agent**
policy_retrieval_agent = Agent(
    role="Policy Retrieval Agent",
    goal="Retrieve the most relevant policy from the unified knowledge base.",
    backstory="You search company policies using semantic search.",
    llm=llm
)

policy_retrieval_task = Task(
    description="Search the company's **unified knowledge base** for the best-matching policy. "
                "If no good match is found, suggest alternative searches or ask for clarification.",
    agent=policy_retrieval_agent,
    expected_output="A relevant policy response."
)

#Validation Agent**
validation_agent = Agent(
    role="Validation Agent",
    goal="Ensure retrieved policies are accurate and clear.",
    backstory="You verify if the retrieved policies fully answer the query.",
    llm=llm
)

validation_task = Task(
    description="Check if the retrieved policies are relevant to the user's query. "
                "- If they fully answer the question, return them as-is.\n"
                "- If they are **partially relevant**, summarize the key points.\n"
                "- If they **do not match**, suggest refining the query.\n\n"
                "**User Query:** {query}\n"
                "**Retrieved Policies:** {retrieved_policies}\n\n"
                "**Expected Output:** A validated, relevant policy response.",
    agent=validation_agent,
    expected_output="A validated response."
)

#Summarization Agent**
summarization_agent = Agent(
    role="Summarization Agent",
    goal="Ensure the final response is concise and structured.",
    backstory="You refine validated responses into clear, well-structured answers.",
    llm=llm
)

summarization_task = Task(
    description="Summarize the validated response into a **concise, structured format**. "
                "- Do **not** change policy details.\n"
                "- Summarize **only** if the response is too long.\n"
                "- If already clear, return as-is.\n\n"
                "**Validated Response:** {validated_response}\n"
                "**Expected Output:** A clear, structured policy response.",
    agent=summarization_agent,
    expected_output="A well-structured final response."
)





#Feedback Agent (Handling User Feedback & IT Issues)**
feedback_agent = Agent(
    role="Feedback Agent",
    goal="Analyze user feedback, determine intent, and detect IT issues while prompting ticket creation when necessary.",
    backstory="You analyze user responses and classify their intent (satisfied, refinement needed, new query, IT issue, or general feedback). If an IT issue is detected, confirm with the user if they want to create a support ticket.",
    llm=llm
)

feedback_task = Task(
    description="Analyze the following user response and determine the intent. "
                "Always check for IT-related issues **first** before considering other intents."
                "\n\n**Intent Prioritization:**"
                "\n1**IT Issue - Prompt Ticket**: If the response mentions an IT problem (e.g., password reset, VPN issue, system failure), classify it as an IT issue and prompt ticket creation."
                "\n2**Satisfied**: If no IT issue is found, check if the user is happy with the answer."
                "\n3**Refine**: If no IT issue is found, determine if the user wants to refine or expand the answer."
                "\n4**New Question**: If the user is asking about a different topic, classify it accordingly."
                "\n5**General Feedback**: If the response is general feedback, classify it as such."
                
                "\n\n**User Response:** {user_response}"
                "\n**Previous Response:** {previous_response}"
                
                "\n\n**Important:** If the user mentions an IT-related issue (e.g., password reset, VPN, account lockout), classify it as an IT issue **before** considering other intents. "
                "Always prioritize IT detection over satisfaction or other intents.",
    agent=feedback_agent,
    expected_output="One of: 'IT Issue - Prompt Ticket', 'Satisfied', 'Refine', 'New Question', or 'General Feedback'."
)





#Ticket Agent**
ticket_agent = Agent(
    role="Ticket Agent",
    goal="Create an IT support ticket if the issue is unresolved.",
    backstory="You generate a structured ticket summary when users require further IT assistance.",
    llm=llm
)

ticket_task = Task(
    description="If the user indicates the issue is unresolved, generate a **structured IT support ticket summary** "
                "using the user's latest query **and** recent conversation context.\n\n"
                "Use the following inputs to ensure a well-structured summary:\n"
                "- **User's Latest Query:** {query}\n"
                "- **Recent Queries for Context:** {recent_queries}\n\n"
                "**Expected Output:** A structured IT support ticket summary that captures the issue comprehensively.\n\n"
                "Then, ask the user to **select a category** before creating the ticket.\n\n"
                "Expected categories: ['Network Issue', 'Password Reset', 'Software Installation', 'Hardware Problem'].",
    agent=ticket_agent,
    expected_output="A structured ticket summary, followed by category selection."
)


#API Endpoint: Handle User Query
@app.post("/query")
async def handle_query(request: QueryRequest):
    """Handles user queries by refining vague queries before retrieval."""
    start_time_total = time.time()
    logger.info(f"Received query: {request.query} (Session: {request.session_id})")

    #Ensure session storage for recent queries and clarifications
    app.state.recent_queries.setdefault(request.session_id, []).append(request.query)
    app.state.recent_queries[request.session_id] = app.state.recent_queries[request.session_id][-5:]

    if not hasattr(app.state, "clarification_attempts"):
        app.state.clarification_attempts = {}  # Store pending clarifications

    if not hasattr(app.state, "pending_refinement"):
        app.state.pending_refinement = {}  # Store user responses that require refinement

    #Handle User Clarifications
    if request.session_id in app.state.clarification_attempts:
        prev_clarification = app.state.clarification_attempts.pop(request.session_id)
        logger.info(f"Processing clarification response: {request.query} (Previous: {prev_clarification})")

        #Use Supervisor Agent to structure the final query meaningfully
        query_rewrite_crew = Crew(agents=[supervisor_agent], tasks=[
            Task(
                description="Rephrase the following query into a structured, self-contained search query. "
                            "Ensure it is meaningful and provides complete context."
                            "\n\nOriginal Query: {prev_query}"
                            "\nUser Clarification: {clarification}",
                agent=supervisor_agent,
                expected_output="A final, context-aware search query."
            )
        ])
        refined_query = await asyncio.to_thread(query_rewrite_crew.kickoff, inputs={
            "prev_query": prev_clarification,
            "clarification": request.query
        })

    else:
        #Supervisor Agent – Initial Query Refinement
        supervisor_crew = Crew(agents=[supervisor_agent], tasks=[supervisor_task])
        refined_query = await asyncio.to_thread(supervisor_crew.kickoff, inputs={
            "query": request.query,
            "recent_queries": "\n".join(app.state.recent_queries[request.session_id])
        })

    #Convert CrewOutput to String
    refined_query_str = str(refined_query).strip()

    #Detect if Supervisor Returned a Clarification Question
    if refined_query_str.endswith("?"):
        logger.info(f"❓ Clarification Needed: {refined_query_str}")
        app.state.clarification_attempts[request.session_id] = request.query  # Store original question
        return {"response": refined_query_str, "clarification_needed": True}

    #Retrieve Policies (Proceed Only If No Clarification Needed)
    policy_response = vector_db.query_policies(refined_query_str)

    #Validate Policies
    validation_crew = Crew(agents=[validation_agent], tasks=[validation_task])
    validated_response = await asyncio.to_thread(validation_crew.kickoff, inputs={
        "query": refined_query_str,
        "retrieved_policies": policy_response
    })

    #Convert CrewOutput to a String
    validated_response_str = str(validated_response).strip()

    #Summarize Response
    summarization_crew = Crew(agents=[summarization_agent], tasks=[summarization_task])
    summarization_result = await asyncio.to_thread(summarization_crew.kickoff, inputs={
        "validated_response": validated_response_str 
    })

    #Extract clean response
    if isinstance(summarization_result, dict) and "tasks_output" in summarization_result:
        final_response = summarization_result["tasks_output"][0].get("raw", "").strip()
    else:
        final_response = str(summarization_result).strip()

    logger.info(f"Final Clean Response: {final_response}")

    # Trigger Feedback Agent**
    logger.info(f"🚀 Triggering Feedback Agent for user response analysis.")

    feedback_crew = Crew(agents=[feedback_agent], tasks=[feedback_task])
    feedback_result = await asyncio.to_thread(feedback_crew.kickoff, inputs={
        "user_response": final_response,
        "previous_response": validated_response_str
    })

    feedback_str = str(feedback_result).strip()
    logger.info(f"🔍 Feedback Agent Analysis Result: {feedback_str}")

    # Handle Feedback Response (Including IT Issues)**
    if "IT Issue - Prompt Ticket" in feedback_str:
        logger.info("🚀 IT-related issue detected by Feedback Agent. Asking user if they want to create a ticket.")

        return {
            "response": final_response,  # how final response normally
            "prompt_ticket": True  # sk user for confirmation in Streamlit
        }
    elif "Satisfied" in feedback_str:
        follow_up_response = "Glad I could help! 😊 Let me know if you have any other questions."
    elif "Refine" in feedback_str:
        app.state.pending_refinement[request.session_id] = final_response
        follow_up_response = "Please provide more details so I can refine my answer. ✏️"
    elif "New Question" in feedback_str:
        follow_up_response = "Sure! What other policy would you like to ask about? 🔄"
    else:
        follow_up_response = "Thank you for your feedback! Let me know if I can assist you further. 🙌"

    total_time = time.time() - start_time_total
    logger.info(f"⏱️ **Total Query Processing Time: {total_time:.2f} seconds**")

    return {"response": f"{final_response}\n\n🔍 *{follow_up_response}*"}



# API Endpoint: Generate Ticket Summary
@app.post("/generate_ticket_summary")
async def generate_ticket_summary(request: QueryRequest):
    """Generates a structured ticket summary using the Ticket Agent."""
    logger.info(" Generating structured summary for IT support ticket.")

    #**Trigger Ticket Agent for Structured Summary**
    ticket_crew = Crew(agents=[ticket_agent], tasks=[ticket_task])
    ticket_summary_result = await asyncio.to_thread(ticket_crew.kickoff, inputs={
        "query": request.query,  # User's original query
        "recent_queries": "\n".join(app.state.recent_queries.get(request.session_id, [])) if app.state.recent_queries.get(request.session_id) else "No recent queries available."
    })

    # Convert Ticket Agent Output to String
    ticket_summary = str(ticket_summary_result).strip()
    logger.info(f"Structured Ticket Summary: {ticket_summary}")

    return {"ticket_summary": ticket_summary}



#  API Endpoint: Create Ticket
@app.post("/create_ticket")
async def create_ticket(request: TicketRequest):
    """Creates an IT support ticket."""
    logger.info(f"Creating IT support ticket.")

    ticket = {
        "ticket_id": f"TCK-{len(load_tickets()) + 1:04d}",
        "issue_summary": request.issue_summary,
        "issue_category": request.issue_category,
        "status": "Open"
    }

    save_ticket(ticket)

    return {
        "response": f" Ticket Created: {ticket['ticket_id']} in category *{ticket['issue_category']}*.",
        "ticket": ticket
    }



def load_tickets():
    """Load existing tickets from a JSON file."""
    if os.path.exists(TICKET_FILE):
        with open(TICKET_FILE, "r") as file:
            return json.load(file)
    return []

def save_ticket(ticket):
    """Save a new ticket to the JSON file."""
    tickets = load_tickets()
    tickets.append(ticket)
    with open(TICKET_FILE, "w") as file:
        json.dump(tickets, file, indent=4)



