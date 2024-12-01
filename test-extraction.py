import json
from openai import OpenAI
import time

def assistant_request(file_path):
    client = OpenAI()

    print("Uploading file...")
    with open(file_path, "rb") as file:
        uploaded_file = client.files.create(
            file=file,
            purpose='assistants'
        )
    print(f"File uploaded successfully. File ID: {uploaded_file.id}")

    print("Retrieving assistant...")
    assistant = client.beta.assistants.retrieve("asst_dTGzcEDkc4gsweh3FaEidJ9l")
    print(f"Assistant retrieved successfully. Assistant ID: {assistant.id}")

    print("Creating thread...")
    thread = client.beta.threads.create()
    print(f"Thread created successfully. Thread ID: {thread.id}")

    print("Sending message to assistant...")
    thread_message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Extract all questions from the document and format them in JSON.",
        attachments=[{
            "file_id": uploaded_file.id,
            "tools": [{"type": "file_search"}]
        }]
    )
    print("Message sent successfully. Waiting for the assistant to process...")

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    while run.status not in ["completed", "failed"]:
        print(f"Current run status: {run.status}. Waiting...")
        time.sleep(2)
        run = client.beta.threads.runs.retrieve(run_id=run.id, thread_id=thread.id)

    if run.status == "completed":
        print("Assistant has completed processing.")
        print("Fetching the response...")
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        return messages.data

    raise RuntimeError("Assistant processing failed.")

def extract_questions_json(messages_data):
    for message in messages_data:
        if message["role"] == "assistant":
            for content in message["content"]:
                if "value" in content["text"]:
                    raw_json = content["text"]["value"]
                    parsed_data = json.loads(raw_json)
                    questions_json = {
                        "filename": parsed_data.get("filename"),
                        "questions": parsed_data.get("questions")
                    }
                    return questions_json

def save_json_to_file(data, output_file_path):
    with open(output_file_path, "w") as output_file:
        json.dump(data, output_file, indent=2)
    print(f"Formatted JSON saved to {output_file_path}")

def process_data(messages_data):
    message = messages_data[0]

    content_blocks = message.content

    for block in content_blocks:
        if hasattr(block, "text") and hasattr(block.text, "value"):
            json_string = block.text.value
            break
    else:
        raise ValueError("No JSON content found in the message.")

    parsed_data = json.loads(json_string)

    filename = parsed_data.get("filename", "No filename found")
    questions = parsed_data.get("questions", [])

    return {
        "filename": filename,
        "questions": questions
    }

def write_json(data, output_file="output.json"):
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Data has been written to {output_file}")



file_path = r"/Users/manavk/Documents/secureblox/ml/test-files/Blank RFI - Questionnaire - to be completed/RFI Sample #2.docx"
output_json_path = "output.json"

messages_data = assistant_request(file_path)
processed_data = process_data(messages_data)
write_json(processed_data, output_json_path)