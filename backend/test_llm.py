import json
from app.llm import chat, llm_available, get_model

print("Model:", get_model(), "| key configured:", llm_available())

# Test 1: plain reply
msg = chat([{"role": "user", "content": "Reply with exactly the word: READY"}], max_tokens=300)
print("Test 1 reply:", msg.content)

# Test 2: does the model actually call a tool?
tools = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a source file from the repository.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}]
msg = chat(
    [{"role": "user", "content": "Use your tool to read the file calculator.py"}],
    tools=tools,
)
if msg.tool_calls:
    call = msg.tool_calls[0]
    print("Test 2 tool call:", call.function.name, json.loads(call.function.arguments))
else:
    print("Test 2 FAILED: no tool call. Model said:", msg.content)
