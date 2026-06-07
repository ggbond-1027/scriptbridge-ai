"""LLMProvider - LLM抽象接口

提供两个核心方法：
1. generateStructured<T>: Schema-first生成，先选Schema再生成
2. rewrite: 局部再生成，含instruction/context/selection
"""

from typing import Any, Dict, Generic, Optional, Type, TypeVar
from dataclasses import dataclass
import json
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.core.model_router import ModelRouter, TaskType, ModelInfo

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class RewriteRequest:
    """局部重写请求"""
    instruction: str           # 重写指令（如"让这段对话更加紧张"）
    context: str               # 上下文文本（周围的场景或段落）
    selection: str             # 需要重写的选中文本
    task_type: TaskType = TaskType.REWRITE
    preserve_structure: bool = True   # 是否保持结构不变


@dataclass
class GenerateResult:
    """生成结果"""
    content: Any
    model_id: str
    input_tokens: int
    output_tokens: int
    success: bool
    error: Optional[str] = None


class LLMProvider:
    """LLM提供者抽象接口"""

    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        self._clients: Dict[str, AsyncOpenAI] = {}
        self._init_clients()

    def _init_clients(self):
        """初始化各提供商的OpenAI兼容客户端"""
        for model_id, model_info in model_router._models.items():
            client = AsyncOpenAI(
                api_key=model_info.api_key,
                base_url=model_info.base_url,
            )
            self._clients[model_id] = client

    async def generate_structured(
        self,
        output_type: Type[T],
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        few_shot_examples: Optional[list] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
        prefer_tier: Optional[str] = None,
        cost_limit: Optional[float] = None,
    ) -> GenerateResult:
        """
        Schema-first生成：先确定输出Schema，再让LLM生成符合Schema的内容

        Args:
            output_type: Pydantic模型类，定义输出结构
            task_type: 任务类型，用于模型路由
            prompt: 用户提示文本
            system_prompt: 系统提示（可选）
            few_shot_examples: 示例列表（可选）
            temperature: 生成温度
            max_retries: 最大重试次数
            prefer_tier: 优先模型层级
            cost_limit: 成本限制

        Returns:
            GenerateResult: 包含生成的结构化数据
        """
        from app.core.model_router import ModelTier

        tier = ModelTier(prefer_tier) if prefer_tier else None
        model_info = self.model_router.route(task_type, prefer_tier=tier, cost_limit=cost_limit)
        model_id = self._get_model_id(model_info)
        client = self._clients.get(model_id)

        if client is None:
            return GenerateResult(
                content=None, model_id=model_id,
                input_tokens=0, output_tokens=0,
                success=False, error=f"未找到模型 {model_id} 的客户端"
            )

        # 构造消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加few-shot示例
        if few_shot_examples:
            for example in few_shot_examples:
                if "input" in example and "output" in example:
                    messages.append({"role": "user", "content": example["input"]})
                    messages.append({"role": "assistant", "content": json.dumps(example["output"], ensure_ascii=False)})

        # 构造Schema提示
        schema = output_type.model_json_schema()
        schema_prompt = f"{prompt}\n\n请严格按照以下JSON Schema格式输出：\n```json\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n```"

        messages.append({"role": "user", "content": schema_prompt})

        # 尝试使用instructor进行结构化输出（如果模型支持）
        if model_info.supports_structured_output:
            try:
                import instructor
                instructor_client = instructor.from_openai(client)
                result = await instructor_client.chat.completions.create(
                    model=model_info.name,
                    response_model=output_type,
                    messages=messages,
                    temperature=temperature,
                    max_retries=max_retries,
                )
                # instructor返回的是Pydantic对象
                input_tokens = 0  # instructor不直接返回token数
                output_tokens = 0
                self.model_router.record_usage(model_id, input_tokens, output_tokens, success=True)
                return GenerateResult(
                    content=result,
                    model_id=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=True,
                )
            except ImportError:
                logger.warning("instructor未安装，回退到普通生成模式")
            except Exception as e:
                logger.warning(f"instructor结构化输出失败，回退: {e}")

        # 回退方案：普通生成 + JSON解析
        for attempt in range(max_retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=model_info.name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=model_info.max_tokens,
                )

                content_text = response.choices[0].message.content
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                # 尝试从回复中提取JSON
                parsed = self._extract_json_from_response(content_text)

                if parsed:
                    # 验证是否符合Schema
                    try:
                        validated = output_type.model_validate(parsed)
                        self.model_router.record_usage(model_id, input_tokens, output_tokens, success=True)
                        return GenerateResult(
                            content=validated,
                            model_id=model_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            success=True,
                        )
                    except Exception as validate_error:
                        logger.warning(f"Schema校验失败 (attempt {attempt+1}): {validate_error}")
                        if attempt < max_retries:
                            # 修复提示
                            messages.append({"role": "assistant", "content": content_text})
                            messages.append({
                                "role": "user",
                                "content": f"输出不符合要求的Schema。错误：{validate_error}。请重新生成符合Schema的JSON。"
                            })
                            continue

                self.model_router.record_usage(model_id, input_tokens, output_tokens, success=False)
                return GenerateResult(
                    content=None,
                    model_id=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=False,
                    error="无法从回复中提取有效的JSON结构",
                )

            except Exception as e:
                logger.error(f"生成失败 (attempt {attempt+1}): {e}")
                self.model_router.record_usage(model_id, 0, 0, success=False)
                if attempt < max_retries:
                    continue
                return GenerateResult(
                    content=None, model_id=model_id,
                    input_tokens=0, output_tokens=0,
                    success=False, error=str(e)
                )

        return GenerateResult(
            content=None, model_id=model_id,
            input_tokens=0, output_tokens=0,
            success=False, error="超过最大重试次数"
        )

    async def rewrite(self, request: RewriteRequest) -> GenerateResult:
        """
        局部再生成：基于instruction/context/selection进行定向改写

        Args:
            request: RewriteRequest对象

        Returns:
            GenerateResult: 包含改写后的文本
        """
        model_info = self.model_router.route(request.task_type)
        model_id = self._get_model_id(model_info)
        client = self._clients.get(model_id)

        if client is None:
            return GenerateResult(
                content=None, model_id=model_id,
                input_tokens=0, output_tokens=0,
                success=False, error=f"未找到模型 {model_id} 的客户端"
            )

        # 构造重写提示
        system_prompt = "你是一个专业的剧本编辑助手。你需要根据用户的指令，对选中的文本进行改写，同时保持与上下文的连贯性。"

        user_prompt = f"""## 改写指令
{request.instruction}

## 上下文
{request.context}

## 需要改写的文本
{request.selection}

请根据改写指令，重新撰写选中的文本。{'保持原有的结构和格式不变。' if request.preserve_structure else '可以调整结构和格式。'}只输出改写后的文本，不要包含任何解释。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await client.chat.completions.create(
                model=model_info.name,
                messages=messages,
                temperature=0.7,
                max_tokens=model_info.max_tokens,
            )

            content_text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            self.model_router.record_usage(model_id, input_tokens, output_tokens, success=True)

            return GenerateResult(
                content=content_text,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=True,
            )

        except Exception as e:
            logger.error(f"重写生成失败: {e}")
            self.model_router.record_usage(model_id, 0, 0, success=False)
            return GenerateResult(
                content=None, model_id=model_id,
                input_tokens=0, output_tokens=0,
                success=False, error=str(e)
            )

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """从LLM回复中提取JSON内容"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从markdown代码块中提取
        import re
        json_pattern = re.compile(r'```(?:json)?\s*\n(.*?)\n```', re.DOTALL)
        match = json_pattern.search(text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到最外层的大括号
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _get_model_id(self, model_info: ModelInfo) -> str:
        """根据ModelInfo获取内部模型ID"""
        for id, m in self.model_router._models.items():
            if m.name == model_info.name and m.provider == model_info.provider:
                return id
        return f"{model_info.provider}/{model_info.name}"