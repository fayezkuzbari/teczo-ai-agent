# Teczo AI Agent Assessment

## Setup Instructions
1. Ensure Python 3.x and Node.js are installed on your system.
2. Clone this repository to your local machine.
3. Install the required Python libraries by running: `pip install mcp anthropic python-dotenv`
4. Create a `.env` file in the root directory and add your Anthropic API key: `ANTHROPIC_API_KEY=your_key_here`
5. Run the agent using the command: `python agent.py`

## Design Decisions & Architecture
For this assessment, I designed a terminal-based AI agent using Python and the Anthropic Claude API, integrated with the official MCP Filesystem Server. I chose to use the pre-built `@modelcontextprotocol/server-filesystem` to handle local file operations securely and reliably, which allowed me to focus the architecture on the agent's core decision-making logic. The agent is instructed via its system prompt on the required JSON schema and the specific data fields to extract, but its navigation behavior is entirely autonomous. It dynamically lists the directory contents, reads file names, and decides on its own which file to read while ignoring decoys—there are absolutely no hardcoded filenames in the script. 

## Limitations
One limitation of this current prototype is that it relies on standard text parsing. If the target document were a complex PDF or contained image-based tables, a dedicated document parsing tool or OCR library would need to be added to the MCP server toolbox. Additionally, while the agent handles basic tool execution, a more robust production version would implement explicit retry mechanisms and error handling in the Python control loop for unexpected API timeouts or malformed JSON generation. Overall, this architecture successfully demonstrates a flexible, MCP-powered intelligence capable of navigating local environments to extract structured data.