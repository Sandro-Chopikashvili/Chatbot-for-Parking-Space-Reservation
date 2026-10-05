# Main entry point for the CityPark assistant:
# - Build the LangGraph workflow and create a unique conversation thread.
# - Read user messages in a loop and send them to the graph for processing.
# - Display the assistant's response or a friendly error message.
# - Exit when the user types "exit" or "quit".

import uuid

from dotenv import load_dotenv

# Load environment variables from the .env file.
load_dotenv()
# Import the function that builds the CityPark LangGraph workflow.
from src.graph import build_graph 

# Run the CityPark assistant in an interactive terminal loop.
def main():
    # Build the conversation graph.
    graph = build_graph()
    # Create a unique ID to keep this conversation's state separate.
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    print("CityPark assistant. Type 'exit' to quit.")

    # Continuously read and process user messages.
    while True:
        text = input("You: ").strip()
        # Stop the program when the user wants to exit.
        if text.lower() in {"exit", "quit"}:
            break
        # Ignore empty messages.
        if not text:
            continue
        try:
            # Send the user's message to the graph and get the updated state.
            out = graph.invoke({"messages": [("user", text)]}, cfg)
            print("Bot:", out["messages"][-1].content, "\n")
        except Exception as e:
            # Show an error without crashing the application.
            print(f"Bot: Sorry, something went wrong ({type(e).__name__}: {e})\n")


if __name__ == "__main__":
    main()