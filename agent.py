import os
import json
import asyncio
from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load the API key
load_dotenv()

async def main():
    print("Starting the Teczo AI Agent...")
    
    # Define the target directory
    target_dir = os.path.abspath(os.path.join(os.getcwd(), "test_documents"))
    print(f"Connecting to MCP server and mapping local directory: {target_dir}")
    
    # Configure MCP
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", target_dir],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Fetch tools
            tools = await session.list_tools()
            mcp_tools = [{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tools.tools]
            
            print(f"Success! Agent loaded {len(mcp_tools)} tools from the MCP toolbox.")
            
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            system_prompt = f"""You are DocuNestAI, an intelligent document processing agent. Your task:
            1. Use your tools to browse the folder: {target_dir}
            2. Find the project report file (ignore decoys).
            3. Read the contents of the correct target file.
            4. Extract this specific data: Project Name, Client Name, Date, Equipment List (as an array of strings), and Total Cost (as a pure number).
            5. Output ONLY a valid, raw JSON object. The JSON must exactly match this schema:
               - source_file: (string)
               - extracted_at: (string) current timestamp
               - metadata: (object) containing title, date, author
               - data: (object) containing the extracted project data
               - agent_notes: (string) your thought process
            """
            
            messages = [{"role": "user", "content": "Begin processing the documents folder now."}]
            print("Agent is thinking and exploring the folder...")
            
            while True:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514", # Using the required Teczo model
                    max_tokens=1000,
                    system=system_prompt,
                    messages=messages,
                    tools=mcp_tools
                )
                
                if response.stop_reason == "tool_use":
                    # SAFTEY NET: Safely extract the tool block to prevent StopIteration crashes
                    tool_use = next((block for block in response.content if block.type == "tool_use"), None)
                    
                    if not tool_use:
                        # If Claude glitches, silently tell it to try again
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({"role": "user", "content": "You did not include the tool block. Please try again."})
                        continue

                    tool_name = tool_use.name
                    tool_args = tool_use.input
                    
                    print(f" -> Agent Action: Decided to use tool '{tool_name}' with arguments: {tool_args}")
                    
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user", 
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result.content[0].text
                        }]
                    })
                
                elif response.stop_reason == "end_turn":
                    final_text = response.content[0].text.strip()
                    print("\nAgent finished processing. Generating output.json...")
                    
                    # Clean the JSON output
                    start_idx = final_text.find('{')
                    end_idx = final_text.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        final_text = final_text[start_idx:end_idx+1]
                    
                    try:
                        parsed_data = json.loads(final_text)
                        with open("output.json", "w") as f:
                            json.dump(parsed_data, f, indent=4)
                        print("SUCCESS: output.json has been created in your folder!")
                    except Exception as e:
                        print("Failed to save JSON. Raw output from agent was:")
                        print(final_text)
                        
                    break

if __name__ == "__main__":
    asyncio.run(main())