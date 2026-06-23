"""
Gerald Design Studio — FastAPI microservice for generating visual UI mockup concepts.
Runs on port 8002 independently of gerald_bridge.py (port 8000).

Start: uvicorn gerald_design_studio:app --host 0.0.0.0 --port 8002
"""
import asyncio
import os
import uuid

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

app = FastAPI(title="Gerald Design Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    description: str
    count: int = 3


class IterateRequest(BaseModel):
    original_description: str
    iteration_notes: str
    count: int = 1


def _build_prompt(description: str) -> str:
    return (
        f"A high-fidelity mobile app UI mockup screenshot for: {description}. "
        "Design style: Clean, modern flat design. Dark navy background with electric blue "
        "accent colors. Shows a realistic mobile phone screen with navigation elements, "
        "cards, buttons, and typography clearly visible. "
        "Professional UI/UX design mockup. No people or 3D elements. Pure mobile UI."
    )


async def _generate_one(
    client: AsyncOpenAI, prompt: str, concept_id: str, description: str
) -> dict:
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        response_format="b64_json",
    )
    return {
        "id": concept_id,
        "description": description,
        "image_b64": response.data[0].b64_json or "",
        "mime_type": "image/png",
        "revised_prompt": response.data[0].revised_prompt or prompt,
    }


@app.post("/design/generate")
async def generate_design_concepts(req: GenerateRequest):
    count = min(max(int(req.count), 1), 3)
    description = req.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    client = AsyncOpenAI(api_key=api_key)
    prompt = _build_prompt(description)

    tasks = [
        _generate_one(client, prompt, str(uuid.uuid4())[:8], description)
        for _ in range(count)
    ]
    concepts = list(await asyncio.gather(*tasks))
    return {"ok": True, "concepts": concepts}


@app.post("/design/iterate")
async def iterate_design_concept(req: IterateRequest):
    count = min(max(int(req.count), 1), 3)
    combined_desc = (
        f"{req.original_description.strip()}. "
        f"Refinement: {req.iteration_notes.strip()}"
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    client = AsyncOpenAI(api_key=api_key)
    prompt = _build_prompt(combined_desc)

    tasks = [
        _generate_one(client, prompt, str(uuid.uuid4())[:8], combined_desc)
        for _ in range(count)
    ]
    concepts = list(await asyncio.gather(*tasks))
    return {"ok": True, "concepts": concepts}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gerald-design-studio"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
