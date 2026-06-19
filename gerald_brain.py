"""
gerald_brain.py — Brain file management for Gerald projects.

Provides functions to:
- Read brain files from a project directory
- Auto-create brain stubs if missing
- Inject brain context into Claude prompts
- Generate isolation blocks (forbidden paths)
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional


# Brain file definitions
BRAIN_FILES = [
    "project_brain.md",
    "roadmap.md",
    "current_status.md",
    "architecture.md"
]


def get_brain_stub(filename: str, project_name: str) -> str:
    """
    Generate a minimal brain file stub for a new project.
    
    Args:
        filename: Name of the brain file (e.g., "project_brain.md")
        project_name: Name of the project
        
    Returns:
        String content for the stub file
    """
    stubs = {
        "project_brain.md": f"""# {project_name} — Project Brain

## Overview
[Describe what this project does]

## Tech Stack
- [List technologies used]

## Architecture
- [Describe key components]

## Key Decisions
- [Document important architectural decisions]
""",
        "roadmap.md": f"""# {project_name} — Roadmap

## Completed
- [ ] Initial project setup

## Planned
- [ ] [Add planned features here]
""",
        "current_status.md": f"""# {project_name} — Current Status

**Last Updated:** [Date]
**Version:** V0.1

## What's Working
- Initial project structure created

## Active Issues
- None

## Next Steps
- [Define initial tasks]
""",
        "architecture.md": f"""# {project_name} — Architecture

## Structure
```
{project_name}/
├── [List key files and directories]
```

## Data Flow
[Describe how data flows through the system]

## Key Decisions
- [Document architectural choices]
"""
    }
    
    return stubs.get(filename, f"# {project_name} — {filename}\n\n[Content to be added]\n")


def has_brain_files(project_path: str) -> bool:
    """
    Check if a project has at least one brain file.
    
    Args:
        project_path: Absolute path to the project directory
        
    Returns:
        True if at least one brain file exists, False otherwise
    """
    for brain_file in BRAIN_FILES:
        if os.path.isfile(os.path.join(project_path, brain_file)):
            return True
    return False


def create_brain_files(project_path: str, project_name: str) -> List[str]:
    """
    Create brain file stubs in a project directory.
    
    Args:
        project_path: Absolute path to the project directory
        project_name: Name of the project (for stub content)
        
    Returns:
        List of created file paths
    """
    created_files = []
    
    for brain_file in BRAIN_FILES:
        file_path = os.path.join(project_path, brain_file)
        
        # Only create if it doesn't exist
        if not os.path.isfile(file_path):
            stub_content = get_brain_stub(brain_file, project_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(stub_content)
            
            created_files.append(file_path)
    
    return created_files


def read_brain_files(project_path: str) -> Dict[str, str]:
    """
    Read all brain files from a project directory.
    
    Args:
        project_path: Absolute path to the project directory
        
    Returns:
        Dictionary mapping filename to file content.
        Missing files are excluded from the result.
    """
    brain_content = {}
    
    for brain_file in BRAIN_FILES:
        file_path = os.path.join(project_path, brain_file)
        
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    brain_content[brain_file] = f.read()
            except Exception as e:
                # Log error but continue reading other files
                print(f"Warning: Could not read {file_path}: {e}")
    
    return brain_content


def format_brain_context(brain_content: Dict[str, str]) -> str:
    """
    Format brain file content for injection into Claude prompts.
    
    Args:
        brain_content: Dictionary mapping filename to file content
        
    Returns:
        Formatted string ready for prompt injection
    """
    if not brain_content:
        return ""
    
    sections = ["# Project Brain (Context)"]
    
    for filename, content in brain_content.items():
        sections.append(f"### {filename}")
        sections.append(content)
    
    return "\n".join(sections)


def get_forbidden_paths(
    projects_file: str = "/opt/Gerald/gerald_projects.json",
    current_project_path: Optional[str] = None
) -> List[str]:
    """
    Get list of forbidden paths for project isolation.
    
    Args:
        projects_file: Path to gerald_projects.json
        current_project_path: Path to current project (excluded from forbidden list)
        
    Returns:
        List of absolute paths that should not be accessed
    """
    forbidden = []
    
    if not os.path.isfile(projects_file):
        return forbidden
    
    try:
        with open(projects_file, 'r', encoding='utf-8') as f:
            projects = json.load(f)
        
        for project in projects:
            project_path = project.get("path", "")
            
            # Normalize paths for comparison
            normalized_project_path = os.path.normpath(project_path)
            normalized_current_path = os.path.normpath(current_project_path) if current_project_path else None
            
            # Exclude current project from forbidden list
            if normalized_current_path and normalized_project_path == normalized_current_path:
                continue
            
            if project_path and os.path.isdir(project_path):
                forbidden.append(project_path)
    
    except Exception as e:
        print(f"Warning: Could not read projects file: {e}")
    
    return forbidden


def format_isolation_block(forbidden_paths: List[str]) -> str:
    """
    Format isolation block for injection into Claude prompts.
    
    Args:
        forbidden_paths: List of paths that should not be accessed
        
    Returns:
        Formatted isolation instructions
    """
    if not forbidden_paths:
        return ""
    
    lines = ["# Project Isolation"]
    lines.append("DO NOT read or modify any files outside the current project directory.")
    lines.append("Explicitly forbidden paths:")
    
    for path in forbidden_paths:
        lines.append(f"- {path}")
    
    return "\n".join(lines)


def inject_brain_context(
    original_prompt: str,
    project_path: str,
    project_name: str,
    projects_file: str = "/opt/Gerald/gerald_projects.json",
    auto_create: bool = True
) -> str:
    """
    Inject brain context and isolation rules into a Claude prompt.
    
    Args:
        original_prompt: The user's original task prompt
        project_path: Absolute path to the project directory
        project_name: Name of the project
        projects_file: Path to gerald_projects.json
        auto_create: If True, create brain files if missing
        
    Returns:
        Enhanced prompt with brain context and isolation rules
    """
    # Auto-create brain files if missing
    if auto_create and not has_brain_files(project_path):
        created = create_brain_files(project_path, project_name)
        print(f"Auto-created {len(created)} brain files for {project_name}")
    
    # Read brain files
    brain_content = read_brain_files(project_path)
    brain_context = format_brain_context(brain_content)
    
    # Get forbidden paths for isolation
    forbidden_paths = get_forbidden_paths(projects_file, project_path)
    isolation_block = format_isolation_block(forbidden_paths)
    
    # Build enhanced prompt
    sections = []
    
    # 1. Original user prompt
    sections.append(original_prompt)
    
    # 2. Brain context (if available)
    if brain_context:
        sections.append("\n" + brain_context)
    
    # 3. Isolation block (if needed)
    if isolation_block:
        sections.append("\n" + isolation_block)
    
    # 4. Brain update instructions
    sections.append("""
# Project Brain Update
After completing the task, update the brain files if relevant:
- current_status.md — always update if you changed code (what is now working, any blockers)
- roadmap.md — update if you completed items or identified new ones
- project_brain.md — update if tech stack, architecture, or key decisions changed
- architecture.md — update if the system structure changed
Only update files that are directly relevant to what you just did. Keep updates concise.
""")
    
    return "\n".join(sections)


def get_brain_status(project_path: str) -> Dict[str, bool]:
    """
    Check which brain files exist in a project.

    Args:
        project_path: Absolute path to the project directory

    Returns:
        Dictionary mapping brain file names to existence status
    """
    status = {}

    for brain_file in BRAIN_FILES:
        file_path = os.path.join(project_path, brain_file)
        status[brain_file] = os.path.isfile(file_path)

    return status


if __name__ == "__main__":
    _result = inject_brain_context(
        "test task",
        "/opt/Gerald",
        "CommuteCoder",
        auto_create=False,
    )
    assert "test task" in _result, "inject_brain_context dropped the original prompt"
    print(f"[brain-test] inject_brain_context OK — {len(_result)} chars returned, original prompt preserved")
