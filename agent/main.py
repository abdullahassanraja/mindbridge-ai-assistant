# main.py
# Interactive terminal CLI for MindBridge Wellness AI intake assistant.

import sys
from state import create_initial_state, AgentState
from graph import app_graph


def run_cli():
    print("=" * 70)
    print("🌿 MindBridge Wellness — AI Intake Assistant CLI")
    print("=" * 70)
    print("Type your message and press Enter to chat.")
    print("Type 'reset' to start a new conversation.")
    print("Type 'exit' or 'quit' to end the session.\n")

    # Initial state
    state: AgentState = create_initial_state()

    # Initial greeting from assistant
    welcome_text = (
        "Hello and welcome to MindBridge Wellness. I'm the practice's AI intake assistant. "
        "I can answer questions about our counseling services, help you find a therapist whose "
        "specialties match what you're looking for, or connect you with our clinical team. "
        "How can I help you today?"
    )
    state["messages"].append({"role": "assistant", "content": welcome_text})
    print(f"Assistant: {welcome_text}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Thank you for visiting MindBridge Wellness.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("\nSession ended. Take care!")
            break

        if user_input.lower() == "reset":
            state = create_initial_state()
            print("\n--- [Conversation Reset] ---\n")
            print(f"Assistant: {welcome_text}\n")
            state["messages"].append({"role": "assistant", "content": welcome_text})
            continue

        # Append user message
        state["messages"].append({"role": "user", "content": user_input})

        # Process message through LangGraph
        try:
            state = app_graph.invoke(state)
            latest_assistant = state["messages"][-1]["content"]
            print(f"\nAssistant: {latest_assistant}\n")
        except Exception as err:
            print(f"\n[Error processing message]: {err}\n")


if __name__ == "__main__":
    # Ensure UTF-8 output in Windows terminal
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_cli()
