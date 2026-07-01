import asyncio
import os
import sys
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.session import Session
from google.genai import types

# Import the agent
from salesforce_agent import salesforce_agent

# Special function name for confirmation in ADK
REQUEST_CONFIRMATION_FUNCTION_CALL_NAME = 'adk_request_confirmation'

def get_pending_confirmations(events):
    """Scan events for pending human-in-the-loop tool confirmations."""
    pending = []
    for event in events:
        lr_ids = getattr(event, 'long_running_tool_ids', None)
        if not lr_ids:
            continue
        content = getattr(event, 'content', None)
        if not content or not content.parts:
            continue
        for part in content.parts:
            fc = part.function_call
            if fc and fc.id in lr_ids:
                if fc.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME:
                    pending.append((fc.id, fc.name, fc.args or {}))
    return pending

async def main():
    # Setup standard logging to stderr
    # Check if either Gemini API key or Vertex AI project configurations are set
    has_studio_key = bool(os.environ.get("GEMINI_API_KEY"))
    has_vertex_conf = (
        os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
        and bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    )
    if not (has_studio_key or has_vertex_conf):
        print("⚠️ Warning: No authentication configuration detected.")
        print("Please configure one of the following:")
        print("  Option A (Vertex AI): Run 'gcloud auth application-default login' and export env vars:")
        print("     export GOOGLE_GENAI_USE_VERTEXAI=true")
        print("     export GOOGLE_CLOUD_PROJECT='your-project-id'")
        print("     export GOOGLE_CLOUD_LOCATION='us-central1'")
        print("  Option B (AI Studio): Export GEMINI_API_KEY env var:")
        print("     export GEMINI_API_KEY='your_api_key_here'\n")

    print("Initializing Salesforce CPQ Agent CLI...")
    session_service = InMemorySessionService()
    
    # Create a new session
    session_id = "salesforce-cpq-session-1"
    user_id = "sales_rep_user"
    session = Session(
        id=session_id,
        app_name="salesforce_cpq_app",
        user_id=user_id
    )
    await session_service.create_session(session)

    runner = Runner(
        agent=salesforce_agent,
        app_name="salesforce_cpq_app",
        session_service=session_service
    )

    print("\nAgent is ready! Ask a question or request an action.")
    print("Example prompts:")
    print("  - 'Show opportunity opp_123'")
    print("  - 'Create a CPQ quote for opportunity opp_123 using its suggested items'")
    print("  - 'exit'\n")

    next_message = None
    resume_invocation_id = None

    while True:
        if next_message is None:
            try:
                query = input("\n[user]: ")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
                
            if not query or not query.strip():
                continue
            if query.lower() == 'exit':
                print("Goodbye!")
                break
                
            next_message = types.Content(role='user', parts=[types.Part(text=query)])

        collected_events = []
        invocation_id = None

        # Execute agent turn
        try:
            events_generator = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=next_message,
                invocation_id=resume_invocation_id,
            )
            
            async for event in events_generator:
                collected_events.append(event)
                if getattr(event, 'invocation_id', None):
                    invocation_id = event.invocation_id
                
                # Print agent text response
                if event.content and event.content.parts:
                    text_parts = [part.text for part in event.content.parts if part.text]
                    if text_parts:
                        full_text = "".join(text_parts)
                        print(f"[{event.author}]: {full_text}")

                # Print function calls being made
                for fc in event.get_function_calls():
                    if fc.name != REQUEST_CONFIRMATION_FUNCTION_CALL_NAME:
                        print(f"⚙️ [Tool Call] {fc.name}({fc.args})")

                # Print function responses
                for fr in event.get_function_responses():
                    if fr.name != REQUEST_CONFIRMATION_FUNCTION_CALL_NAME:
                        # Truncate response output if too long
                        resp_str = str(fr.response)
                        if len(resp_str) > 200:
                            resp_str = resp_str[:200] + "..."
                        print(f"✅ [Tool Result] {fr.name} -> {resp_str}")

        except Exception as e:
            print(f"❌ Error during agent execution: {e}", file=sys.stderr)
            next_message = None
            resume_invocation_id = None
            continue

        next_message = None
        resume_invocation_id = None

        # Check if there are any pending human-in-the-loop confirmations
        pending_confirms = get_pending_confirmations(collected_events)
        if pending_confirms:
            parts = []
            for fc_id, fc_name, args in pending_confirms:
                # Prompt the user for approval
                print("\n👉 Do you approve this Quote creation? (type 'yes' or 'y' to confirm, anything else to reject)")
                user_decision = input("[approval]: ").strip().lower()
                
                confirmed = user_decision in ('y', 'yes')
                if confirmed:
                    print("✅ Quote creation approved. Sending confirmation back to the agent...")
                else:
                    print("❌ Quote creation rejected. Sending rejection back to the agent...")
                
                # Build the response to resume the turn
                parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=fc_id,
                            name=fc_name,
                            response={'confirmed': confirmed}
                        )
                    )
                )
            
            next_message = types.Content(role='user', parts=parts)
            resume_invocation_id = invocation_id

    await runner.close()

if __name__ == "__main__":
    asyncio.run(main())
