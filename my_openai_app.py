from openai import OpenAI

# It's recommended to set your API key as an environment variable (OPENAI_API_KEY)
# Alternatively, you can pass it directly:
# client = OpenAI(api_key="YOUR_API_KEY")

client = OpenAI()

try:
    chat_completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello world"}],
    )
    print(chat_completion.choices[0].message.content)
except Exception as e:
    print(f"An error occurred: {e}")
