from langchain_core.messages import HumanMessage
from graph.workflow import hotel_booking_graph
from state.agent_state import AgentState  # not used directly but keeping for reference


def create_initial_state():
    return {
        "messages": [],
        "user_intent": "",
        "search_params": {},
        "search_results": [],
        "selected_hotel": {},
        "availability_results": {},
        "hotel_details": {},
        "booking_context": {},
        "error_context": "",
    }

def run_agent(user_message, state):
    """run a message through the graph, returns (response_text, updated_state)"""
    state["messages"].append(HumanMessage(content=user_message))
    result = hotel_booking_graph.invoke(state)

    # grab the last ai message from the result
    reply = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and not isinstance(msg, HumanMessage):
            reply = msg.content
            break

    return reply, result
