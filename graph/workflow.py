import json
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from state.agent_state import AgentState
from tools.hotel_tools import search_hotels, check_availability, get_hotel_details

load_dotenv()

# lazy init so we don't blow up on import without a key
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    return _llm


INTENT_PROMPT = """You are an intent classifier for a hotel booking assistant.

Analyze the user's latest message in the context of the conversation history.
You must return a JSON object (no markdown fencing) with these fields:

{{
  "intent": "<one of: search_hotels, check_availability, get_hotel_details, general_query, clarification_needed>",
  "params": {{
    "city": "<city name or null>",
    "checkin": "<YYYY-MM-DD or null>",
    "checkout": "<YYYY-MM-DD or null>",
    "guests": <integer or null>,
    "hotel_name": "<hotel name mentioned or null>",
    "hotel_id": "<hotel_id if identifiable from context or null>"
  }},
  "reasoning": "<one sentence explaining your classification>"
}}

Rules:
1. If the user asks to find/search/look for hotels → "search_hotels"
2. If the user asks about rooms, availability, pricing, or cost → "check_availability"
3. If the user asks about amenities, policies, location, details, cancellation, check-in/out times, landmarks → "get_hotel_details"
4. If the query can be answered from existing conversation context without any tool → "general_query"
5. If required info is missing (e.g., no city for search, no hotel selected for details) → "clarification_needed"
6. For "search_hotels", city is REQUIRED. If dates are missing, still classify as search_hotels but set dates to null.
7. If user mentions a hotel name, try to map it to a hotel_id from the search results in context.
8. If the user asks to compare hotels, use "get_hotel_details" intent.
9. Current date: {current_date}. If user says "next weekend", "tomorrow", etc., compute the actual dates.
"""

RESPONSE_PROMPT = """You are a friendly, knowledgeable hotel booking assistant. Your name is HotelBot.

Generate a helpful, natural response based on the conversation and available data.

Guidelines:
- Be warm, conversational, and concise
- Present hotel lists in a clear, scannable format with emojis for visual appeal
- For pricing, always show per-night AND total costs
- When showing availability, highlight room types clearly
- For hotel details, weave amenities into natural prose — don't just list them
- If there was an error, explain it kindly and suggest alternatives
- If you have data from previous turns that answers the question, use it directly
- Don't mention technical details like cache, API, tools, or state objects
- End responses with a helpful follow-up suggestion when appropriate
- Use ₹ symbol for Indian Rupees
"""


# ---- node functions ----

def detect_intent(state: AgentState) -> dict:
    msgs = state.get("messages", [])
    if not msgs:
        return {"user_intent": "clarification_needed", "error_context": "No message received."}

    today = datetime.now().strftime("%Y-%m-%d")
    sys_msg = INTENT_PROMPT.format(current_date=today)

    # shove existing state into the prompt so the llm knows what we already have
    parts = []
    search_res = state.get("search_results", [])
    if search_res:
        parts.append(f"Current search results in memory: {json.dumps(search_res, indent=2)}")

    sel = state.get("selected_hotel", {})
    if sel:
        parts.append(f"Currently selected hotel: {json.dumps(sel)}")

    params = state.get("search_params", {})
    if params:
        parts.append(f"Current search parameters: {json.dumps(params)}")

    details = state.get("hotel_details", {})
    if details:
        parts.append(f"Hotel details already fetched: {json.dumps(details)}")

    avail = state.get("availability_results", {})
    if avail:
        parts.append(f"Availability data already fetched: {json.dumps(avail)}")

    if parts:
        sys_msg += "\n\nCurrent session context:\n" + "\n".join(parts)

    llm_msgs = [SystemMessage(content=sys_msg)]
    # only last 10 messages, don't wanna blow the context window
    for m in msgs[-10:]:
        if isinstance(m, HumanMessage):
            llm_msgs.append(HumanMessage(content=m.content))
        elif isinstance(m, AIMessage):
            llm_msgs.append(AIMessage(content=m.content))

    resp = get_llm().invoke(llm_msgs)

    try:
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        parsed = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        return {"user_intent": "general_query", "error_context": ""}

    intent = parsed.get("intent", "general_query")
    p = parsed.get("params", {})

    updates = {"user_intent": intent, "error_context": ""}

    # merge new params with existing, keep old ones if not overridden
    existing = state.get("search_params", {}) or {}
    new_params = {}
    for k in ["city", "checkin", "checkout", "guests"]:
        val = p.get(k)
        if val is not None:
            new_params[k] = val
        elif k in existing:
            new_params[k] = existing[k]

    if new_params:
        # if city or dates changed, clear old results
        changed = (
            new_params.get("checkin") != existing.get("checkin") or
            new_params.get("checkout") != existing.get("checkout") or
            new_params.get("city", "").lower() != existing.get("city", "").lower()
        )
        if changed and existing:
            updates["search_results"] = []
            updates["availability_results"] = {}
            updates["selected_hotel"] = {}
        updates["search_params"] = new_params

    # figure out which hotel user is talking about
    hid = p.get("hotel_id")
    hname = p.get("hotel_name")
    if hid:
        updates["selected_hotel"] = {"hotel_id": hid, "name": hname or ""}
    elif hname and search_res:
        for h in search_res:
            if hname.lower() in h.get("name", "").lower():
                updates["selected_hotel"] = {"hotel_id": h["hotel_id"], "name": h["name"]}
                break

    return updates


def search_node(state: AgentState) -> dict:
    p = state.get("search_params", {})
    city = p.get("city", "")
    checkin = p.get("checkin", "")
    checkout = p.get("checkout", "")
    guests = p.get("guests", 2)

    if not city:
        return {"error_context": "I need to know which city you'd like to search in. Could you tell me the city?"}
    if not checkin or not checkout:
        return {"error_context": "I'd love to help you search! Could you share your check-in and check-out dates?"}

    try:
        res = search_hotels(city, checkin, checkout, guests)
        hotels = res.get("hotels", [])
        if not hotels:
            return {
                "search_results": [],
                "error_context": f"No hotels found in {city} for those dates. Try a different city or adjust your dates.",
            }
        return {"search_results": hotels, "error_context": ""}
    except Exception as e:
        return {"error_context": f"Search failed: {str(e)}"}


def availability_node(state: AgentState) -> dict:
    sel = state.get("selected_hotel", {})
    hid = sel.get("hotel_id", "")
    p = state.get("search_params", {})
    checkin = p.get("checkin", "")
    checkout = p.get("checkout", "")

    if not hid:
        return {"error_context": "Which hotel would you like to check availability for? Please select one from the search results."}
    if not checkin or not checkout:
        return {"error_context": "I need your check-in and check-out dates to check availability."}

    res = check_availability(hid, checkin, checkout)

    if res.get("error"):
        return {"error_context": res["error"]}

    rooms = res.get("rooms", [])
    all_booked = all(r.get("available_rooms", 0) == 0 for r in rooms)
    if all_booked:
        return {
            "availability_results": res,
            "error_context": f"{sel.get('name', 'This hotel')} is fully booked for your dates. Would you like to check another hotel?",
        }

    return {"availability_results": res, "error_context": ""}


def details_node(state: AgentState) -> dict:
    sel = state.get("selected_hotel", {})
    hid = sel.get("hotel_id", "")

    if not hid or hid == "":
        return {"error_context": "Which hotel are you asking about? Please mention a hotel name from the search results."}

    res = get_hotel_details(hid)
    if res.get("error"):
        return {"error_context": res["error"]}

    data = res
    return {"hotel_details": data, "error_context": ""}


def respond(state: AgentState) -> dict:
    """takes all the state and generates a response via llm"""
    msgs = state.get("messages", [])
    intent = state.get("user_intent", "general_query")
    err = state.get("error_context", "")

    parts = []
    if err:
        parts.append(f"Error/Issue: {err}")

    search_res = state.get("search_results", [])
    if search_res and intent in ("search_hotels", "general_query"):
        parts.append(f"Search Results:\n{json.dumps(search_res, indent=2)}")

    sel = state.get("selected_hotel", {})
    if sel:
        parts.append(f"Selected Hotel: {json.dumps(sel)}")

    params = state.get("search_params", {})
    if params:
        parts.append(f"Search Parameters: {json.dumps(params)}")

    avail = state.get("availability_results", {})
    if avail and intent in ("check_availability", "general_query"):
        parts.append(f"Room Availability:\n{json.dumps(avail, indent=2)}")

    details = state.get("hotel_details", {})
    if details and intent in ("get_hotel_details", "general_query"):
        parts.append(f"Hotel Details:\n{json.dumps(details, indent=2)}")

    # for general queries, dump everything we have so the llm can reference it
    if intent == "general_query":
        if avail and "Room Availability" not in str(parts):
            parts.append(f"Room Availability:\n{json.dumps(avail, indent=2)}")
        if details and "Hotel Details" not in str(parts):
            parts.append(f"Hotel Details:\n{json.dumps(details, indent=2)}")
        if search_res and "Search Results" not in str(parts):
            parts.append(f"Search Results:\n{json.dumps(search_res, indent=2)}")

    ctx = "\n\n".join(parts) if parts else "No data available yet."
    sys_content = RESPONSE_PROMPT + f"\n\nAvailable Data:\n{ctx}"

    llm_msgs = [SystemMessage(content=sys_content)]
    for m in msgs[-10:]:
        if isinstance(m, HumanMessage):
            llm_msgs.append(HumanMessage(content=m.content))
        elif isinstance(m, AIMessage):
            llm_msgs.append(AIMessage(content=m.content))

    resp = get_llm().invoke(llm_msgs)
    return {"messages": [AIMessage(content=resp.content)]}


# ---- routing ----

def route(state: AgentState) -> str:
    # returns name of next node — has to match exactly or langgraph throws
    intent = state.get("user_intent", "general_query")
    err = state.get("error_context", "")

    if err:
        return "respond"

    if intent == "search_hotels":
        return "search"
    elif intent == "check_availability":
        return "availability"
    elif intent == "get_hotel_details":
        return "details"
    elif intent == "clarification_needed":
        return "respond"
    else:
        return "respond"


# ---- graph construction ----

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("detect_intent", detect_intent)
    g.add_node("search", search_node)
    g.add_node("availability", availability_node)
    g.add_node("details", details_node)
    g.add_node("respond", respond)

    g.set_entry_point("detect_intent")

    g.add_conditional_edges(
        "detect_intent",
        route,
        {
            "search": "search",
            "availability": "availability",
            "details": "details",
            "respond": "respond",
        },
    )

    # all tool nodes feed into respond
    g.add_edge("search", "respond")
    g.add_edge("availability", "respond")
    g.add_edge("details", "respond")

    # not sure if we need this edge explicitly, but removing it broke things
    g.add_edge("respond", END)

    return g.compile()


hotel_booking_graph = build_graph()
