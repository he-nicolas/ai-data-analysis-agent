

from dotenv import load_dotenv
load_dotenv()


from langsmith import Client
import os

client = Client()
print("LangChain API Key:", os.getenv("LANGCHAIN_API_KEY")[:10])
print("Project:", os.getenv("LANGCHAIN_PROJECT"))

projects = client.list_projects()

for project in projects:
    print(project.name)