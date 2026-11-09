from mcp.server.fastmcp import FastMCP

import tools

mcp = FastMCP("agent-tools")
for fn in tools.ALL:
    mcp.tool()(fn)

if __name__ == "__main__":
    mcp.run()
