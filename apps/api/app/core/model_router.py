"""ModelRouter - 模型路由器

根据任务类型、成本、可用性自动选择最优LLM模型。
支持API模式（OpenAI/DeepSeek/GLM/Claude）和本地模式（Ollama/vLLM）。
"""

from typing import Dict, List, Optional, Any, Literal
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

from app.config import Settings, LLMProviderMode

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """模型层级"""
    PREMIUM = "premium"     # 最高质量，成本最高（如 GPT-4o, Claude 3.5）
    STANDARD = "standard"   # 平衡质量与成本（如 DeepSeek, GPT-4o-mini）
    ECONOMY = "economy"     # 低成本，适合批量处理（如 本地模型, GPT-3.5）


class TaskType(str, Enum):
    """任务类型"""
    CHAPTER_UNDERSTANDING = "chapter_understanding"
    STORY_BIBLE_MERGE = "story_bible_merge"
    SCENE_SPLITTING = "scene_splitting"
    ELEMENT_GENERATION = "element_generation"
    POLISH_DIALOGUE = "polish_dialogue"
    REWRITE = "rewrite"
    VALIDATION_REPAIR = "validation_repair"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    provider: str
    tier: ModelTier
    base_url: str
    api_key: str
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    supports_structured_output: bool = True
    supports_function_calling: bool = True
    available: bool = True
    last_checked: Optional[datetime] = None


# 任务类型到推荐模型层级的映射
TASK_MODEL_MAPPING: Dict[TaskType, ModelTier] = {
    TaskType.CHAPTER_UNDERSTANDING: ModelTier.STANDARD,    # 理解阶段不需要最强模型
    TaskType.STORY_BIBLE_MERGE: ModelTier.PREMIUM,        # 合并归一化需要高质量推理
    TaskType.SCENE_SPLITTING: ModelTier.STANDARD,         # 场景拆分中等难度
    TaskType.ELEMENT_GENERATION: ModelTier.PREMIUM,       # 剧本元素生成是核心任务
    TaskType.POLISH_DIALOGUE: ModelTier.PREMIUM,          # 润色需要高质量
    TaskType.REWRITE: ModelTier.STANDARD,                 # 局部改写中等难度
    TaskType.VALIDATION_REPAIR: ModelTier.ECONOMY,        # 修复可用低成本模型
}


class ModelRouter:
    """模型路由器 - 根据任务类型和可用性自动选择最优模型"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._models: Dict[str, ModelInfo] = {}
        self._usage_stats: Dict[str, Dict[str, Any]] = {}
        self._init_models()

    def _init_models(self):
        """初始化可用模型列表"""
        s = self.settings

        # OpenAI系列
        if s.OPENAI_API_KEY:
            self._models["openai/gpt-4o"] = ModelInfo(
                name="gpt-4o",
                provider="openai",
                tier=ModelTier.PREMIUM,
                base_url=s.OPENAI_BASE_URL,
                api_key=s.OPENAI_API_KEY,
                max_tokens=4096,
                cost_per_1k_input=0.005,
                cost_per_1k_output=0.015,
                supports_structured_output=True,
                supports_function_calling=True,
            )
            self._models["openai/gpt-4o-mini"] = ModelInfo(
                name="gpt-4o-mini",
                provider="openai",
                tier=ModelTier.STANDARD,
                base_url=s.OPENAI_BASE_URL,
                api_key=s.OPENAI_API_KEY,
                max_tokens=4096,
                cost_per_1k_input=0.00015,
                cost_per_1k_output=0.0006,
                supports_structured_output=True,
                supports_function_calling=True,
            )

        # DeepSeek系列
        if s.DEEPSEEK_API_KEY:
            self._models["deepseek/deepseek-chat"] = ModelInfo(
                name="deepseek-chat",
                provider="deepseek",
                tier=ModelTier.STANDARD,
                base_url=s.DEEPSEEK_BASE_URL,
                api_key=s.DEEPSEEK_API_KEY,
                max_tokens=4096,
                cost_per_1k_input=0.00014,
                cost_per_1k_output=0.00028,
                supports_structured_output=True,
                supports_function_calling=True,
            )

        # GLM系列
        if s.GLM_API_KEY:
            self._models["glm/glm-4"] = ModelInfo(
                name="glm-4",
                provider="glm",
                tier=ModelTier.STANDARD,
                base_url=s.GLM_BASE_URL,
                api_key=s.GLM_API_KEY,
                max_tokens=4096,
                cost_per_1k_input=0.001,
                cost_per_1k_output=0.001,
                supports_structured_output=True,
                supports_function_calling=True,
            )

        # Claude系列
        if s.CLAUDE_API_KEY:
            self._models["claude/claude-3.5-sonnet"] = ModelInfo(
                name="claude-3-5-sonnet-20241022",
                provider="claude",
                tier=ModelTier.PREMIUM,
                base_url=s.CLAUDE_BASE_URL,
                api_key=s.CLAUDE_API_KEY,
                max_tokens=4096,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
                supports_structured_output=True,
                supports_function_calling=True,
            )

        # 本地模型 - Ollama
        if s.LLM_PROVIDER == LLMProviderMode.LOCAL:
            self._models["local/ollama"] = ModelInfo(
                name=s.LOCAL_LLM_MODEL,
                provider="ollama",
                tier=ModelTier.ECONOMY,
                base_url=s.LOCAL_LLM_BASE_URL,
                api_key="ollama",  # Ollama不需要API Key
                max_tokens=4096,
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                supports_structured_output=False,
                supports_function_calling=False,
            )

        # 本地模型 - vLLM
        if s.LLM_PROVIDER == LLMProviderMode.LOCAL and s.VLLM_BASE_URL:
            self._models["local/vllm"] = ModelInfo(
                name=s.VLLM_MODEL,
                provider="vllm",
                tier=ModelTier.ECONOMY,
                base_url=s.VLLM_BASE_URL,
                api_key="vllm",
                max_tokens=4096,
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                supports_structured_output=False,
                supports_function_calling=False,
            )

        # 为每个模型初始化使用统计
        for model_id in self._models:
            self._usage_stats[model_id] = {
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "last_used": None,
                "error_count": 0,
            }

    def route(
        self,
        task_type: TaskType,
        prefer_tier: Optional[ModelTier] = None,
        cost_limit: Optional[float] = None,
        exclude_models: Optional[List[str]] = None,
    ) -> ModelInfo:
        """
        根据任务类型自动路由到最优模型

        Args:
            task_type: 任务类型
            prefer_tier: 优先使用的模型层级（覆盖默认映射）
            cost_limit: 单次请求成本限制（USD）
            exclude_models: 排除的模型ID列表

        Returns:
            ModelInfo: 选中的模型信息
        """
        # 确定目标层级
        target_tier = prefer_tier or TASK_MODEL_MAPPING.get(task_type, ModelTier.STANDARD)

        # 排除指定模型
        exclude = set(exclude_models or [])

        # 本地模式下只选本地模型
        if self.settings.LLM_PROVIDER == LLMProviderMode.LOCAL:
            local_candidates = [
                m for id, m in self._models.items()
                if m.provider in ("ollama", "vllm")
                and id not in exclude
                and m.available
            ]
            if local_candidates:
                # 优先Ollama
                ollama_models = [m for m in local_candidates if m.provider == "ollama"]
                selected = ollama_models[0] if ollama_models else local_candidates[0]
                self._record_selection(selected)
                return selected
            logger.warning("本地模式下无可用本地模型，将尝试API模型")

        # API模式：按层级筛选
        tier_order = self._get_tier_order(target_tier)

        for tier in tier_order:
            candidates = [
                m for id, m in self._models.items()
                if m.tier == tier
                and id not in exclude
                and m.available
            ]

            # 应用成本限制
            if cost_limit is not None:
                candidates = [m for m in candidates if m.cost_per_1k_input * 2 <= cost_limit]

            if candidates:
                # 选择错误率最低的模型
                selected = min(
                    candidates,
                    key=lambda m: self._usage_stats.get(self._get_model_id(m), {}).get("error_count", 0)
                )
                self._record_selection(selected)
                return selected

        # 兜底：返回任何可用模型
        fallback = [
            m for id, m in self._models.items()
            if id not in exclude and m.available
        ]
        if fallback:
            selected = fallback[0]
            self._record_selection(selected)
            return selected

        raise RuntimeError(f"没有可用的模型来处理任务: {task_type}")

    def _get_tier_order(self, target_tier: ModelTier) -> List[ModelTier]:
        """获取层级优先顺序，从目标层级开始向下"""
        tier_priority = {
            ModelTier.PREMIUM: [ModelTier.PREMIUM, ModelTier.STANDARD, ModelTier.ECONOMY],
            ModelTier.STANDARD: [ModelTier.STANDARD, ModelTier.ECONOMY, ModelTier.PREMIUM],
            ModelTier.ECONOMY: [ModelTier.ECONOMY, ModelTier.STANDARD, ModelTier.PREMIUM],
        }
        return tier_priority.get(target_tier, [ModelTier.STANDARD, ModelTier.ECONOMY, ModelTier.PREMIUM])

    def _get_model_id(self, model: ModelInfo) -> str:
        """根据ModelInfo获取内部模型ID"""
        for id, m in self._models.items():
            if m.name == model.name and m.provider == model.provider:
                return id
        return f"{model.provider}/{model.name}"

    def _record_selection(self, model: ModelInfo):
        """记录模型选择"""
        model_id = self._get_model_id(model)
        logger.info(f"ModelRouter: 为任务选择模型 {model_id} (tier={model.tier}, provider={model.provider})")

    def record_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        success: bool = True,
    ):
        """记录模型使用情况"""
        stats = self._usage_stats.get(model_id, {})
        stats["total_requests"] += 1
        stats["total_input_tokens"] += input_tokens
        stats["total_output_tokens"] += output_tokens
        stats["last_used"] = datetime.now()

        model = self._models.get(model_id)
        if model:
            cost = (input_tokens / 1000 * model.cost_per_1k_input) + (output_tokens / 1000 * model.cost_per_1k_output)
            stats["total_cost"] += cost

        if not success:
            stats["error_count"] += 1
            # 连续3次错误则标记不可用
            if stats.get("consecutive_errors", 0) >= 3:
                if model:
                    model.available = False
                    logger.warning(f"模型 {model_id} 连续失败3次，已标记为不可用")

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取所有可用模型列表"""
        result = []
        for model_id, model in self._models.items():
            stats = self._usage_stats.get(model_id, {})
            result.append({
                "id": model_id,
                "name": model.name,
                "provider": model.provider,
                "tier": model.tier.value,
                "available": model.available,
                "cost_per_1k_input": model.cost_per_1k_input,
                "cost_per_1k_output": model.cost_per_1k_output,
                "supports_structured_output": model.supports_structured_output,
                "total_requests": stats.get("total_requests", 0),
                "total_cost": stats.get("total_cost", 0.0),
            })
        return result

    def get_task_model_mapping(self) -> Dict[str, str]:
        """获取任务-模型层级映射"""
        return {task.value: tier.value for task, tier in TASK_MODEL_MAPPING.items()}

    def update_model_availability(self, model_id: str, available: bool):
        """手动更新模型可用性"""
        if model_id in self._models:
            self._models[model_id].available = available
            self._models[model_id].last_checked = datetime.now()
            logger.info(f"模型 {model_id} 可用性更新为: {available}")

    def get_model_for_task(self, task_type: TaskType) -> ModelInfo:
        """快捷方法：获取指定任务类型的推荐模型"""
        return self.route(task_type)

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "provider_mode": self.settings.LLM_PROVIDER.value,
            "available_models_count": len([m for m in self._models.values() if m.available]),
            "total_models_count": len(self._models),
            "default_model": self.settings.MODEL_NAME,
            "task_mapping": self.get_task_model_mapping(),
        }