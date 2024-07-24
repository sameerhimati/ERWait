import openai
from helpers.config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def get_chat_response(user_input):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant providing information about healthcare and medical topics."},
                {"role": "user", "content": user_input}
            ]
        )
        return response.choices[0].message['content']
    except Exception as e:
        print(f"Error in chat service: {str(e)}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again later."

# You can add more functions here for handling different types of chat interactions or processing the chat history