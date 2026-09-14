# Webpage / Web Application Knowledge Guide

## 1. What We Built

The project now has a web-based interface for the PSA AI Knowledge Engine.

Previously, the Knowledge Engine was primarily accessed through a terminal/CLI interface. The web implementation adds a browser-based interface so users can interact with the same backend through a normal webpage.

The webpage provides:

* A chat interface for asking questions
* Conversation history during the current chat
* Freshdesk/customer data statistics
* Last synchronization information
* A manual data synchronization button
* A simple system status indicator
* Markdown-formatted AI responses

The webpage is intended to become the main user-facing interface for PSA AI.

---

# 2. Technologies Used

The web implementation uses several technologies, each with a different responsibility.

## Python

Python is the main programming language of the project.

The existing Knowledge Engine, database logic, Freshdesk/Jira integrations, AI providers, retrieval system, and the web backend are all implemented in Python.

The webpage therefore connects naturally to the existing Python application instead of requiring a separate backend technology.

---

## FastAPI

**FastAPI** is the Python web framework used to create the backend API for the webpage.

In simple terms:

> FastAPI allows Python functions to become web endpoints that a browser can call.

For example, instead of the webpage directly accessing SQLite or calling the AI provider, it sends a request to FastAPI:

```text
Webpage
   ↓
POST /chat
   ↓
FastAPI
   ↓
Knowledge Engine
   ↓
AI response
   ↓
FastAPI
   ↓
Webpage
```

FastAPI is responsible for receiving HTTP requests, executing the appropriate Python backend logic, and returning responses to the webpage.

The FastAPI application is defined in:

```text
api.py
```

The FastAPI application object is:

```python
app
```

---

## Uvicorn

**Uvicorn** is the server that actually runs the FastAPI application.

FastAPI defines the application and its endpoints.

Uvicorn provides the web server that listens for incoming HTTP requests.

A simple way to think about it:

```text
FastAPI = defines what the application does

Uvicorn = runs the application and listens for web requests
```

For example:

```powershell
uvicorn api:app --reload --port 8001
```

means:

* `api` → use `api.py`
* `app` → use the FastAPI object called `app`
* `--reload` → automatically reload during development when Python files change
* `--port 8001` → listen on port 8001

---

## NSSM

**NSSM** stands for **Non-Sucking Service Manager**.

It is a Windows utility that allows a normal application such as Python/Uvicorn to run as a Windows service.

This is useful on the server because we do not want someone to manually open a terminal and run Uvicorn every time the server starts.

The Windows service is:

```text
SupportCopilot
```

NSSM is configured to run:

```text
C:\Support-Copilot\.venv\Scripts\python.exe
```

with:

```text
-m uvicorn api:app --host 0.0.0.0 --port 8000
```

The application directory is:

```text
C:\Support-Copilot
```

Therefore the server architecture is:

```text
Windows
   ↓
NSSM Service: SupportCopilot
   ↓
Python virtual environment
   ↓
Uvicorn
   ↓
FastAPI (api.py)
```

---

# 3. Local vs Server Ports

The application currently uses different ports locally and on the server.

## Local development

```text
127.0.0.1:8001
```

Started with:

```powershell
uvicorn api:app --reload --port 8001
```

Port `8001` was chosen locally because port `8000` caused a Windows socket/permission issue.

## Server

The server uses:

```text
0.0.0.0:8000
```

NSSM starts:

```text
-m uvicorn api:app --host 0.0.0.0 --port 8000
```

This difference is intentional.

The application does not require the same port in both environments.

---

# 4. The Webpage Frontend

The webpage itself is implemented using standard web technologies:

* HTML
* CSS
* JavaScript

The current webpage contains:

```text
Sidebar
 ├── PSA AI branding
 ├── New conversation
 ├── Freshdesk ticket count
 ├── Customer count
 ├── Last synchronization time
 ├── Sync Data button
 └── Knowledge Engine status

Main area
 ├── Welcome message
 ├── Conversation messages
 └── Question input / Send button
```

The webpage is designed as a chat-style application.

The HTML contains the visual structure and CSS styling, while JavaScript handles communication with the FastAPI backend.

The frontend identifies itself as:

```text
PSA AI
AI-powered knowledge & data assistant
```

---

# 5. JavaScript and Backend Communication

The webpage uses JavaScript's `fetch()` function to communicate with FastAPI.

The browser does not directly call the database or AI provider.

Instead:

```text
JavaScript
   ↓
HTTP request
   ↓
FastAPI endpoint
   ↓
Python backend
```

This separation is important because it keeps the frontend independent from the internal implementation of the Knowledge Engine.

---

# 6. API Endpoints

The web application currently uses three main API endpoints.

## GET /stats

```text
GET /stats
```

Purpose:

> Retrieve information used by the sidebar of the webpage.

The frontend calls:

```javascript
fetch("/stats")
```

The returned data is used to display:

* Number of Freshdesk tickets
* Number of customers
* Last synchronization timestamp

The frontend expects data in the following general structure:

```json
{
    "tickets": 31245,
    "customers": 31505,
    "last_sync": "..."
}
```

The exact values depend on the current database.

If there is no synchronization timestamp, the webpage displays:

```text
Never
```

---

## POST /sync

```text
POST /sync
```

Purpose:

> Trigger a data synchronization from the webpage.

When the user clicks:

```text
↻ Sync Data
```

JavaScript sends:

```javascript
fetch("/sync", {
    method: "POST"
})
```

The button is disabled while synchronization is running.

The UI changes to:

```text
↻ Syncing...
```

After a successful synchronization it temporarily displays:

```text
✓ Sync completed
```

The statistics are then refreshed.

This means the webpage does not implement the synchronization logic itself.

Instead:

```text
User clicks Sync
       ↓
POST /sync
       ↓
Backend sync function
       ↓
Database updated
       ↓
Statistics refreshed
```

---

## POST /chat

```text
POST /chat
```

This is the main AI endpoint.

Purpose:

> Send the user's question and conversation history to the Knowledge Engine and return the AI response.

The browser sends JSON containing:

```json
{
    "message": "User question",
    "history": []
}
```

The backend processes the request through the existing AI/Knowledge Engine architecture.

The response contains the generated answer and updated conversation history.

The frontend then does:

```javascript
addMessage("assistant", data.answer);
history = data.history;
```

Therefore the browser maintains the conversation history while the backend remains responsible for processing the actual question.

---

# 7. Chat Flow

The complete chat flow is approximately:

```text
User enters question
        ↓
JavaScript sendMessage()
        ↓
POST /chat
        ↓
FastAPI
        ↓
Knowledge Engine
        ↓
Database / Retrieval / Tools
        ↓
AI Provider
        ↓
Answer
        ↓
FastAPI response
        ↓
JavaScript
        ↓
Display answer
```

The frontend also displays:

```text
Thinking...
```

while the request is being processed.

If the request fails, the webpage displays a generic error message rather than exposing the backend exception directly.

---

# 8. Conversation History

The webpage maintains a JavaScript variable:

```javascript
let history = [];
```

When a question is sent, the current history is included in the `/chat` request.

The backend returns updated history.

The webpage then replaces its local history with:

```javascript
history = data.history;
```

This allows multiple questions to remain part of the same conversation.

---

# 9. New Conversation

The sidebar contains:

```text
＋ New conversation
```

This calls:

```javascript
newChat()
```

The function:

1. Clears the current conversation history
2. Clears the displayed messages
3. Restores the welcome screen
4. Clears the input field
5. Focuses the input

In other words, it starts a new browser-side conversation without requiring a new server process.

---

# 10. Markdown Responses

AI responses can contain Markdown formatting.

For assistant messages, the webpage uses:

```javascript
marked.parse(text)
```

This converts Markdown returned by the AI into HTML for display.

For example, an AI response containing:

```markdown
## Root Cause

The issue is related to...

- Point 1
- Point 2
```

can be displayed as properly formatted headings and bullet points instead of plain text.

User messages are displayed as text rather than being interpreted as HTML.

---

# 11. Input Handling

The question input is a `<textarea>`.

The webpage supports:

```text
Enter       → Send message
Shift+Enter → New line
```

The textarea also automatically grows as the user types, up to a defined maximum height.

This provides a more natural chat experience without requiring a separate submit form.

---

# 12. Data Sidebar

The sidebar provides basic visibility into the local knowledge database.

Currently displayed information includes:

```text
Freshdesk
X tickets

Customers
X customers

Last sync
<date/time>
```

The values are loaded dynamically through:

```text
GET /stats
```

This means the webpage does not contain hard-coded ticket/customer counts for normal operation.

---

# 13. Manual Synchronization

The webpage provides:

```text
↻ Sync Data
```

This allows synchronization to be triggered manually when needed.

The synchronization itself remains a backend responsibility.

The broader project also plans to run synchronization through a scheduled task, so the manual button is intended as an additional on-demand option.

The intended architecture is:

```text
Automatic scheduled sync
        OR
Manual Web UI sync
        ↓
Same backend synchronization logic
        ↓
SQLite database
```

This avoids having two separate synchronization implementations.

---

# 14. Webpage and Knowledge Engine Separation

One of the most important architectural decisions is that the webpage is **not the Knowledge Engine**.

The webpage is an interface to it.

The separation is:

```text
                    WEB LAYER
                       │
             ┌─────────┴─────────┐
             │                   │
          HTML/CSS           JavaScript
             │                   │
             └─────────┬─────────┘
                       │
                     HTTP
                       │
                       ▼
                    FastAPI
                    api.py
                       │
                       ▼
               Knowledge Engine
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       SQLite       Retrieval     AI Provider
          │
          ├── Freshdesk
          └── Jira
```

This allows the web interface to change without rebuilding the underlying AI/retrieval architecture.

---

# 15. Why FastAPI Was Used

FastAPI was chosen because the existing project is already Python-based.

This allows the web layer to call existing Python functions directly instead of creating another backend technology.

For example:

```text
Web request
    ↓
FastAPI
    ↓
existing Python function
    ↓
existing Knowledge Engine
```

This keeps the architecture relatively simple.

FastAPI also provides automatic API handling, request parsing, JSON responses, and standard HTTP endpoint support.

---

# 16. Why Uvicorn Was Used

FastAPI is the application framework, but it needs an ASGI server to actually receive HTTP requests.

Uvicorn provides that server.

Therefore:

```text
FastAPI → application framework
Uvicorn → server that runs the FastAPI application
```

---

# 17. Why NSSM Was Used

The development environment can simply run:

```powershell
uvicorn api:app --reload
```

But a server needs the application to keep running without someone manually keeping a terminal open.

NSSM solves this by registering the application as a Windows service.

The server can therefore run:

```text
Windows Service
     ↓
NSSM
     ↓
Python
     ↓
Uvicorn
     ↓
FastAPI
```

The service can be controlled using:

```powershell
C:\nssm\nssm.exe start SupportCopilot
```

```powershell
C:\nssm\nssm.exe stop SupportCopilot
```

```powershell
C:\nssm\nssm.exe restart SupportCopilot
```

```powershell
C:\nssm\nssm.exe status SupportCopilot
```

---

# 18. Current Server Configuration

Current NSSM configuration:

```text
Service:
SupportCopilot

Application:
C:\Support-Copilot\.venv\Scripts\python.exe

AppDirectory:
C:\Support-Copilot

Arguments:
-m uvicorn api:app --host 0.0.0.0 --port 8000
```

The `0.0.0.0` host means Uvicorn listens on all network interfaces on the server rather than only accepting connections from the server itself.

---

# 19. Current Web Architecture Summary

The current implementation can be summarized as:

```text
Browser
   │
   │ HTTP
   ▼
FastAPI (api.py)
   │
   ├── GET  /stats
   │
   ├── POST /sync
   │
   └── POST /chat
   │
   ▼
Existing Python Knowledge Engine
   │
   ├── SQLite
   ├── Freshdesk
   ├── Jira
   ├── Retrieval
   ├── Tools
   └── AI Provider
```

The web application therefore adds a browser interface without replacing the existing Knowledge Engine.

---

# 20. Current Status

Implemented:

* FastAPI web backend
* Uvicorn application server
* Browser-based HTML/CSS/JavaScript interface
* Chat interface
* Conversation history
* `/chat` endpoint
* `/stats` endpoint
* `/sync` endpoint
* Dynamic ticket/customer statistics
* Last synchronization display
* Manual synchronization button
* Markdown rendering for AI responses
* New conversation functionality
* Server deployment through NSSM
* Local development configuration on port `8001`
* Server configuration on port `8000`

The FastAPI application has been successfully tested locally and on the server.

The server was also tested by running Uvicorn directly:

```powershell
C:\Support-Copilot\.venv\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000
```

and the application reached:

```text
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

This confirms that the FastAPI/Uvicorn application itself is functioning correctly independently of the NSSM service state.

---

# 21. Important Distinction

There are three different layers that should not be confused:

### Frontend

```text
HTML
CSS
JavaScript
```

Responsible for what the user sees and how the browser communicates with the backend.

### Backend Web API

```text
FastAPI
api.py
```

Responsible for receiving browser requests and calling the appropriate Python functionality.

### Knowledge Engine

```text
Existing Python modules
Database
Retrieval
Tools
AI providers
```

Responsible for actually understanding the question, retrieving information, querying data, and generating the answer.

The intended relationship is:

> **The webpage is the interface. FastAPI is the bridge. The Knowledge Engine is the intelligence.**
