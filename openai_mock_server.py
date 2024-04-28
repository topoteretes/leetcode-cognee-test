import json
from urllib import request

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, validator
import httpx
from typing import List
from dotenv import load_dotenv
import os
import logging

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


app = FastAPI()

class Message(BaseModel):
    role: str
    content: str

class ChatMessage(BaseModel):
    messages: List[Message]
    model: str
    max_tokens: int
    stream: bool

    @validator('messages', each_item=True)
    def check_messages(cls, v):
        if v.role not in ["system", "user", "assistant"]:
            raise ValueError("Role must be 'system', 'user', or 'assistant'")
        return v


def get_next_sequence_number():
    """ Retrieve the next sequence number from a file, increment, and update the file. """
    sequence_path = "continue_requests/sequence.txt"
    try:
        with open(sequence_path, "r") as file:
            sequence_number = int(file.read().strip())
    except FileNotFoundError:
        sequence_number = 0

    sequence_number += 1

    with open(sequence_path, "w") as file:
        file.write(str(sequence_number))

    return sequence_number


@app.on_event("startup")
def setup_folder():
    """ Ensure the continue_requests folder exists at startup. """
    if not os.path.exists("continue_requests"):
        os.makedirs("continue_requests")


@app.post("/chat/completions")
async def chat(message: ChatMessage):
    # Retrieve the next sequence number
    sequence_number = get_next_sequence_number()

    # Convert the request data to JSON string
    raw_body = json.dumps(message.dict(), indent=2)

    # Define the file path in the continue_requests folder
    file_path = f"continue_requests/request_{sequence_number}.txt"

    # Write the data to a sequentially numbered text file within the folder
    with open(file_path, "w") as file:
        file.write(raw_body)

    # Log the JSON payload for debugging
    print(f"Request saved in {file_path}")

    # Return a simple JSON object indicating where the data was saved
    return {"message": "Data processed", "file": file_path}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=11435)