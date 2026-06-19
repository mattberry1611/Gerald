import os
import base64
from openai import OpenAI

VISION_PROMPT = """
You are Gerald, Matt's AI project manager and UI reviewer.

Review this app screenshot like a senior product/design partner.

Give:
1. What looks good.
2. What looks wrong or confusing.
3. What should be improved first.
4. A practical redesign plan.

Be direct, useful, and focused on improving the app.
"""

def review_image(image_bytes: bytes, mime_type: str = "image/jpeg", prompt: str = "") -> str:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"

    user_text = prompt.strip() or "Please review this Gerald app screenshot and suggest improvements."

    response = client.responses.create(
        model="gpt-4.1",
        instructions=VISION_PROMPT,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": user_text},
                {"type": "input_image", "image_url": data_url},
            ],
        }],
    )

    return response.output_text.strip()
