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


TASK_ANALYSIS_PROMPT = """
You are an expert image analyst helping a code assistant understand an uploaded image.

Produce a structured analysis with these sections:

1. **Image Description**: What is shown overall (screenshot, diagram, mockup, photo, etc.).
2. **UI / Layout / Style Details**: Components, layout structure, colors, typography, spacing, design patterns. Note any specific measurements or positions if visible.
3. **Visible Text**: Extract ALL text visible in the image exactly as written (labels, button text, headings, code, messages, error text, URLs, etc.).
4. **Task-Relevant Summary**: Key information a developer needs to implement or match what is shown. Include any IDs, class names, or data values visible.

Be thorough and precise. This text will replace the image for a code assistant that cannot view images directly.
"""


def analyze_image_for_task(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Analyze an image and return structured text suitable for injecting into a Claude Code task."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"

    response = client.responses.create(
        model="gpt-4.1",
        instructions=TASK_ANALYSIS_PROMPT,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Analyze this image for a development task context."},
                {"type": "input_image", "image_url": data_url},
            ],
        }],
    )

    return response.output_text.strip()
