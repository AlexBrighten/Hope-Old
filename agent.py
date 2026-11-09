import gradio as gr

from mcp_agent import NAME, MCPAgent

agent = MCPAgent()
print("MCP tools:", agent.tool_names() if agent.session else agent.error)


def respond(message, history):
    return agent.ask(message)


demo = gr.ChatInterface(fn=respond, title=NAME)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
