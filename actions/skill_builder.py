"""Draft, inspect, and request approval for generated plugins.

The source checks catch accidental mistakes only; Python plugin code is not
sandboxed. Installation requires explicit review and a process restart.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from threading import Thread

from core import gemini
from core.llm_client import call_llm_text, get_llm_provider


def _base_dir() -> Path:
    import sys
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def _safe_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    if not name or not name[0].isalpha() and name[0] != "_":
        name = "skill_" + name
    return name[:64]


def _extract_code(text: str) -> str:
    text = (text or "").strip()
    match = re.search(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)\s*```", text, flags=re.DOTALL)
    if match:
        code = match.group(1).strip()
    else:
        code = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", text, flags=re.I)
        code = re.sub(r"\s*```$", "", code).strip()
    lines = code.splitlines()
    if lines and lines[0].strip().lower() in ("python", "python3", "py", "markdown", "code"):
        code = "\n".join(lines[1:]).strip()
    return code


def _ask_model(request: str, name: str) -> str:
    prompt = (
        "Write one self-contained Python plugin for the Mark LV personal assistant. "
        "Return ONLY Python source code inside a markdown block. "
        "The code MUST follow this exact structure:\n\n"
        "PLUGIN = {\n"
        f"    \"name\": {json.dumps(name)},\n"
        "    \"description\": \"Describe what the plugin does\",\n"
        "    \"parameters\": {\n"
        "        \"type\": \"OBJECT\",\n"
        "        \"properties\": {},\n"
        "        \"required\": []\n"
        "    }\n"
        "}\n\n"
        "def run(parameters: dict, player=None, session_memory=None) -> str:\n"
        "    # Your code here\n"
        "    return \"Result string\"\n\n"
        "Rules:\n"
        "- Use safe standard library imports only (json, math, datetime, re, time, string, typing, collections).\n"
        "- Do NOT use subprocess, eval, exec, destructive file writes, or system commands.\n"
        "- Parameters schema must have 'type': 'OBJECT'.\n"
        "- Always return a clear natural language string.\n\n"
        f"Capability requested: {request}"
    )
    
    try:
        provider = get_llm_provider()
        if provider in ("ollama", "openai"):
            print(f"[SkillBuilder] Drafting via local LLM / Hermes ({provider})…")
            text = call_llm_text(prompt, system="You are an expert Python plugin developer for MARK LV.", timeout=60)
            if text:
                return _extract_code(text)
    except Exception as e:
        print(f"[SkillBuilder] Local LLM draft failed ({e}), falling back to Gemini…")

    response = gemini.call(prompt, tier=gemini.SMART, timeout_ms=60000)
    if response is None:
        raise RuntimeError("The model did not return a draft.")
    return _extract_code(getattr(response, "text", "") or "")


def _clean_and_normalize(source: str, expected_name: str) -> str:
    # 1. Clean markdown fences or surrounding chatter
    source = _extract_code(source)

    # 2. Fix lowercase 'object' in parameters
    source = re.sub(r'([\"\']type[\"\']\s*:\s*[\"\'])object([\"\'])', r'\g<1>OBJECT\g<2>', source)

    # 3. Parse AST to inspect and normalize PLUGIN dict
    try:
        tree = ast.parse(source)
    except Exception:
        return source

    assign_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PLUGIN" for t in node.targets):
            assign_node = node
            break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "PLUGIN":
            assign_node = node
            break

    if assign_node and assign_node.value:
        try:
            meta = ast.literal_eval(assign_node.value)
            if isinstance(meta, dict):
                modified = False
                if meta.get("name") != expected_name:
                    meta["name"] = expected_name
                    modified = True
                params = meta.get("parameters")
                if not isinstance(params, dict):
                    meta["parameters"] = {"type": "OBJECT", "properties": {}, "required": []}
                    modified = True
                elif params.get("type") != "OBJECT":
                    if "properties" not in params:
                        clean_props = {}
                        for k, v in params.items():
                            if isinstance(v, dict):
                                clean_props[k] = v
                                if "type" in v and isinstance(v["type"], str):
                                    v["type"] = v["type"].upper()
                        meta["parameters"] = {
                            "type": "OBJECT",
                            "properties": clean_props,
                            "required": list(clean_props.keys())
                        }
                    else:
                        params["type"] = "OBJECT"
                        meta["parameters"] = params
                    modified = True
                else:
                    props = params.get("properties", {})
                    if isinstance(props, dict):
                        for k, v in props.items():
                            if isinstance(v, dict) and "type" in v and isinstance(v["type"], str):
                                v["type"] = v["type"].upper()

                if modified:
                    formatted_meta = "PLUGIN = " + json.dumps(meta, indent=4)
                    lines = source.splitlines()
                    new_lines = lines[:assign_node.lineno - 1] + [formatted_meta] + lines[assign_node.end_lineno:]
                    source = "\n".join(new_lines)
        except Exception as e:
            print(f"[SkillBuilder] AST literal_eval note: {e}")

    return source


def _check_source(source: str, expected_name: str) -> str:
    source = _clean_and_normalize(source, expected_name)
    if not source or len(source) > 20_000:
        raise ValueError("Draft is empty or exceeds the 20 KB limit.")
    tree = ast.parse(source)
    forbidden = {"exec", "eval", "compile", "__import__", "open", "input", "os.system", "subprocess"}
    allowed_modules = {
        "json", "math", "datetime", "urllib", "re", "random", "collections",
        "time", "string", "typing", "calendar", "decimal", "functools",
        "itertools", "statistics", "base64", "hashlib"
    }
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod_name = node.module.split('.')[0] if isinstance(node, ast.ImportFrom) and node.module else (node.names[0].name.split('.')[0] if node.names else "")
            if mod_name not in allowed_modules:
                raise ValueError(f"Draft imports restricted or unknown module '{mod_name}'. Allowed: {allowed_modules}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden:
            raise ValueError(f"Draft uses prohibited operation: {node.func.id}.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Draft uses prohibited dunder access.")

    names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                assignments[node.target.id] = node.value

    if "run" not in names or "PLUGIN" not in assignments:
        raise ValueError("Draft must define PLUGIN and run().")
    try:
        metadata = ast.literal_eval(assignments["PLUGIN"])
    except Exception as exc:
        raise ValueError("PLUGIN metadata must be a literal dictionary.") from exc
    if not isinstance(metadata, dict) or metadata.get("name") != expected_name:
        raise ValueError("Draft metadata has an unexpected plugin name.")
    if not isinstance(metadata.get("description"), str) or not isinstance(metadata.get("parameters"), dict):
        raise ValueError("Draft metadata is missing a description or parameter schema.")
    if metadata["parameters"].get("type") != "OBJECT":
        raise ValueError("Plugin parameters must use an OBJECT schema.")
    return source.rstrip() + "\n"



def _create_draft(request: str, name: str, player=None) -> str:
    plugins_dir = _base_dir() / "plugins"
    target = plugins_dir / f"{name}.py"
    if target.exists():
        return f"A plugin named {name} already exists. No file was changed."
    draft_dir = plugins_dir / "drafts"
    draft = draft_dir / f"{name}.py"
    if draft.exists():
        return f"A draft named {name} already exists. Review that draft; no file was changed."
    source = _check_source(_ask_model(request, name), name)
    draft_dir.mkdir(parents=True, exist_ok=True)
    try:
        with draft.open("x", encoding="utf-8") as handle:
            handle.write(source)
    except FileExistsError:
        return f"A draft named {name} already exists. Review that draft; no file was changed."
    return f"Draft successfully created and verified at {draft}. Ready for installation."


def load_draft_plugin(name: str, player=None) -> str:
    """Install a reviewed draft on explicit user approval; restart loads it."""
    base = _base_dir()
    drafts_dir = base / "plugins" / "drafts"
    plugins_dir = base / "plugins"
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,63}", name or ""):
        return "Invalid plugin name. No file was changed."
    draft_path = drafts_dir / f"{name}.py"
    target_path = plugins_dir / f"{name}.py"

    if not draft_path.exists():
        return f"No draft found for {name}."
    if target_path.exists():
        return f"A plugin named {name} already exists. No file was changed."
    try:
        _check_source(draft_path.read_text(encoding="utf-8"), name)
    except Exception as exc:
        return f"Draft verification failed ({exc}); it was not installed."
    from core import confirm
    result = confirm.request(
        key=f"install-plugin-{name}",
        title=f"Install plugin draft {name}",
        detail=(
            f"Install {draft_path} into plugins/{name}.py?\n"
            "Python plugins run with this user's permissions the next time Mark-LV starts. "
            "The syntax checks are not a sandbox. Review the draft source yourself before approving."
        ),
        run=lambda: _install_draft_now(draft_path, target_path, name, player),
    )
    return result


def _install_draft_now(draft_path: Path, target_path: Path, name: str, player=None) -> str:
    """Revalidate and move a draft after the confirmation gate resolves."""
    if target_path.exists():
        return f"A plugin named {name} already exists. The draft was not installed."
    try:
        source = _check_source(draft_path.read_text(encoding="utf-8"), name)
        target_path.write_text(source, encoding="utf-8")
        draft_path.unlink()
    except Exception as exc:
        return f"Could not install {name}: {exc}. The draft was not activated."
    if player and hasattr(player, "request_say"):
        player.request_say(f"Plugin draft {name} was installed after your approval. Restart Mark-LV to load it.")
    return f"Plugin {name} installed. Restart Mark-LV to load it."


def list_plugin_drafts() -> str:
    """List draft plugin names, never importing or executing their source."""
    drafts_dir = _base_dir() / "plugins" / "drafts"
    try:
        names = sorted(path.stem for path in drafts_dir.glob("*.py") if path.is_file())
    except OSError as exc:
        return f"Could not list plugin drafts: {exc}"
    return "No plugin drafts are waiting for review." if not names else "Plugin drafts (review source before installing):\n" + "\n".join(names)


def skill_builder(parameters: dict = None, player=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "draft")).strip().lower()
    if action == "list_drafts":
        return list_plugin_drafts()
    if action == "install_draft":
        name = str(params.get("name", "")).strip()
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,63}", name or ""):
            return "Invalid plugin name. No file was changed."
        try:
            source = (_base_dir() / "plugins" / "drafts" / f"{name}.py").read_text(encoding="utf-8")
        except Exception:
            source = ""
        if not source:
            return load_draft_plugin(name, player)
        if player and hasattr(player, "show_content"):
            player.show_content(f"PLUGIN DRAFT — {name}", source[:4000])
        return load_draft_plugin(name, player)
    if action != "draft":
        return "Unknown action. Use draft, list_drafts, or install_draft."
    request = str(params.get("request", "")).strip()
    if not request or len(request) > 2000:
        return "Describe the capability in 1–2000 characters. No plugin was created."
    name = _safe_name(str(params.get("name", "")) or request[:50])
    if name in {"_template", "skill_builder"}:
        return "That plugin name is reserved. No draft was created."
    try:
        worker = Thread(
            target=lambda: _run_draft_worker(request, name, player),
            daemon=True,
            name=f"skill-draft-{name}",
        )
        worker.start()
        return f"I’m drafting {name} using Hermes/Gemini in the background. I’ll notify you when it's ready for review and installation."
    except Exception as exc:
        return f"Could not start the draft: {exc}. No plugin was installed."


def _run_draft_worker(request: str, name: str, player=None) -> None:
    success = False
    try:
        result = _create_draft(request, name, player)
        success = "successfully created" in result.lower()
    except Exception as exc:
        result = f"Could not create a safe plugin draft: {exc}. No plugin was installed."
    if player:
        try:
            player.write_log(f"SYS: {result}")
        except Exception:
            pass
        try:
            if hasattr(player, "request_say"):
                if success:
                    player.request_say(f"Plugin draft for {name} is ready for review.")
                else:
                    player.request_say(f"Drafting plugin {name} was not successful.")
        except Exception:
            pass


TOOL = {
    "name": "skill_builder",
    "description": ("Drafts reviewable Python plugins via the configured local Hermes/Ollama/OpenAI-compatible LLM or Gemini, "
                    "lists pending drafts, and can request explicit on-screen approval to install a selected draft. "
                    "A Python source check is NOT a sandbox; user must review the file in plugins/drafts before installation. "
                    "Installed plugins require a Mark-LV restart."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "description": "draft (default) | list_drafts | install_draft"},
        "request": {"type": "STRING", "description": "Specific capability the plugin should provide"},
        "name": {"type": "STRING", "description": "Optional short plugin/draft name"}}, "required": []},
    "handler": skill_builder,
}