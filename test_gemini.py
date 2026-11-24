from google import genai

client = genai.Client()
interaction = client.interactions.create(
    model="gemini-4-hydrogen",
    input="Give one tip to reduce indoor smog exposure.",
)
print(interaction.output_text)