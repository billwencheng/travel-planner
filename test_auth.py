import os
import asyncio
from dotenv import load_dotenv
from google.genai import Client

# Disable mTLS via env vars before loading anything
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"

load_dotenv(".env.local")

async def main():
    try:
        client = Client(vertexai=True, project=os.getenv("GOOGLE_CLOUD_PROJECT"), location=os.getenv("GOOGLE_CLOUD_LOCATION"))
        response = await client.aio.models.generate_content(
            model='gemini-1.5-flash',
            contents='Hello, who are you?'
        )
        print("Response:", response.text)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
