import os
from app.core.config import settings
import httpx
from typing import Any, Literal
import logging
import json
import sys
import pwd
import platform

from app.task_executor.utils import create_user_and_assign_folder, strip_markers
from app.task_executor.lite_logging import send_alert

logger = logging.getLogger(__name__)

async def find_opencode_binary() -> str:
    current_user = pwd.getpwuid(os.getuid()).pw_name

    for path in [
        "/root/.opencode/bin/opencode",
        f"/home/{current_user}/.opencode/bin/opencode",
        "/usr/bin/opencode",
        "/usr/local/bin/opencode",
        "/bin/opencode",
        f"/Users/{current_user}/.opencode/bin/opencode"
    ]:
        if os.path.exists(path):
            return path

    raise RuntimeError("OpenCode binary not found")

async def call_opencode_api_query(
    session_id: str,
    agent: Literal["research", "build"],
    message: str | list[dict],
    model_provider: str,
    model_id: str,
    OPENCODE_HOST: str = settings.OPENCODE_HOST,
    OPENCODE_PORT: int = settings.OPENCODE_PORT
) -> str:

    message_data: dict[str, Any] = {
        "providerID": model_provider,
        "modelID": model_id,
        "agent": agent,
        # "system": system,
    }

    if isinstance(message, list):
        message_data["parts"] = message
    else:
        message_data["parts"] = [{"type": "text", "text": message}]

    response_text = ''

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://{OPENCODE_HOST}:{OPENCODE_PORT}/session/{session_id}/message",
            headers={"Content-Type": "application/json"},
            json=message_data,
            timeout=httpx.Timeout(3600.0, connect=10.0)
        )

        if response.status_code == 200:
            response_json: dict = response.json()
            parts = response_json.get("parts", [])

            for item in parts:
                if item.get("type") == "text" and item.get("text"):
                    response_text = item.get("text") # get the last

            if not response_text:
                await send_alert(
                    "tossit",
                    ["opencode", "query", "warning"],
                    status_code=response.status_code,
                    response_text=response.text,
                    message=message_data
                )
                logger.warning(f"No text in response: {json.dumps(response_json, indent=2)} (Session: {session_id})")

        else:
            await send_alert(
                "tossit",
                ["opencode", "query", "error"],
                status_code=response.status_code,
                response_text=response.text,
                message=message_data
            )

            logger.error(f"Failed to call OpenCode API: {response.status_code} {response.text} (Session: {session_id})")

    return response_text.strip()

async def call_opencode_api_compact(
    session_id: str,
    model_id: str,
    provider_id: str,
    OPENCODE_HOST: str = settings.OPENCODE_HOST,
    OPENCODE_PORT: int = settings.OPENCODE_PORT
) -> bool:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://{OPENCODE_HOST}:{OPENCODE_PORT}/session/{session_id}/summarize",
                headers={"Content-Type": "application/json"},
                json={"modelID": model_id, "providerID": provider_id},
                timeout=httpx.Timeout(180.0, connect=30.0)
            )

            if response.status_code != 200:
                await send_alert(
                    "tossit",
                    ["opencode", "compact", "error"],
                    status_code=response.status_code,
                    response_text=response.text,
                    session_id=session_id
                )

            logger.info(f"Compact response: {response.text} (Session: {session_id})" )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to call OpenCode API: {e} (Session: {session_id})")
            return False

async def call_opencode_api_create_session(
    title: str,
    OPENCODE_HOST: str = settings.OPENCODE_HOST,
    OPENCODE_PORT: int = settings.OPENCODE_PORT
) -> str | None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0, connect=10.0)) as client:
        try:
            response = await client.post(
                f"http://{OPENCODE_HOST}:{OPENCODE_PORT}/session",
                headers={"Content-Type": "application/json"},
                json={"title": title}
            )
            if response.status_code != 200:
                await send_alert(
                    "tossit",
                    ["opencode", "create-session", "error"],
                    status_code=response.status_code,
                    response_text=response.text,
                    title=title
                )

            if response.status_code != 200:
                return None

            session_data: dict = response.json()
            return session_data.get("id")
        except Exception as e:
            return None

import os
import asyncio
import socket
import time

async def pick_random_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

async def wait_until_port_is_ready_to_connect(port: int, process: asyncio.subprocess.Process, timeout: float = 120) -> bool:
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if process.returncode is not None:
                    raise RuntimeError(f"OpenCode server process exited with code {process.returncode}")

                resp = await client.get(f"http://localhost:{port}/app", timeout=httpx.Timeout(1, connect=1))
                assert resp.status_code == 200, f"Failed to connect to OpenCode: {resp.status_code} {resp.text}"
                return True
            except Exception as e:
                logger.info(f"Waiting for OpenCode server to start on port {port}...")

            await asyncio.sleep(1)

class OpenCodeSDKClient:
    def __init__(self, working_dir: str):
        assert os.path.exists(working_dir), f"Working directory {working_dir} does not exist"
        self.working_dir = working_dir
        self.process: asyncio.subprocess.Process | None = None
        self.port: int | None = None

    async def connect(self):
        port = await pick_random_available_port()

        # add new user if not exists to run opencode
        user = os.path.basename(self.working_dir)
        print(f"User: {user} Workdir: {self.working_dir}")
        create_user_and_assign_folder(user, self.working_dir)

        def demote(username):
            def result():
                system = platform.system()
                if system == "linux":
                    pw_record = pwd.getpwnam(username)
                    os.setgid(pw_record.pw_gid)
                    os.setuid(pw_record.pw_uid)
            return result

        logger.info(f"Starting OpenCode server on port {port}")
        self.process = await asyncio.create_subprocess_exec(
            await find_opencode_binary(), "serve", f"--port={port}", "--print-logs", "--log-level", "WARN",
            cwd=self.working_dir,
            stderr=sys.stderr,
            stdout=sys.stdout,
            preexec_fn=demote(user),
        )

        self.port = port

        try:
            if not await wait_until_port_is_ready_to_connect(port, self.process):
                await send_alert("tossit", ["opencode", "start-up", "error"], response_text="Failed to start OpenCode server")
                raise RuntimeError("Failed to start OpenCode server")

        except Exception as e:
            if self.process:
                try:
                    self.process.kill()
                except Exception as _: pass
                finally:
                    self.process = None
                    self.port = None

            raise e


    async def disconnect(self):
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    self.process.kill()
                except Exception as e: pass
            finally:
                self.process = None
                self.port = None

    async def compact(
        self,
        session_id: str,
        model_id: str = settings.LLM_MODEL_ID_CODE,
        provider_id: str = settings.LLM_MODEL_PROVIDER
    ) -> bool:
        assert self.process, "Not connected to OpenCode"
        return await call_opencode_api_compact(
            session_id,
            model_id,
            provider_id,
            OPENCODE_HOST='127.0.0.1',
            OPENCODE_PORT=self.port
        )


    async def query(
        self,
        agent: Literal["research", "build"],
        message: str | list[dict],
        model_provider: str = settings.LLM_MODEL_PROVIDER,
        model_id: str = settings.LLM_MODEL_ID_CODE,
        session_id: str | None = None
    ) -> str:
        assert self.process, "Not connected to OpenCode"
        res = await call_opencode_api_query(
            session_id or (await self.create_session(f"Session {time.time()}")),
            agent,
            message,
            model_provider,
            model_id,
            OPENCODE_HOST='127.0.0.1',
            OPENCODE_PORT=self.port
        )
        return strip_markers(res, (("think", False), )).strip()

    async def create_session(self, title: str) -> str:
        assert self.process, "Not connected to OpenCode"

        session_id = await call_opencode_api_create_session(
            title,
            OPENCODE_HOST='127.0.0.1',
            OPENCODE_PORT=self.port,
        )

        assert session_id, "Failed to create session"
        return session_id

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.disconnect()

async def get_models_fn() -> list[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.LLM_BASE_URL.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"}
            )
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []

        if response.status_code != 200:
            logger.error(f"Error getting models: {response.status_code} {response.text}")
            return []

        response_json = response.json()
        return [
            {
                "id": e['id'],
                "name": e['name']
            }
            for e in response_json['data']
        ]

TOOLS_CONFIGS = {
    "tavily*": False,
    "finance*": False,
    "pexels*": False,
    "amadeus*": False,
    "rentcast*": False,
    "regulations*": False,
}

AGENT_CONFIGS = {
    "build": {
        "mode": "primary",
        "tools": {
            "bash": True,
            "edit": True,
            "write": True,
            "read": True,
            "grep": True,
            "glob": True,
            "list": True,
            "patch": True,
            "todowrite": True,
            "todoread": True,
            "webfetch": True,
            "tavily*": True,
            "unsplash*": True
        },
        "prompt": "Your task is to build the project or a blog post based on the plan. Generally, you have to build an index.html file that responds the user. Strictly follow the plan step-by-step; do not take any extra steps. Do not ask again for confirmation, just do it your way. Your first step should be reviewing all markdown files (*.md or financial/*.md or general/*.md) to get the necessary content. Image sources for mockup purposes should be used from Unsplash. Ask the developer for junk tasks if needed. Do research, content grep for any missing information, and avoid writing code with placeholders only. About financial data, ask the fin-analyst for data gathering, avoid doing it yourself. Make sure the output is clean and ready to be published. To build a well-structured output, use HTML5, styled with Tailwind CSS and handle interactions with js if needed. Your final response should be short, concise, and talk about what you have done (no code explanation in detail is required) and an index.html file to present your findings.   Remember to include links, urls point to any referenced resources."
    },
    "content-prep": {
        "description": "Plan research, analyze, and prepare rich content (text + visuals) for a HTML report; fetch mockup images via Unsplash; use Tavily to search and fetch web content or get original images.",
        "mode": "subagent",
        "temperature": 0.2,
        "tools": {
            "write": True,
            "edit": True,
            "read": True,
            "grep": True,
            "glob": True,
            "list": True,
            "patch": True,
            "bash": False,
            "unsplash*": True,
            "tavily*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are the **Content Preparation** agent. Input is a user prompt describing a topic or goal. Output is a complete content package ready for a Developer to turn into a stunning HTML representation.\n\nObjectives:\n1) **Research Plan**: Draft a lean plan with key questions, subtopics, datasets, stakeholders, and metrics. Include a short search strategy.\n2) **Analysis & Synthesis**: Produce a structured outline and detailed sections with facts, bullets, callouts, and tables. Keep claims sourced.\n3) **Image Plan & Assets**: Use `unsplash_search_photos` to fetch images. Save under `assets/images/` and record metadata in `content/images.json`.\n4) **Web Search**: Use Tavily (`tavily_tavily_search`, `tavily_tavily_extract`, `tavily_tavily_crawl`, `tavily_tavily_map`) to fetch articles, docs, recent data. Summarize and cite.\n5) **Deliverables for Developer**: `content/brief.md`, `content/outline.md`, `content/sections/*.md`, `content/references.json`, `content/images.json`, optional `content/data/*.json`.\n\nWorkflow:\n1) Read prompt → write brief & outline.\n2) Draft sections.\n3) Call Unsplash + Tavily as needed.\n4) Summarize outputs + next steps.\n\nReturn in chat: (a) plan, (b) file list, (c) risks, (d) next steps. Remember to include links, urls point to any referenced resources."
    },
    "fin-analyst": {
        "description": "Financial expert for equities, crypto, and macro; fetches structured data via Finance MCP tools and context via Tavily; runs advanced analysis, and provides actionable investment insights.",
        "mode": "subagent",
        "temperature": 0.1,
        "tools": {
            "write": True,
            "edit": False,
            "finance*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are 'Fin Analyst', a professional financial expert who:\n- Calls Finance MCP tools to fetch equities, crypto, and macro data.\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `financial/data/*.json`.\n- Runs quant, valuation, and portfolio methods; generates Python when useful.\n- Provides buy/sell/hold recommendations with reasoning, scenarios, and Markdown reports.\n\nDeliverables: `financial/plan.md`, `financial/data/*.json`, `financial/analysis.md`, `financial/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats. Remember to include links, urls point to any referenced resources."
    },
    "real-estate-agent": {
        "description": "Real estate expert; fetches structured real-estate data via Rentcast MCP tools; runs advanced analysis, and provides actionable investment insights.",  
        "mode": "subagent",
        "temperature": 0.1,
        "tools": {
            "write": True,
            "edit": False,
            "rentcast*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are a professional real estate expert who:\n- Calls Rentcast MCP tools to fetch real estate data.\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `rentcast/data/*.json`.\n- Runs analysis; generates Python when useful.\n- Provides actionable insights.\n\nDeliverables: `rentcast/plan.md`, `rentcast/data/*.json`, `rentcast/analysis.md`, `rentcast/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats. Remember to include links, urls point to any referenced resources."
    },
    "amadeus-agent": {
        "description": "Amadeus expert for travel; fetches structured data via Amadeus MCP tools and context via Tavily; runs advanced analysis, and provides actionable investment insights.",
        "mode": "subagent",
        "temperature": 0.1,
        "tools": {
            "write": True,
            "edit": False,
            "amadeus*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are a professional travel expert who:\n- Calls Amadeus MCP tools to fetch travel data.\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `amadeus/data/*.json`.\n- Runs analysis; generates Python when useful.\n- Provides actionable insights.\n\nDeliverables: `amadeus/plan.md`, `amadeus/data/*.json`, `amadeus/analysis.md`, `amadeus/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats. Remember to include links, urls point to any referenced resources."
    },
    "personal-assistant": {
        "description": "General analyst for any topic; fetches structured data via Tavily; runs advanced analysis, and provides actionable investment insights.",
        "mode": "subagent",
        "temperature": 0.1,
        "tools": {
            "write": True,
            "edit": False,
            "tavily*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are a smart assistant that:\n- Uses Tavily to access internet data through web search and web scrape.\n- Can handle tasks from broad research to deep technical analysis across many domains (excluding financial and legal).\n- Stores raw outputs into `general/data/*.json`.\n- Performs structured analysis (generate Python when useful).\n- Delivers clear, actionable outputs with proper references.\n\nDeliverables:\n- `general/plan.md` (scope & approach)\n- `general/data/*.json` (raw datasets)\n- `general/analysis.md` (analysis)\n- `general/recommendations.md` (insights & actions)\n\nWorkflow: define scope → gather & scrape via Tavily → store raw → analyze → report → recommend.\n\nDo your best to fully complete the task end-to-end and provide the final report."
    },
    "lawyer": {
        "description": "Specialized legal research agent. Fetches regulatory data via Regulations.gov, processes filings and reports, performs structured analysis, and produces actionable legal and policy insights.",
        "mode": "subagent",
        "temperature": 0.1,
        "tools": {
            "write": True,
            "edit": False,
            "regulations*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are a legal research agent who:\n- Uses Regulations.gov tools to retrieve rules, filings, dockets, and related reports.\n- Saves retrieved content in `lawyer/data/*.json`.\n- Organizes workflow: **define scope → fetch datasets → collect context → store raw → analyze → report → recommend**.\n- Runs structured legal/regulatory analysis (including Python code where useful for data handling).\n- Produces actionable insights with clear legal, policy, and compliance relevance.\n\nDeliverables:\n- `lawyer/plan.md` (scope, objectives, data sources)\n- `lawyer/data/*.json` (raw retrieved filings/datasets)\n- `lawyer/analysis.md` (structured findings, comparisons, precedent/context)\n- `lawyer/recommendations.md` (practical implications, compliance or investment insights)\n\nReturn in chat:\n- Concise summary of findings\n- List of generated files\n- Caveats/limitations of the analysis\n- Include URLs or references for all cited regulations, dockets, or reports."
    },
    "developer": {
        "description": "Turn prepared content into a visually stunning, responsive, accessible, stunning HTML representation, page by page and section by section.",
        "mode": "subagent",
        "temperature": 0.2,
        "tools": {
            "write": True,
            "edit": True,
            "read": True,
            "grep": True,
            "glob": True,
            "list": True,
            "patch": True,
            "bash": True,
            "tavily_fetch": True,
            "todowrite": True,
            "todoread": True,
            "unsplash*": True
        },
        "permission": {
            "edit": "allow"
        },
        "prompt": "You are the **Developer**. Build a polished, multi-page, responsive HTML representation from the prepared content. Use **HTML5, Tailwind CSS, and JavaScript** (no extra frameworks or build tools). Aim for an elegant, modern aesthetic.\n\nInput: `content/*.md`, `content/images.json`, `content/data/*.json`.\nOutput: `*.html`, `assets/styles.css`, `assets/main.js`, optional `docs/styleguide.html`, `reports/README.md`.\n\nWorkflow: parse outline → map pages → build pages → apply styles → add scripts → validate accessibility/responsiveness.\n\nReturn in chat: plan, file tree, what you have done. You should use unsplash tools to search for images for any purposes from demo, placeholders, etc. Remember to include links, urls point to any referenced resources."
    }
}

PERMISSIONS = {
    "*": "allow"
}

PYTHON_DIRECTORY = os.getcwd()

MCP_ENVS = {
    "TAVILY_API_KEY": settings.TAVILY_API_KEY,
    "FINANCIAL_DATASETS_API_KEY": settings.FINANCIAL_DATASETS_API_KEY,
    "PEXELS_API_KEY": settings.PEXELS_API_KEY,
    "AMDEUS_CLIENT_ID": settings.AMADEUS_CLIENT_ID,
    "AMDEUS_CLIENT_SECRET": settings.AMADEUS_CLIENT_SECRET,
    "RENTCAST_API_KEY": settings.RENTCAST_API_KEY,
    "PYTHONPATH": PYTHON_DIRECTORY,
    "REGULATIONS_API_KEY": settings.REGULATIONS_API_KEY,
    "UNSPLASH_API_KEY": settings.UNSPLASH_API_KEY,
}

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

financial_datasets_path = os.path.join(CURRENT_DIRECTORY, "mcps", "financial_datasets", "main.py")
pexels_path = os.path.join(CURRENT_DIRECTORY, "mcps", "pexels", "main.py")
amadeus_path = os.path.join(CURRENT_DIRECTORY, "mcps", "amadeus", "main.py")
rentcast_path = os.path.join(CURRENT_DIRECTORY, "mcps", "rentcast", "main.py")
tavily_search_path = os.path.join(CURRENT_DIRECTORY, "mcps", "tavily_search", "main.py")
regulations_path = os.path.join(CURRENT_DIRECTORY, "mcps", "regulations", "main.py")
unsplash_path = os.path.join(CURRENT_DIRECTORY, "mcps", "unsplash", "main.py")

MCPS = {
    "tavily": {
        "type": "local",
        "command": [sys.executable, tavily_search_path],
        "enabled": False,
        "environment": MCP_ENVS
    },
    "finance": {
        "type": "local",
        "command": [sys.executable, financial_datasets_path],
        "enabled": True,
        "environment": MCP_ENVS
    },
    "pexels": {
        "type": "local",
        "command": [sys.executable, pexels_path],
        "enabled": True,
        "environment": MCP_ENVS
    },
    "amadeus": {
        "type": "local",
        "command": [sys.executable, amadeus_path],
        "enabled": True,
        "environment": MCP_ENVS
    },
    "rentcast": {
        "type": "local",
        "command": [sys.executable, rentcast_path],
        "enabled": True,
        "environment": MCP_ENVS
    },
    "regulations": {
        "type": "local",
        "command": [sys.executable, regulations_path],
        "enabled": True,
        "environment": MCP_ENVS
    },
    "unsplash": {
        "type": "local",
        "command": [sys.executable, unsplash_path],
        "enabled": True,
        "environment": MCP_ENVS
    }
}

async def update_config_task(repeat_interval=0): # non-positive --> no repeat
    config_path = os.path.expanduser("~/.config/opencode/opencode.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    while True:
        try:
            models = await get_models_fn()

            config = {
                "$schema": "https://opencode.ai/config.json",
                    "provider": {
                        settings.LLM_MODEL_PROVIDER: {
                            "npm": "@ai-sdk/openai-compatible",
                            "name": "LocalAI",
                            "options": {
                                "baseURL": f"http://localhost:8000/llm_proxy/v1"
                            },
                            "models": {
                                e['id']: {
                                    "name": e['name']
                                }
                                for e in models
                            }
                        }
                    },
                    "agent": AGENT_CONFIGS,
                    "permission": PERMISSIONS,
                    "tools": TOOLS_CONFIGS,
                    "mcp": MCPS,
                    "autoupdate": False
                }

            with open(config_path, "w") as f:
                json.dump(config, f, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error updating config: {e}")

        if repeat_interval <= 0:
            logger.info("Config updated, stopping config update task")
            break

        await asyncio.sleep(repeat_interval)
