import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import os
from dotenv import load_dotenv
load_dotenv('.env')

from google import genai
client = genai.Client(vertexai=True, project="super-billwencheng-test001", location="us-central1")
try:
    res = client.models.generate_content(model="gemini-2.5-pro", contents="hello")
    print("SUCCESS:", res.text)
except Exception as e:
    print("ERROR:", str(e))
