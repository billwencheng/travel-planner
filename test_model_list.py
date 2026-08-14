import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import os
from dotenv import load_dotenv
load_dotenv('.env')

from google import genai
client = genai.Client(vertexai=True, project="super-billwencheng-test001", location="asia-southeast1")
try:
    for model in client.models.list():
        print(model.name)
except Exception as e:
    print("ERROR:", str(e))
