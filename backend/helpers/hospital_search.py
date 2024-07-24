import requests
from bs4 import BeautifulSoup
from googlesearch import search
import openai
import os

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_hospital_address_web_search(hospital_name):
    # Perform a web search
    search_results = search(f"{hospital_name} address", num_results=5)
    
    content = ""
    for url in search_results:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            content += soup.get_text() + "\n"
        except:
            continue

    # Use an LLM to extract the address from the content
    return extract_address_with_llm(hospital_name, content)

def extract_address_with_llm(hospital_name, content):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Extract the full address of the hospital from the given text."},
            {"role": "user", "content": f"Hospital name: {hospital_name}\n\nContent: {content}"}
        ]
    )
    return response.choices[0].message['content'].strip()

import requests

def get_hospital_address_geocoding(hospital_name):
    # Replace with your actual Google Maps API key
    api_key = "your_google_maps_api_key"
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    params = {
        "address": hospital_name,
        "key": api_key
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if data["status"] == "OK":
        address = data["results"][0]["formatted_address"]
        return address
    else:
        return "Address not found"
    
import requests

def get_hospital_address_hhs(hospital_name):
    base_url = "https://data.cms.gov/provider-data/api/1/datastore/sql"
    query = f"SELECT NAME, ADDRESS FROM 34b46d35-e980-40c7-9f20-07a8c8e89893 WHERE NAME LIKE '%{hospital_name}%' LIMIT 1"
    
    params = {
        "query": query
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if data and len(data) > 0:
        return data[0]["ADDRESS"]
    else:
        return "Address not found"
    
from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.llms import OpenAI

def get_hospital_address_langchain(hospital_name):
    # Set your OpenAI API key
    openai_api_key = "your_openai_api_key"
    
    # Initialize the language model
    llm = OpenAI(temperature=0, openai_api_key=openai_api_key)
    
    # Load the search tool
    tools = load_tools(["serpapi"], llm=llm)
    
    # Initialize the agent
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)
    
    # Run the agent
    result = agent.run(f"Find the full address of {hospital_name}. Return only the address, nothing else.")
    
    return result

# import os
# from llama_index import GPTSimpleVectorIndex, SimpleDirectoryReader, Document
# from llama_index.node_parser import SimpleNodeParser
# from llama_index.langchain_helpers.text_splitter import TokenTextSplitter
# from llama_index.readers.web import SimpleWebPageReader

# def get_hospital_address_llama_index(hospital_name):
#     # Set your OpenAI API key
#     os.environ['OPENAI_API_KEY'] = "your_openai_api_key"
    
#     # Create a web crawler and fetch content
#     urls = [f"https://www.google.com/search?q={hospital_name}+address"]
#     documents = SimpleWebPageReader(html_to_text=True).load_data(urls)
    
#     # Parse the documents into nodes
#     parser = SimpleNodeParser.from_defaults(
#         text_splitter=TokenTextSplitter(chunk_size=1024, chunk_overlap=20)
#     )
#     nodes = parser.get_nodes_from_documents(documents)
    
#     # Build the index
#     index = GPTSimpleVectorIndex(nodes)
    
#     # Query the index
#     response = index.query(f"What is the full address of {hospital_name}?")
    
#     return response.response

