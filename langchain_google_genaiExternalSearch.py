from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.agent_toolkits import load_tools
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.chains import LLMMathChain

# 1) LLM (Gemini 2.5 Pro)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)

# 2) Tools
# Web search (no API key needed)
search = DuckDuckGoSearchRun()
search_tool = Tool(
    name="Search",
    func=search.run,
    description="Use for current facts or news on the public web."
)

# Calculator (LLM-based math chain)
llm_math_chain = LLMMathChain.from_llm(llm=llm)
math_tool = Tool(
    name="Calculator",
    func=llm_math_chain.run,
    description="Useful for when you need to answer questions that require calculations or mathematical reasoning."
)

tools = [search_tool, math_tool]

# 3) Conversational memory
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

# 4) Initialize agent (react-style with conversation support)
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
    memory=memory,
)

# 5) Run a small demo conversation
print(agent.run("who has the highest batting average in the IPL?"))
print(agent.run("what is the batting average of the player?"))
print(agent.run("Summarize both answers briefly."))
