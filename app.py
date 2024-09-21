from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import requests
import re
import json
import logging
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from typing import List, Optional, Dict, Any
import aiohttp

app = FastAPI()

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')
print("WEBHOOK_VERIFY_TOKEN:", WEBHOOK_VERIFY_TOKEN)
GRAPH_API_TOKEN = os.getenv('GRAPH_API_TOKEN')
print("GRAPH_API_TOKEN:", GRAPH_API_TOKEN)
PORT = int(os.getenv('PORT', 3000))
print("PORT:", PORT)

MONGO_URI = os.getenv('MONGO_URI')  # Retrieve MongoDB URI from .env
MONGO_URI="mongodb+srv://maabanejubilant6:tbtQCFdA3dB4NHQI@backenddb.dorynel.mongodb.net"
print("MONGO_URI:", MONGO_URI)

# Set up MongoDB client
client = MongoClient(MONGO_URI)
db = client['messages_sent']  # Replace with your actual database name
collection = db['messages_collection']  # Use your desired collection name


# Function to send a message
def send_message(phone_number_id, recipient, message_content, message_type="text", template_name="", language_code="en_US", parameters=None):
    if parameters is None:
        parameters = ["param1", "param2"]

    GRAPH_API_VERSION = "v18.0"
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {GRAPH_API_TOKEN}",
        "Content-Type": "application/json"
    }

    if message_type == "text":
        message_data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "body": message_content
            }
        }
    elif message_type == "template":
        # Handle different templates
        if template_name == "hoa_main_welcome_m_m":
            message_data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    },
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "image": {
                                        "link": "https://cdn.glitch.global/3012a9fc-685b-458a-99d0-aecb6944077d/Connect%20My%20Estate.png?v=1723057525558"
                                    }
                                }
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "flow",
                            "index": 0
                        }
                    ]
                }
            }
        elif template_name == "order_confirmation":
            body_parameters = [{"type": "text", "text": param} for param in parameters]
            message_data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": body_parameters
                        }
                    ]
                }
            }
        else:
            raise ValueError("Unsupported template name")
    
    else:
        raise ValueError("Unsupported message type")

    try:
        response = requests.post(url, headers=headers, json=message_data)
        response.raise_for_status()
        return response.json()  # Return the response content
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


class IncomingMessage(BaseModel):
    entry: list

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print("Incoming webhook message:", data)
        
        changes = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {})
        
        logic_api_url = "https://whatsapp-flask-logic-app.onrender.com/process_message"
        database_api_url = "https://whatsapp-database-query-1.onrender.com/gated_communities/hoa_details"
        url_data_insert = "https://whatsapp-database-query-1.onrender.com/webhook_data_inert"
        INSERT_API_URL = url_data_insert

        if 'messages' in changes:
            message = changes['messages'][0]
            print("Received message:", message)
            user_phone_number = message['from']
            print("User phone number:", user_phone_number)

            if message['type'] == 'text':
                business_phone_number_id = changes.get('metadata', {}).get('phone_number_id')
                print("Business phone number ID:", business_phone_number_id)
                user_message = message['text']['body'].lower()
                print("User message:", user_message)

                # Check if phone number exists in the database
                try:
                    db_response = requests.get(f"{database_api_url}?phone_number={user_phone_number}")
                    raw_response = db_response.text
                    print("Raw database response:", raw_response)
                    
                    if db_response.status_code == 404:
                        response_message = "You are not registered in our system. Please contact support for assistance."
                        send_message(business_phone_number_id, user_phone_number, response_message)
                        return {"status": "ok", "message": "User not registered"}
                    
                    db_data = db_response.json()
                    print("Parsed database response:", db_data)

                    if 'data' in db_data and isinstance(db_data['data'], list) and len(db_data['data']) > 0:
                        data_full = db_data['data'][0]
                        hoa_name = data_full.get('hoa_name', 'Guest')
                        response_message = f"Welcome back {hoa_name}! How can we assist you today?"
                        send_message(business_phone_number_id, user_phone_number, response_message)
                    else:
                        response_message = "Sorry, there was an issue processing your request."
                        send_message(business_phone_number_id, user_phone_number, response_message)
                        return {"status": "ok", "message": "Issue with request"}
                except requests.RequestException as e:
                    print(f"Error querying the database API: {e}")
                    response_message = "There was an issue verifying your phone number. Please try again later."
                    send_message(business_phone_number_id, user_phone_number, response_message)
                    raise HTTPException(status_code=500, detail="Database query failed")

                # Process logic API based on message
                template_name = ""
                if re.search(r'\b\d+\b', user_message):
                    print("Integer Triggered:", user_message)
                    try:
                        response = requests.post(logic_api_url, json={"message": user_message})
                        response.raise_for_status()
                        response_data = response.json()
                        response_message2 = response_data.get('response', '').replace('\n', ' ')
                        print("Response from logic API:", response_message2)
                        response_message = response_message2
                    except requests.RequestException as e:
                        print(f"Error sending message to logic API: {e}")
                        response_message = "Sorry, there was an error processing your request."
                elif "hello" in user_message or "hi" in user_message:
                    template_name = "hoa_main_welcome_m_m"
                elif "main menu" in user_message or "menu" in user_message:
                    template_name = "main_menu_hoa_m"
                elif "escalation" in user_message:
                    template_name = "hoa_escalation_m"
                else:
                    response_message = "Sorry, I did not understand your request."

                try:
                    if template_name:
                        send_message(business_phone_number_id, message['from'], "", "template", template_name)
                    else:
                        send_message(business_phone_number_id, message['from'], response_message)

                    # Mark message as read
                    requests.post(
                        f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages",
                        headers={"Authorization": f"Bearer {GRAPH_API_TOKEN}"},
                        json={"messaging_product": "whatsapp", "status": "read", "message_id": message['id']}
                    )
                except requests.RequestException as e:
                    print(f"Error processing message: {e}")

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the webhook.")
    
    return {"status": "ok"}


@app.get("/webhook")
async def webhook_verification(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
            logging.info("Webhook verified successfully.")
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            logging.warning("Webhook verification failed. Invalid token or mode.")
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        logging.error("Missing mode or token in the request.")
        raise HTTPException(status_code=400, detail="Bad Request")
    

# Define the schema for incoming messages
class IncomingMessage(BaseModel):
    object: str
    entry: List[Dict[str, Any]]

class SendMessageRequest(BaseModel):
    phone_number_id: str
    recipient: str
    message_content: str
    message_type: str = "text"
    template_name: str = ""
    language_code: str = "en_US"
    parameters: List[str] = ["2024-09-04", "S02879"]

class CheckAndRespondRequest(BaseModel):
    database_api_url: str
    user_phone_number: str
    changes: Dict[str, Any]


async def send_message(phone_number_id: str, recipient: str, message_content: str, message_type: str = "text", template_name: str = "", language_code: str = "en_US", parameters: List[str] = ["param1", "param2"]):
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {GRAPH_API_TOKEN}",
        "Content-Type": "application/json"
    }

    if message_type == "text":
        message_data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "body": message_content
            }
        }
    elif message_type == "template":
        if template_name == "hoa_main_welcome_m_m":
            message_data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    },
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "image": {
                                        "link": "https://cdn.glitch.global/3012a9fc-685b-458a-99d0-aecb6944077d/Connect%20My%20Estate.png?v=1723057525558"
                                    }
                                }
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "flow",
                            "index": 0
                        }
                    ]
                }
            }
        else:
            raise ValueError("Unsupported template name")
    else:
        raise ValueError("Unsupported message type")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=message_data) as response:
            response.raise_for_status()
            return await response.json()

@app.post("/sendmessage")
async def handle_send_message(request: SendMessageRequest):
    try:
        response = await send_message(
            phone_number_id=request.phone_number_id,
            recipient=request.recipient,
            message_content=request.message_content,
            message_type=request.message_type,
            template_name=request.template_name,
            language_code=request.language_code,
            parameters=request.parameters
        )
        return {"status": "success", "response": response}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check_and_respond")
async def check_and_respond_to_user(request: CheckAndRespondRequest):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{request.database_api_url}?phone_number={request.user_phone_number}") as db_response:
                raw_response = await db_response.text()
                print("Raw database response:", raw_response)

                if db_response.status == 404:
                    response_message = "You are not registered in our system. Please contact support for assistance."
                    business_phone_number_id = request.changes.get('metadata', {}).get('phone_number_id')
                    await send_message(business_phone_number_id, request.user_phone_number, response_message)
                    return {"status": "ok", "message": "User not registered"}

                if db_response.status == 200:
                    try:
                        db_data = await db_response.json()
                        print("Parsed database response:", db_data)

                        if 'data' in db_data and isinstance(db_data['data'], list) and len(db_data['data']) > 0:
                            data_full = db_data['data'][0]
                            hoa_name = data_full.get('hoa_name', 'Guest')
                            response_message = f"Welcome back {hoa_name}! How can we assist you today?"
                            business_phone_number_id = request.changes.get('metadata', {}).get('phone_number_id')

                            if request.user_phone_number and business_phone_number_id:
                                print(f"business_phone_number_id: {business_phone_number_id}, user_phone_number: {request.user_phone_number}, response_message: {response_message}")
                            else:
                                logging.warning("User phone number or business phone number ID is missing.")
                        else:
                            response_message = "Sorry, there was an issue processing your request."
                            business_phone_number_id = request.changes.get('metadata', {}).get('phone_number_id')
                            await send_message(business_phone_number_id, request.user_phone_number, response_message)
                            return {"status": "ok", "message": "Issue with request"}

                    except ValueError as e:
                        logging.error(f"Error parsing database JSON response: {e}")
                        raise HTTPException(status_code=500, detail="Invalid response format")

                else:
                    logging.error(f"Unexpected response from database API: {db_response.status}")
                    raise HTTPException(status_code=500, detail="Unexpected error querying the database")

    except aiohttp.ClientError as e:
        logging.error(f"Error querying the database API: {e}")
        response_message = "There was an issue verifying your phone number. Please try again later."
        business_phone_number_id = request.changes.get('metadata', {}).get('phone_number_id')
        await send_message(business_phone_number_id, request.user_phone_number, response_message)
        raise HTTPException(status_code=500, detail="Database query failed")

@app.post("/classify_message")
async def classify_message(incoming_message: Dict[str, Any]):
    dropdown_value = incoming_message.get('screen_0_Dropdown_0', '')
    classification = "Order/Fault" if "Order/Fault" in dropdown_value else "Unknown"
    print(f"Classification: {classification}")
    return {"classification": classification}

@app.post("/send_email")
async def send_email(logic_api_url2: str, incoming_message: Dict[str, Any]):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(logic_api_url2, json=incoming_message) as response:
                response.raise_for_status()
                print("Email sent successfully")
                await classify_message(incoming_message)
                return {"status": "success"}
    except aiohttp.ClientError as e:
        print(f"Failed to send email: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/getMessages")
async def get_messages(recipient: Optional[str] = None, status: Optional[str] = None):
    try:
        match_conditions = {}
        if recipient:
            match_conditions['recipient'] = recipient
        if status:
            match_conditions['status_code'] = status

        # Replace with actual MongoDB retrieval logic
        pipeline = [
            {'$match': match_conditions},
            {'$sort': {'_id': -1}},
            {'$project': {'_id': 0}}
        ]

        # Replace `collection` with your MongoDB collection
        # messages = list(collection.aggregate(pipeline))
        messages = []  # Placeholder
        print("Messages found:", messages)
        return {"messages": messages}
    except Exception as e:
        print("Error retrieving messages:", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")

@app.get("/status")
async def status():
    return {"status": "Server is running"}
