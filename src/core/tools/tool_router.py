import json
import discord

from .time import get_datetime, get_datetime_config
from .user import get_user_info, get_user_info_config
from .reminder import set_reminder, set_reminder_config

toolConfigurations = [get_datetime_config, get_user_info_config, set_reminder_config]


async def route_tool_calls(bot: discord.client, message: discord.message, tool_calls: list) -> str:
    """
    Routes a list of tool calls (e.g., from an LLM response) to the appropriate
    Python function and executes it.

    Args:
        tool_calls: A list of dictionaries, where each dict represents a tool call.
                     Expected structure: [{"name": "get_datetime", "arguments": {"timezone": "America/Los_Angeles"}}]

    Returns:
        A JSON string containing the results of all executed tools.
    """
    results = []
    for call in tool_calls:
        tool_name = call['function']['name']
        args = call['function']['arguments']

        print(f"Toolcall: {call}")

        if not tool_name:
            results.append({"error": "Tool name missing."})
            continue

        try:

            # Simple dispatch mechanism based on the tool name
            if tool_name == "get_datetime":
                timezone = args.get("timezone")
                if timezone:
                    result = get_datetime(timezone)
                    results.append({"role": "tool", "name": tool_name, "content": result})
                else:
                    results.append({"role": "tool", "name": tool_name, "content": "ERROR: Missing 'timezone' argument for get_datetime."})

            elif tool_name == "get_user_info":
                user_id = args.get("user_id")
                if user_id:
                    result = await get_user_info(bot=bot, message=message, user_id=user_id)
                    results.append({"role": "tool", "name": tool_name, "content": result})
                else:
                    results.append({"role": "tool", "name": tool_name, "content": "ERROR: Missing 'user_id' argument for get_user_info."})

            elif tool_name == "set_reminder":
                time = args.get("time")
                content = args.get("content")
                if time and content:
                    result = await set_reminder(bot=bot, message=message, time=time, content=content)
                    results.append({"role": "tool", "name": tool_name, "content": result})
                elif time:
                    results.append({"role": "tool", "name": tool_name, "content": "ERROR: Missing 'content' argument for set_reminder."})
                elif content:
                    results.append({"role": "tool", "name": tool_name, "content": "ERROR: Missing 'time' argument for set_reminder."})
                else:
                    results.append({"role": "tool", "name": tool_name, "content": "ERROR: Missing 'time' and 'content' arguments for set_reminder."})

            else:
                results.append({"role": "tool", "name": tool_name, "content": f"ERROR: Unknown tool: {tool_name}"})

        except Exception as e:
            results.append({"error": f"Execution failed for {tool_name}: {str(e)}"})

    return results