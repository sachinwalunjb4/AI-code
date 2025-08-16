from langchain_google_genai import ChatGoogleGenerativeAI
from duckduckgo_search import DDGS
import datetime

# 1) Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)

# Helper: run a DuckDuckGo search (manual, no agent)
def web_search(query: str) -> str:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=2))
    return results[0]["body"] if results else "No results found."

# 2) Step 1: Get RBI Governor
governor_info = web_search("Current RBI Governor of India")
print("Search Result:", governor_info)

# Extract name via LLM (not autonomous, we ask explicitly)
response1 = llm.invoke(f"Extract just the name of the RBI Governor from this text:\n{governor_info}")
governor_name = response1.content
print("Governor Name:", governor_name)

# 3) Step 2: Get Date of Birth (manual second query)
dob_info = web_search(f"{governor_name} date of birth")
print("DOB Search Result:", dob_info)

response2 = llm.invoke(f"Extract the date of birth from this text:\n{dob_info}")
dob_text = response2.content
print("DOB:", dob_text)

# 4) Step 3: Calculate Age manually (no math tool)
try:
    dob_year = int([word for word in dob_text.split() if word.isdigit()][0])
    current_year = datetime.date.today().year
    age = current_year - dob_year
except:
    age = "Unknown"

print("Calculated Age:", age)

# 5) Step 4: Summarize (explicit prompt, not memory-driven)
summary = llm.invoke(
    f"Summarize in one sentence: The RBI Governor is {governor_name}, "
    f"born in {dob_text}, currently about {age} years old."
)
print("Summary:", summary.content)
