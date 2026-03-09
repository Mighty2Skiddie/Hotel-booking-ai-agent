from typing import Annotated
from langgraph.graph.message import add_messages


class AgentState(dict):
    """state obj that gets passed through every node in the graph"""
    messages: Annotated[list, add_messages]
    user_intent: str
    search_params: dict
    search_results: list
    selected_hotel: dict
    availability_results: dict
    hotel_details: dict
    booking_context: dict
    error_context: str
