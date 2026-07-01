import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.adk.tools.tool_context import ToolContext
from mcp import StdioServerParameters

def get_current_tool_name(tool_context: ToolContext) -> str:
    """Helper to retrieve the name of the tool currently being executed."""
    fc_id = tool_context.function_call_id
    if not fc_id or not tool_context.invocation_context or not tool_context.invocation_context.session:
        return ""
    
    # Walk session events to find the matching function call ID
    for event in tool_context.invocation_context.session.events:
        for fc in event.get_function_calls():
            if fc.id == fc_id:
                return fc.name
    return ""

def confirm_quote_creation(tool_context: ToolContext, **kwargs) -> bool:
    """Human-in-the-loop callback to approve Quote record creation in Salesforce.
    
    This function intercepts the 'createRecord' tool call when creating
    a Salesforce CPQ Quote (SBQQ__Quote__c) record.
    """
    tool_name = get_current_tool_name(tool_context)
    
    # Check if the tool is createRecord and it's creating a Salesforce CPQ Quote
    if tool_name == "createRecord" and kwargs.get("apiName") == "SBQQ__Quote__c":
        print("\n" + "="*60)
        print("🚨 HUMAN IN THE LOOP APPROVAL REQUIRED 🚨")
        print("="*60)
        print("The AI Agent wants to create a new Salesforce CPQ Quote (SBQQ__Quote__c):")
        
        fields = kwargs.get("fields", {})
        print(f"  Opportunity Reference (SBQQ__Opportunity2__c): {fields.get('SBQQ__Opportunity2__c')}")
        print(f"  Account reference (SBQQ__Account__c):          {fields.get('SBQQ__Account__c')}")
        print(f"  Status (SBQQ__Status__c):                      {fields.get('SBQQ__Status__c', 'Draft')}")
        print("="*60)
        return True # Triggers the human confirmation prompt
        
    return False # No confirmation needed for other tools/objects

# Path to the mock Salesforce Hosted MCP server
server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "salesforce_mcp_server.py"))

salesforce_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python3",
            args=[server_path]
        )
    ),
    require_confirmation=confirm_quote_creation
)

# Instantiate the Agent
salesforce_agent = Agent(
    name="salesforce_cpq_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a sales operations assistant specializing in Salesforce CPQ.\n"
        "You assist users by querying opportunities and creating CPQ Quote records.\n\n"
        
        "Guidelines:\n"
        "1. To inspect opportunities or query products, write and execute standard SOQL queries using `executeSoqlQuery` tool. "
        "For example, to find opportunity products, query from `OpportunityLineItem` associated with the opportunity ID.\n"
        "2. To get the field definitions of an object, use the `getObjectSchema` tool.\n"
        "3. To create a new CPQ Quote, use `createRecord` with `apiName='SBQQ__Quote__c'`.\n"
        "Always query the opportunity details first to locate the AccountId and details before creating a quote."
    ),
    tools=[salesforce_mcp_toolset]
)
