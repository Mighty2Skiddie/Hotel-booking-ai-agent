import chainlit as cl
from agent.controller import create_initial_state, run_agent

WELCOME = (
    "👋 **Welcome to HotelBot!** I'm your AI hotel booking assistant.\n\n"
    "I can help you:\n"
    "- 🔍 **Search hotels** in any city\n"
    "- 🛏️ **Check room availability** and pricing\n"
    "- 🏨 **Get hotel details** — amenities, policies, landmarks\n"
    "- ❓ **Answer questions** about hotels you're interested in\n\n"
    "Try something like: *\"Find me hotels in Jaipur from Dec 10 to Dec 13 for 2 guests\"*"
)

@cl.on_chat_start
async def start():
    state = create_initial_state()
    cl.user_session.set("state", state)
    await cl.Message(content=WELCOME).send()


@cl.on_message
async def handle(message: cl.Message):
    state = cl.user_session.get("state")

    msg = cl.Message(content="")
    await msg.send()

    try:
        resp, new_state = run_agent(message.content, state)
        cl.user_session.set("state", new_state)
        msg.content = resp
        await msg.update()
    except Exception as e:
        msg.content = f"Something went wrong, please try again.\n\n*Error: {e}*"
        await msg.update()
