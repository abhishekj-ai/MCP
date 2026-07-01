# Salesforce CPQ ADK Agent with Human-in-the-Loop

This folder contains a complete implementation of an AI agent built using **Google's Agent Development Kit (ADK)** that integrates with a mock **Salesforce CPQ Model Context Protocol (MCP)** server. 

The agent is configured with a **Human-in-the-Loop (HITL) approval mechanism** that intercepts the quote creation process, prompting you for manual confirmation before the quote is officially created.

---

## Folder Structure

*   **`salesforce_mcp_server.py`**: A mock MCP server written using `FastMCP`. It simulates the official Salesforce **Hosted MCP Server (`sobject-all`)** by exposing standard tools: `executeSoqlQuery`, `getObjectSchema`, and `createRecord`.
*   **`salesforce_agent.py`**: Configures the ADK `Agent` and connects it to the MCP server. It implements the confirmation callback function `confirm_quote_creation` which triggers human-in-the-loop confirmation when the agent tries to create a `SBQQ__Quote__c` (Salesforce CPQ Quote) record.
*   **`run_salesforce_agent.py`**: An interactive CLI runner script. It drives the conversation, displays agent steps, intercepts the confirmation request, prompts the user for approval, and resumes execution with the user's decision.

---

## How It Works

```
                        +---------------------------------------+
                        |                 User                  |
                        +-------------------+-------------------+
                                            | 1. Prompt: "Create quote"
                                            v
+-----------------------+       +-----------+-----------+       +-----------------------+
|  Salesforce MCP Server| <---> |       ADK Agent       | <---> |  Gemini LLM Service  |
|     (sobject-all)     |       +-----------+-----------+       +-----------------------+
+-----------+-----------+                   | 2. Executing createRecord()
            ^                               v    for SBQQ__Quote__c
            |                   +-----------+-----------+
            |                   | confirm_quote_creation| (Callback)
            |                   +-----------+-----------+
            |                               | 3. Returns True (requires approval)
            |                               v
            |                   +-----------+-----------+
            |                   |  CLI Interactive Loop |
            |                   +-----------+-----------+
            |                               | 4. User inputs: 'yes'
            |                               v
            +-------------------------------+ 5. Resumes & executes tool
```

1.  **Callback Interception**: The `confirm_quote_creation` function in `salesforce_agent.py` is configured as the `require_confirmation` callback on the `McpToolset`. 
2.  **Tool Call Detection**: When the agent decides to invoke the `createRecord` tool for the object `SBQQ__Quote__c`, the callback is triggered. It detects the tool name and target object API name, returning `True` to pause execution and emit an `adk_request_confirmation` event.
3.  **User Prompting**: The runner (`run_salesforce_agent.py`) intercepts the event, extracts the quote details, and prompts the user: `Do you approve this Quote creation? (y/n)`.
4.  **Resuming Execution**: The runner wraps the user's choice in a `FunctionResponse` payload and resumes execution.
    - If approved, the mock Salesforce MCP server creates the Quote record.
    - If rejected, the agent is informed of the rejection and continues accordingly.


---

## Setup and Run

### 1. Prerequisites
Make sure your environment has the correct dependencies installed:
```bash
pip install google-adk mcp
```

### 2. Configure Authentication

You can authenticate the agent in two ways:

#### Option A: Project Authentication / Vertex AI (Recommended)
This uses your Google Cloud Project credentials (via Application Default Credentials).
1. Authenticate your terminal session using gcloud:
   ```bash
   gcloud auth application-default login
   ```
2. Export the Vertex AI environment variables:
   ```bash
   export GOOGLE_GENAI_USE_VERTEXAI=true
   export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
   export GOOGLE_CLOUD_LOCATION="us-central1" # Or your preferred Vertex AI region
   ```

#### Option B: Google AI Studio (API Key)
If you prefer to use a standard Gemini API key:
```bash
export GEMINI_API_KEY="your-actual-gemini-api-key"
```


### 3. Run the Agent

You can test and run the agent in two ways:

#### Option A: Interactive CLI
Start the interactive CLI:
```bash
python3 run_salesforce_agent.py
```

#### Option B: ADK Web UI
We have created `agent.py` which acts as the entrypoint for the ADK CLI loaders.
To launch the browser-based developer interface:
```bash
adk web "ADK Salesforce MCP"
```
After the server starts, open your browser and navigate to `http://127.0.0.1:8000`. You will be able to converse with the agent, visually inspect its tool calling steps, and approve/reject Quote creations directly via UI widgets!


### Example Walkthrough
1.  Type: `Show opportunity opp_123`
    - The agent executes a SOQL query using `executeSoqlQuery` (e.g. `SELECT Id, Name, AccountId, Amount, StageName FROM Opportunity WHERE Id = 'opp_123'`) and displays the details.
2.  Type: `Create a quote for it`
    - The agent queries the Line Items associated with `opp_123` and then triggers `createRecord` with `apiName='SBQQ__Quote__c'`.
    - The console outputs the `🚨 HUMAN IN THE LOOP APPROVAL REQUIRED 🚨` banner and details of the quote to be created.
    - Prompt: `Do you approve this Quote creation? (type 'yes' or 'y' to confirm, anything else to reject)`
3.  Type `yes` or `y`.
    - The agent receives the approval, executes `createRecord` on the server, and returns the successful quote details.

---

## Connecting to the Real Salesforce Hosted MCP Server

Salesforce officially hosts production-ready MCP servers, meaning **you do not need to host or run any local MCP server bridge**.

For full data and CPQ Quote access, Salesforce provides the **`sobject-all`** hosted server.

### 1. Salesforce Setup
Before connecting the agent, you must configure the environment in your Salesforce organization:
1. Go to **Setup** -> search for **MCP Servers** -> activate the `SObject All` server.
2. Create an **External Client App (ECA)** in Salesforce Setup (using OAuth 2.0 with PKCE) and configure the Callback URL to match your client application redirect URL. Ensure the OAuth Scopes include `mcp_api` and `refresh_token`.
3. Complete the OAuth flow to obtain a Salesforce **Access Token** (Bearer token).

### 2. Configure Agent Toolset
In `salesforce_agent.py`, replace the `McpToolset` definition with the one connecting to the official Salesforce hosted server via Server-Sent Events (SSE):

```python
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

# Salesforce Hosted MCP Endpoint
# For sandboxes: https://api.salesforce.com/platform/mcp/v1/sandbox/platform/sobject-all
SALESFORCE_MCP_URL = "https://api.salesforce.com/platform/mcp/v1/platform/sobject-all"

# Input your retrieved OAuth access token
SALESFORCE_ACCESS_TOKEN = "YOUR_SALESFORCE_OAUTH_ACCESS_TOKEN"

salesforce_mcp_toolset = McpToolset(
    connection_params=SseConnectionParams(
        url=SALESFORCE_MCP_URL,
        headers={"Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}"}
    ),
    require_confirmation=confirm_quote_creation
)
```

