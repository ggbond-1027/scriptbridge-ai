"""模型管理 API - 配置、状态、使用量"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel
import json

from app.config import settings

router = APIRouter()


class TestConnectionRequest(BaseModel):
    """连接测试请求"""
    mode: str = "api"  # api | local
    api_provider: str = "openai"
    api_key: str = ""
    api_base_url: str = ""
    model_name: str = ""
    local_engine: str = "ollama"
    local_base_url: str = ""
    local_model_name: str = ""


def _extract_chat_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    chunks: List[str] = []
    for choice in data.get("choices", []) or []:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        message = choice.get("message") or {}
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            chunks.append(delta["content"])
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            chunks.append(message["content"])
        if isinstance(choice.get("text"), str):
            chunks.append(choice["text"])
    return "".join(chunks)


async def _test_chat_completion(base_url: str, headers: Dict[str, str], model_name: str) -> str:
    import httpx

    if not model_name:
        return ""

    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model_name,
        "messages": [{"role": "user", "content": "只回复两个字：成功"}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        async with client.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code != 200:
                raw = (await response.aread()).decode("utf-8", errors="replace")
                raise RuntimeError(f"chat/completions 返回 {response.status_code}: {raw[:160]}")

            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                raw = (await response.aread()).decode("utf-8", errors="replace")
                try:
                    return _extract_chat_text(json.loads(raw)) or raw
                except json.JSONDecodeError:
                    return raw

            chunks: List[str] = []
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    text = _extract_chat_text(json.loads(payload))
                except json.JSONDecodeError:
                    text = payload
                if text:
                    chunks.append(text)
            return "".join(chunks).strip()


@router.post("/test-connection", summary="测试模型连接")
async def test_connection(req: TestConnectionRequest):
    """从后端代理测试LLM API连接，避免浏览器CORS限制"""
    import httpx
    import asyncio

    base_url = req.api_base_url if req.mode == "api" else req.local_base_url
    api_key = req.api_key if req.mode == "api" else ""

    if not base_url:
        return {
            "status": "failed",
            "error": "未配置 API 地址或本地服务地址",
            "details": "请在模型配置中填写 Base URL",
        }

    headers: Dict[str, str] = {"Content-Type": "application/json"}

    if api_key:
        if req.api_provider == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    # Try /models endpoint (OpenAI-compatible)
    models_url = base_url.rstrip("/")
    if not models_url.endswith("/models"):
        if models_url.endswith("/v1"):
            models_url = f"{models_url}/models"
        else:
            models_url = f"{models_url}/v1/models"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(models_url, headers=headers)

            if response.status_code == 200:
                # Parse model list if available
                try:
                    data = response.json()
                    model_list = []
                    if isinstance(data, dict) and "data" in data:
                        model_list = [m.get("id", "") for m in data.get("data", [])]
                    generation_text = await _test_chat_completion(
                        base_url,
                        headers,
                        req.model_name if req.mode == "api" else req.local_model_name,
                    )
                    return {
                        "status": "connected",
                        "error": None,
                        "details": f"连接成功，可用模型数: {len(model_list)}，生成测试: {generation_text[:20] or '空'}",
                        "available_models": model_list[:20],  # Limit to 20
                    }
                except Exception:
                    return {
                        "status": "connected",
                        "error": None,
                        "details": "连接成功，服务器响应正常",
                        "available_models": [],
                    }
            elif response.status_code == 401:
                return {
                    "status": "failed",
                    "error": "认证失败：API Key 无效或缺失",
                    "details": f"服务器返回 401 Unauthorized",
                }
            elif response.status_code == 404:
                # /models not available but server reachable — still OK
                generation_text = await _test_chat_completion(
                    base_url,
                    headers,
                    req.model_name if req.mode == "api" else req.local_model_name,
                )
                return {
                    "status": "connected",
                    "error": None,
                    "details": f"服务器可达（/models端点不可用），生成测试: {generation_text[:20] or '空'}",
                    "available_models": [],
                }
            else:
                body_text = response.text[:200]
                return {
                    "status": "failed",
                    "error": f"服务器返回错误 {response.status_code}",
                    "details": body_text,
                }
    except httpx.TimeoutException:
        return {
            "status": "failed",
            "error": "连接超时（20秒内未收到响应）",
            "details": "请检查: 1) 地址是否正确 2) 网络是否可达 3) 如在中国大陆请使用代理地址",
        }
    except httpx.ConnectError as e:
        return {
            "status": "failed",
            "error": "无法建立连接",
            "details": f"DNS解析失败或服务器拒绝连接: {str(e)[:100]}。如在中国大陆，api.openai.com需要代理地址",
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": "连接异常",
            "details": str(e)[:200],
        }


@router.get("/config", summary="获取模型配置")
async def get_model_config(request: Request):
    """获取当前模型路由配置"""

    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        from app.core.model_router import ModelRouter
        model_router = ModelRouter(settings)

    config = model_router.get_config_summary()
    models = model_router.get_available_models()

    return {
        "provider_mode": config["provider_mode"],
        "default_model": config["default_model"],
        "available_models": models,
        "total_models_count": config["total_models_count"],
        "available_models_count": config["available_models_count"],
        "task_mapping": config["task_mapping"],
    }


@router.get("/status", summary="获取模型状态")
async def get_model_status(request: Request):
    """获取所有模型的可用状态"""

    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        from app.core.model_router import ModelRouter
        model_router = ModelRouter(settings)

    models = model_router.get_available_models()

    return {
        "models": [
            {
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "tier": m["tier"],
                "available": m["available"],
                "cost_per_1k_input": m["cost_per_1k_input"],
                "cost_per_1k_output": m["cost_per_1k_output"],
                "supports_structured_output": m["supports_structured_output"],
            }
            for m in models
        ],
        "provider_mode": settings.LLM_PROVIDER.value,
    }


@router.get("/usage", summary="获取模型使用统计")
async def get_model_usage(request: Request):
    """获取模型使用量统计"""

    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        from app.core.model_router import ModelRouter
        model_router = ModelRouter(settings)

    models = model_router.get_available_models()

    return {
        "usage_stats": [
            {
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "total_requests": m["total_requests"],
                "total_cost": m["total_cost"],
            }
            for m in models
        ],
        "total_requests": sum(m["total_requests"] for m in models),
        "total_cost": sum(m["total_cost"] for m in models),
    }


@router.patch("/availability/{model_id}", summary="更新模型可用性")
async def update_model_availability(
    model_id: str,
    available: bool,
    request: Request,
):
    """手动启用或禁用指定模型"""

    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        from app.core.model_router import ModelRouter
        model_router = ModelRouter(settings)

    model_router.update_model_availability(model_id, available)

    return {
        "model_id": model_id,
        "available": available,
        "message": f"模型 {model_id} 可用性已更新为 {available}",
    }


@router.get("/tiers", summary="获取模型层级说明")
async def get_model_tiers():
    """获取模型层级说明和推荐"""

    from app.core.model_router import ModelTier, TASK_MODEL_MAPPING, TaskType

    tiers = {
        "premium": {
            "description": "最高质量，成本最高",
            "recommended_for": ["story_bible_merge", "element_generation", "polish_dialogue"],
            "examples": ["GPT-4o", "Claude 3.5 Sonnet"],
        },
        "standard": {
            "description": "平衡质量与成本",
            "recommended_for": ["chapter_understanding", "scene_splitting", "rewrite"],
            "examples": ["DeepSeek-Chat", "GPT-4o-mini", "GLM-4"],
        },
        "economy": {
            "description": "低成本，适合批量处理",
            "recommended_for": ["validation_repair", "本地模型"],
            "examples": ["Ollama本地模型", "vLLM本地模型"],
        },
    }

    mapping = {task.value: tier.value for task, tier in TASK_MODEL_MAPPING.items()}

    return {
        "tiers": tiers,
        "task_model_mapping": mapping,
        "default_mode": settings.LLM_PROVIDER.value,
        "competition_recommendation": {
            "api_mode": "推荐用于竞赛场景，稳定可靠",
            "local_mode": "可选用于成本控制，需要本地部署",
        },
    }
