import os
import json
import time
from openai import OpenAI


class AssistantHandler:
    def __init__(self, instructions_file, name, model="gpt-4o", tools=None, knowledge_document=None):
        """
        Initialize the AssistantHandler. Create or load an assistant using instructions from a file.
        """
        if not knowledge_document:
            raise ValueError("A knowledge document path must be provided.")
        self.client = OpenAI()
        self.assistant_id_file = "assistant_id.txt"
        self.assistant_id = self._load_or_create_assistant(
            instructions_file, name, model, tools, knowledge_document
        )

    def _load_or_create_assistant(self, instructions_file, name, model, tools, knowledge_document):
        if os.path.exists(self.assistant_id_file):
            print("Loading existing assistant ID...")
            with open(self.assistant_id_file, "r") as file:
                assistant_id = file.read().strip()
            print(f"Using existing assistant with ID: {assistant_id}")
            return assistant_id

        print("Creating a new assistant...")
        with open(instructions_file, "r") as file:
            instructions = file.read()

        vector_store_id, file_id = self.create_vector_store(knowledge_document, "Knowledge Vector Store")

        assistant = self.client.beta.assistants.create(
            instructions=instructions,
            name=name,
            model=model,
            tools=[{"type": "file_search",}],
            tool_resources=[vector_store_id]

        )

        assistant_id = assistant.id
        print(f"New assistant created...\n")
        print(assistant)

        with open(self.assistant_id_file, "w") as file:
            file.write(assistant_id)
        return assistant_id



    def create_vector_store(self, file_path, vector_store_name):
        """
        Create a vector store using a file.
        """
        print("Creating vector store...")
        vector_store = self.client.beta.vector_stores.create(
            name=vector_store_name
        )
        print(f"Vector store created with ID: {vector_store.id}")
        

        print("Uploading file...")
        with open(file_path, "rb") as file:
            uploaded_file = self.client.files.create(file=file, purpose="assistants")
        print(f"File uploaded successfully. File ID: {uploaded_file.id}")

        print("Creating vector store file...")
        vector_store_file = self.client.beta.vector_stores.files.create(
            vector_store_id=vector_store.id,
            file_id=uploaded_file.id
        )
        print("Vector store file added succesfully.")
        return (vector_store.id, uploaded_file.id)

    def assistant_request(self, file_path):
        """
        Interact with the assistant by creating a thread and sending a request.
        """
        print("Uploading file...")
        with open(file_path, "rb") as file:
            uploaded_file = self.client.files.create(file=file, purpose="assistants")
        print(f"File uploaded successfully. File ID: {uploaded_file.id}")

        print("Creating thread...")
        thread = self.client.beta.threads.create()
        print(f"Thread created successfully. Thread ID: {thread.id}")

        print("Sending message to assistant...")
        thread_message = self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="Use the uploaded file to answer the questions in the input document.",
            attachments=[{"file_id": uploaded_file.id, "tools": [{"type": "file_search"}]}],
        )
        print("Message sent successfully. Waiting for the assistant to process...")

        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=self.assistant_id
        )

        while run.status not in ["completed", "failed"]:
            print(f"Current run status: {run.status}. Waiting...")
            time.sleep(2)
            run = self.client.beta.threads.runs.retrieve(run_id=run.id, thread_id=thread.id)

        if run.status == "completed":
            print("Assistant has completed processing.")
            print("Fetching the response...")
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            return messages.data

        raise RuntimeError("Assistant processing failed.")

    @staticmethod
    def extract_questions_json(messages_data):
        """
        Extract questions from assistant's response in JSON format.
        """
        # Ensure there are messages in the response
        if not messages_data or len(messages_data) == 0:
            raise ValueError("No messages found in the response.")

        # Inspect the first message (expected to contain assistant's reply)
        message = messages_data[0]
        print(messages_data)
        content_blocks = getattr(message, "content", [])

        # Traverse content blocks to find JSON
        for block in content_blocks:
            if hasattr(block, "text") and hasattr(block.text, "value"):
                json_string = block.text.value.strip()
                if json_string.startswith("```json") and json_string.endswith("```"):
                    # Extract JSON content between the backticks
                    json_string = json_string[7:-3].strip()  # Remove "```json" and trailing "```"
                    try:
                        parsed_data = json.loads(json_string)
                        filename = parsed_data.get("filename", "No filename found")
                        questions = parsed_data.get("questions", [])
                        return {
                            "filename": filename,
                            "questions": questions
                        }
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Failed to parse JSON: {e}")
        else:
            raise ValueError("No JSON content found in the message.")

    @staticmethod
    def save_json_to_file(data, output_file_path="answers.json"):
        """
        Save extracted data to a JSON file.
        """
        with open(output_file_path, "w") as output_file:
            json.dump(data, output_file, indent=2)
        print(f"Formatted JSON saved to {output_file_path}")

    def process_file(self, file_path, output_json_path):
        """
        Full process: file upload, assistant request, and saving JSON output.
        """
        messages_data = self.assistant_request(file_path)
        processed_data = self.extract_questions_json(messages_data)
        self.save_json_to_file(processed_data, output_json_path)


# Example usage
if __name__ == "__main__":
    instructions_file = "instructions.txt"
    knowledge_document = r"/Users/manavk/Documents/secureblox/ml/k1.pptx"
    file_path = r"/Users/manavk/Documents/secureblox/ml/output.json"
    output_json_path = "answers.json"

    assistant_handler = AssistantHandler(
        instructions_file=instructions_file,
        name="Question Extractor",
        knowledge_document=knowledge_document
    )



    # Process the file and save questions to JSON
    assistant_handler.process_file(file_path, output_json_path)
