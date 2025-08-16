from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationBufferMemory

# 1. Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.7)

# 2. Add Memory
memory = ConversationBufferMemory(return_messages=True)

# 3. Create a Conversation Chain
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True
)

# 4. Interact with the agent
print(conversation.predict(input="Who is the current Prime Minister of India?"))
print(conversation.predict(input="What year was he born?"))   # <-- remembers "he"
print(conversation.predict(input="Summarize both answers in one sentence."))