import os
import json
import asyncio
from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load the API key from the hidden .env file we created
load_dotenv()

async def main():
    print("Starting the Teczo AI Agent...")
    
    # 1. Define the folder we want the agent to have access to
    target_dir = os.path.abspath(os.path.join(os.getcwd(), "test_documents"))
    print(f"Connecting to MCP server and mapping local directory: {target_dir}")
    
    # Configure the MCP Filesystem Server (npx runs the Node.js package we need)
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", target_dir],
        env=None
    )

    # 2. Boot up the server and connect our client
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Fetch the tools the MCP server provides (like reading files and listing folders)
            tools = await session.list_tools()
            mcp_tools = [{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tools.tools]
            
            print(f"Success! Agent loaded {len(mcp_tools)} tools from the MCP toolbox.")
            
            # 3. Initialize our LLM (Claude)
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            # This is the system prompt dictating the agent's behavior
            system_prompt = f"""You are DocuNestAI, an intelligent document processing agent. Your task:
            1. Use your tools to browse the folder: {target_dir}
            2. Find the project report file (ignore decoys like meeting notes or random text).
            3. Read the contents of the correct target file.
            4. Extract this specific data: Project Name, Client Name, Date, Equipment List (as an array of strings), and Total Cost (as a pure number).
            5. Output ONLY a valid, raw JSON object (no markdown formatting, no introduction). The JSON must exactly match this schema:
               - source_file: (string) the name of the file processed
               - extracted_at: (string) current timestamp
               - metadata: (object) containing title, date, author (if available)
               - data: (object) containing the extracted project data
               - agent_notes: (string) a brief note about how you found the file
            """
            
            messages = [{"role": "user", "content": "Begin processing the documents folder now."}]
            print("Agent is thinking and exploring the folder...")
            
            # 4. The Main Control Loop
            while True:
                # Send the current state to Claude
                response = client.messages.create(
                    model="claude-sonnet-4-20250514", # Using the required Teczo model
                    max_tokens=1000,
                    system=system_prompt,
                    messages=messages,
                    tools=mcp_tools
                )
                
                # Check if Claude decided it needs to use a tool
                if response.stop_reason == "tool_use":
                    tool_use = next(block for block in response.content if block.type == "tool_use")
                    tool_name = tool_use.name
                    tool_args = tool_use.input
                    
                    print(f" -> Agent Action: Decided to use tool '{tool_name}' with arguments: {tool_args}")
                    
                    # Execute the tool and get the result
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    
                    # Update our message history with the tool's result so Claude can read it
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user", 
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result.content[0].text
                        }]
                    })
                
                # Check if Claude has finished the task and generated the final JSON
                # Check if Claude has finished the task and generated the final JSON
                elif response.stop_reason == "end_turn":
                    final_text = response.content[0].text.strip()
                    print("\nAgent finished processing. Generating output.json...")
                    
                    # Clean up the output to ignore conversational text and grab only the JSON
                    start_idx = final_text.find('{')
                    end_idx = final_text.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        final_text = final_text[start_idx:end_idx+1]
                    
                    try:
                        # Parse the text into actual JSON and save the file
                        parsed_data = json.loads(final_text)
                        with open("output.json", "w") as f:
                            json.dump(parsed_data, f, indent=4)
                        print("SUCCESS: output.json has been created in your folder!")
                    except Exception as e:
                        print("Failed to save JSON. Raw output from agent was:")
                        print(final_text)
                        
                    break

if __name__ == "__main__":
    # Start the asynchronous event loop
    asyncio.run(main())