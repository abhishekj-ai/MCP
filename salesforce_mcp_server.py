import sys
import logging
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP

# Setup logging to stderr because stdout is used for MCP JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("salesforce_mcp_mock")

# Initialize FastMCP Server representing the Salesforce Hosted MCP (sobject-all)
mcp = FastMCP("Salesforce Hosted MCP (sobject-all)")

# Mock Database
OPPORTUNITIES = {
    "opp_123": {
        "Id": "opp_123",
        "Name": "Acme Corp Cloud Expansion",
        "AccountId": "cust_888",
        "StageName": "Proposal/Price Quote",
        "Amount": 55000.0,
    },
    "opp_456": {
        "Id": "opp_456",
        "Name": "Stark Industries Security Upgrade",
        "AccountId": "cust_999",
        "StageName": "Negotiation",
        "Amount": 120000.0,
    }
}

OPPORTUNITY_PRODUCTS = {
    "opp_123": [
        {"OpportunityId": "opp_123", "Product2Id": "prod_saas_license", "Quantity": 100, "UnitPrice": 450.0},
        {"OpportunityId": "opp_123", "Product2Id": "prod_premium_support", "Quantity": 1, "UnitPrice": 10000.0}
    ],
    "opp_456": [
        {"OpportunityId": "opp_456", "Product2Id": "prod_saas_license", "Quantity": 200, "Product2": {"Name": "SaaS Platform User License (Annual)"}, "UnitPrice": 400.0},
        {"OpportunityId": "opp_456", "Product2Id": "prod_premium_support", "Quantity": 1, "UnitPrice": 15000.0},
        {"OpportunityId": "opp_456", "Product2Id": "prod_implementation_services", "Quantity": 50, "UnitPrice": 250.0}
    ]
}

PRODUCTS = [
    {"Id": "prod_saas_license", "Name": "SaaS Platform User License (Annual)", "SBQQ__BillingFrequency__c": "Annual"},
    {"Id": "prod_premium_support", "Name": "Premium Support Plan (Annual)", "SBQQ__BillingFrequency__c": "Annual"},
    {"Id": "prod_implementation_services", "Name": "Professional Services Implementation (Hourly)", "SBQQ__BillingFrequency__c": "One-Time"}
]

CREATED_RECORDS = []

@mcp.tool()
async def executeSoqlQuery(query: str) -> Dict[str, Any]:
    """Execute a SOQL query to retrieve Salesforce records.
    
    Args:
        query: The standard SOQL query string (e.g. SELECT Id, Name FROM Opportunity WHERE Id = 'opp_123').
    """
    logger.info(f"executeSoqlQuery called: {query}")
    query_upper = query.upper()
    
    # 1. Parse simple Opportunity queries
    if "FROM OPPORTUNITY" in query_upper:
        for opp_id, opp_data in OPPORTUNITIES.items():
            if f"'{opp_id}'" in query or f'"{opp_id}"' in query:
                return {"done": True, "totalSize": 1, "records": [opp_data]}
        # If no specific ID, return all mock opportunities
        return {"done": True, "totalSize": len(OPPORTUNITIES), "records": list(OPPORTUNITIES.values())}
        
    # 2. Parse Opportunity Line Item (Products) queries
    if "FROM OPPORTUNITYLINEITEM" in query_upper:
        for opp_id, products in OPPORTUNITY_PRODUCTS.items():
            if f"'{opp_id}'" in query or f'"{opp_id}"' in query:
                return {"done": True, "totalSize": len(products), "records": products}
                
    # 3. Parse Product queries
    if "FROM PRODUCT2" in query_upper:
        return {"done": True, "totalSize": len(PRODUCTS), "records": PRODUCTS}
        
    return {"done": True, "totalSize": 0, "records": [], "message": "No matching mock records found for the query."}

@mcp.tool()
async def getObjectSchema(apiName: str) -> Dict[str, Any]:
    """Retrieve the schema metadata for a specific Salesforce SObject (optimized for LLMs).
    
    Args:
        apiName: The API Name of the Salesforce object (e.g. Opportunity, SBQQ__Quote__c).
    """
    logger.info(f"getObjectSchema called for: {apiName}")
    if apiName == "Opportunity":
        return {
            "apiName": "Opportunity",
            "fields": [
                {"name": "Id", "type": "id", "label": "Opportunity ID", "createable": False, "updateable": False},
                {"name": "Name", "type": "string", "label": "Name", "createable": True, "updateable": True},
                {"name": "AccountId", "type": "reference", "label": "Account ID", "createable": True, "updateable": True},
                {"name": "StageName", "type": "picklist", "label": "Stage", "createable": True, "updateable": True},
                {"name": "Amount", "type": "currency", "label": "Amount", "createable": True, "updateable": True}
            ]
        }
    elif apiName == "SBQQ__Quote__c":
        return {
            "apiName": "SBQQ__Quote__c",
            "fields": [
                {"name": "Id", "type": "id", "label": "Quote ID", "createable": False, "updateable": False},
                {"name": "SBQQ__Opportunity2__c", "type": "reference", "label": "Opportunity", "createable": True, "updateable": False},
                {"name": "SBQQ__Account__c", "type": "reference", "label": "Account", "createable": True, "updateable": False},
                {"name": "SBQQ__Status__c", "type": "picklist", "label": "Status", "createable": True, "updateable": True},
                {"name": "SBQQ__LineItemCount__c", "type": "integer", "label": "Line Item Count", "createable": False, "updateable": False}
            ]
        }
    return {"error": f"Schema for {apiName} not defined in mock."}

@mcp.tool()
async def createRecord(apiName: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new record for the specified Salesforce SObject.
    
    Args:
        apiName: The API Name of the Salesforce object to create (e.g. SBQQ__Quote__c).
        fields: A map of field API names to values.
    """
    logger.info(f"createRecord called for {apiName} with fields {fields}")
    
    record_id = f"rec_{apiName[:3].lower()}_{len(CREATED_RECORDS) + 101}"
    new_record = {
        "Id": record_id,
        "attributes": {"type": apiName},
        **fields
    }
    
    CREATED_RECORDS.append(new_record)
    return new_record

if __name__ == "__main__":
    mcp.run()
