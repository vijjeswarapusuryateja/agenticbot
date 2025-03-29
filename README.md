
# AgenticBot: Multi-Agent Chatbot Framework with Crew AI, FastAPI, and Streamlit

AgenticBot is a **dynamic and intelligent chatbot framework** designed to handle complex user interactions using **multi-agent collaboration**. The framework leverages **Crew AI** for agent orchestration, **FastAPI** for backend processing, and **Streamlit** for a seamless interactive UI.

The chatbot efficiently handles **query refinement**, **response validation**, **summarization**, and **feedback analysis** while offering an **optional ticket creation workflow** for service desk or IT support scenarios.

---

## Table of Contents
1. [Features](#features)  
2. [Architecture](#architecture)  
3. [Technology Stack](#technology-stack)  
4. [Installation](#installation)  
5. [Usage](#usage)  
6. [Configuration](#configuration)  
7. [Contributing](#contributing)  
8. [Acknowledgements](#acknowledgements)  

---

## Features
- **Multi-Agent Collaboration:** Uses Crew AI to manage specialized agents for different tasks.  
- **Dynamic Query Handling:** Efficiently refines vague queries using a Supervisor Agent.  
- **Validation and Summarization:** Ensures accurate responses with validation and structured summarization.  
- **Feedback Management:** Detects user satisfaction and triggers ticket creation if necessary.  
- **Interactive UI:** Built with Streamlit for seamless user interaction.  
- **Ticket Generation (Addon):** Creates structured support tickets when triggered.  

---

## Architecture
The framework is designed using a **modular agentic approach** where each agent specializes in a specific task:

1. **Supervisor Agent:** Handles query refinement and clarification.  
2. **Validation Agent:** Verifies the accuracy and relevance of responses.  
3. **Summarization Agent:** Provides a concise and structured response.  
4. **Feedback Agent:** Analyzes user satisfaction and suggests ticket creation if necessary.  
5. **Ticket Agent (Addon):** Generates structured summaries for ticketing when triggered.  

---

## 🛠️ Technology Stack
- **Crew AI:** Multi-agent collaboration and task delegation.  
- **FastAPI:** High-performance backend for API endpoints.  
- **Streamlit:** Interactive frontend for chat and ticket management.  
- **Vector DB:** Efficient knowledge base for policy retrieval.  
- **Python 3.12.6:** Core programming language.  

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/vijjeswarapusuryateja/agenticbot.git
cd agenticbot
```

### 2. Create and Activate a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scriptsctivate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Usage

### 1. Run the Backend API (FastAPI)
```bash
uvicorn bot:app --reload
```
- The API will be available at **`http://127.0.0.1:8000`**.  

### 2. Run the Frontend (Streamlit)
```bash
streamlit run streamlit_app.py
```
- Access the Streamlit UI at **`http://localhost:8501`**.  

### 3. Interact with the Bot
- Ask your queries in the Streamlit UI and see how the agents dynamically handle the response.  
- If a ticket is triggered, you can choose whether to create one or not.  

---

## Configuration
Update the configuration settings in the **`.env`** file:
```bash
API_URL=http://127.0.0.1:8000/query
TICKET_API_URL=http://127.0.0.1:8000/create_ticket
LOG_LEVEL=INFO
```
- Make sure to update the API keys and endpoints as needed.  

---

## Contributing
Contributions are welcome!
1. Fork the repository.  
2. Create a new branch:
   ```bash
   git checkout -b feature-branch
   ```
3. Make your changes and commit:
   ```bash
   git commit -m 'Add new feature'
   ```
4. Push to the branch:
   ```bash
   git push origin feature-branch
   ```
5. Open a Pull Request.  

---

## Acknowledgements
Thanks to **Crew AI**, **FastAPI**, and **Streamlit** communities for their excellent tools and documentation.
