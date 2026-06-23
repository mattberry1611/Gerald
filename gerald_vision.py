import os
import re
import json
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


VISUAL_COPY_COMPARE_PROMPT = """
You are a precise UI visual comparison engine.

You will be shown two images:
1. TARGET: the reference/design image that the UI should match
2. CURRENT: the actual current screenshot of the implementation

Compare them exhaustively and return ONLY valid JSON with exactly these fields:

{
  "similarity_score": <integer 0-100, where 100 = pixel-perfect match>,
  "layout_differences": "<description of layout/positioning differences>",
  "size_proportion_differences": "<description of size and proportion differences>",
  "colour_differences": "<description of colour/background/border colour differences>",
  "typography_differences": "<description of font, size, weight, spacing differences>",
  "missing_extra_elements": "<elements present in TARGET but missing in CURRENT, and vice versa>",
  "top_5_fixes": [
    "<specific actionable fix 1>",
    "<specific actionable fix 2>",
    "<specific actionable fix 3>",
    "<specific actionable fix 4>",
    "<specific actionable fix 5>"
  ],
  "summary": "<1-2 sentence summary of the main visual gap and most important fix>"
}

Be precise and specific. Reference actual values where visible (e.g. pixel sizes, hex colours, font names).
Return ONLY the JSON object. No markdown fences. No explanation outside the JSON.
"""


def compare_images(
    target_bytes: bytes,
    target_mime: str,
    result_bytes: bytes,
    result_mime: str,
) -> dict:
    """Compare a target/reference image against a current-result screenshot via GPT-4.1 vision.

    Returns a dict with similarity_score (0-100), layout_differences,
    size_proportion_differences, colour_differences, typography_differences,
    missing_extra_elements, top_5_fixes (list), and summary.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    target_data_url = f"data:{target_mime};base64,{base64.b64encode(target_bytes).decode()}"
    result_data_url = f"data:{result_mime};base64,{base64.b64encode(result_bytes).decode()}"

    response = client.responses.create(
        model="gpt-4.1",
        instructions=VISUAL_COPY_COMPARE_PROMPT,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "IMAGE 1 (TARGET/REFERENCE):"},
                {"type": "input_image", "image_url": target_data_url},
                {"type": "input_text", "text": "IMAGE 2 (CURRENT RESULT):"},
                {"type": "input_image", "image_url": result_data_url},
            ],
        }],
    )

    raw = response.output_text.strip()
    # Strip markdown code fences if the model wraps in them
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()

    parsed = json.loads(raw)

    fixes = parsed.get("top_5_fixes", [])
    if not isinstance(fixes, list):
        fixes = [str(fixes)]
    parsed["top_5_fixes"] = fixes[:5]

    return parsed
