"""
Main AI Agent — orchestrates content generation, scheduling, and publishing
using Claude as the reasoning engine with tool use.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import anthropic
import config
import storage
import scheduler as sched
from platforms import get_available_platforms
from content.generator import ContentGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions exposed to the Claude agent
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "generate_content",
        "description": (
            "Generate platform-optimised social media content for a topic. "
            "Use this to create posts before scheduling or publishing them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The subject of the post"},
                "platform": {
                    "type": "string",
                    "enum": ["twitter", "linkedin", "facebook", "instagram", "bluesky"],
                    "description": "Target platform",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["compound_spotlight", "research_update", "mechanism_explainer",
                             "study_breakdown", "lab_insight", "research_q_and_a",
                             "compound_comparison", "industry_news", "educational", "safety_protocol"],
                    "description": "Style of content to generate",
                },
                "extra_instructions": {
                    "type": "string",
                    "description": "Optional additional instructions for content generation",
                },
            },
            "required": ["topic", "platform"],
        },
    },
    {
        "name": "cross_post_generate",
        "description": "Generate platform-adapted content for multiple platforms at once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "platforms": {
                    "type": "array",
                    "items": {"type": "string",
                              "enum": ["twitter", "linkedin", "facebook", "instagram", "bluesky"]},
                    "description": "List of platforms to generate content for",
                },
                "content_type": {
                    "type": "string",
                    "default": "educational",
                    "enum": ["compound_spotlight", "research_update", "mechanism_explainer",
                             "study_breakdown", "lab_insight", "research_q_and_a",
                             "compound_comparison", "industry_news", "educational", "safety_protocol"],
                },
                "extra_instructions": {"type": "string"},
            },
            "required": ["topic", "platforms"],
        },
    },
    {
        "name": "publish_now",
        "description": "Immediately publish content to a social media platform.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string",
                             "enum": ["twitter", "linkedin", "facebook", "instagram", "bluesky"]},
                "content": {"type": "string", "description": "The text to publish"},
                "topic": {"type": "string", "description": "Topic label for tracking"},
            },
            "required": ["platform", "content", "topic"],
        },
    },
    {
        "name": "schedule_post",
        "description": "Schedule a post for future publishing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "content": {"type": "string"},
                "topic": {"type": "string"},
                "delay_minutes": {
                    "type": "integer",
                    "description": "Minutes from now to publish (0 = immediate next flush)",
                    "default": 60,
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "ISO datetime string (UTC) to override delay_minutes",
                },
            },
            "required": ["platform", "content", "topic"],
        },
    },
    {
        "name": "list_platforms",
        "description": "List all configured and available social media platforms.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_posts",
        "description": "List recent posts from the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Filter by platform"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "posted", "failed", "skipped"],
                    "description": "Filter by status",
                },
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_analytics",
        "description": "Get engagement analytics summary across all platforms.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "content_plan",
        "description": "Generate a content calendar plan with multiple post ideas for a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "num_posts": {"type": "integer", "default": 5},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "flush_scheduled",
        "description": "Manually trigger publishing of all due scheduled posts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "suggest_hashtags",
        "description": "Suggest research-appropriate hashtags for a peptide topic on Instagram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The peptide compound or research topic"},
                "count": {"type": "integer", "default": 12, "description": "Number of hashtags to suggest"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "check_compliance",
        "description": (
            "Review post content for regulatory compliance — checks for medical claims, "
            "human consumption language, or anything that violates research-only rules."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The post text to review"},
            },
            "required": ["content"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def _execute_tool(tool_name: str, tool_input: dict) -> Any:
    generator = ContentGenerator()
    available = get_available_platforms()

    if tool_name == "generate_content":
        content = generator.generate(
            topic=tool_input["topic"],
            platform=tool_input["platform"],
            content_type=tool_input.get("content_type", "educational"),
            extra_instructions=tool_input.get("extra_instructions"),
        )
        return {"platform": tool_input["platform"], "content": content, "char_count": len(content)}

    elif tool_name == "cross_post_generate":
        results = generator.generate_cross_platform(
            topic=tool_input["topic"],
            platforms=tool_input["platforms"],
            content_type=tool_input.get("content_type", "educational"),
            extra_instructions=tool_input.get("extra_instructions"),
        )
        return {
            p: {"content": c, "char_count": len(c)}
            for p, c in results.items()
        }

    elif tool_name == "publish_now":
        platform_name = tool_input["platform"]
        platform = available.get(platform_name)
        if platform is None:
            return {"success": False, "error": f"Platform '{platform_name}' is not configured."}
        result = platform.post(tool_input["content"])
        if result.success:
            post_id = storage.save_post(
                tool_input["topic"], platform_name, tool_input["content"],
                scheduled_at=datetime.utcnow().isoformat(),
            )
            storage.update_post_status(post_id, "posted", platform_post_id=result.platform_post_id)
        return {
            "success": result.success,
            "platform_post_id": result.platform_post_id,
            "url": result.url,
            "error": result.error,
        }

    elif tool_name == "schedule_post":
        post_id = sched.schedule_post(
            topic=tool_input["topic"],
            platform=tool_input["platform"],
            content=tool_input["content"],
            delay_minutes=tool_input.get("delay_minutes", 60),
            scheduled_at=tool_input.get("scheduled_at"),
        )
        return {"post_id": post_id, "status": "scheduled"}

    elif tool_name == "list_platforms":
        return {
            "available": list(available.keys()),
            "all_platforms": ["twitter", "linkedin", "facebook", "instagram", "bluesky"],
        }

    elif tool_name == "list_posts":
        posts = storage.get_posts(
            platform=tool_input.get("platform"),
            status=tool_input.get("status"),
            limit=tool_input.get("limit", 10),
        )
        return {"posts": posts, "count": len(posts)}

    elif tool_name == "get_analytics":
        return {"summary": storage.get_analytics_summary()}

    elif tool_name == "content_plan":
        plan = generator.generate_content_plan(
            topic=tool_input["topic"],
            num_posts=tool_input.get("num_posts", 5),
        )
        return {"plan": plan}

    elif tool_name == "flush_scheduled":
        results = sched.flush_due_posts()
        return {"flushed": len(results), "results": results}

    elif tool_name == "suggest_hashtags":
        tags = generator.suggest_hashtags(
            topic=tool_input["topic"],
            platform="instagram",
            count=tool_input.get("count", 12),
        )
        return {"hashtags": tags, "count": len(tags)}

    elif tool_name == "check_compliance":
        result = generator.check_compliance(tool_input["content"])
        return result

    return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

class SocialMediaAgent:
    """Agentic loop: accepts natural-language commands and executes them via tools."""

    SYSTEM = (
        f"You are an expert AI social media manager for {config.agent.brand_name}, "
        f"a peptide research company. Your primary platform is Instagram.\n"
        f"Brand voice: {config.agent.brand_voice}\n"
        f"Core topics: {config.agent.brand_topics}\n\n"
        "COMPLIANCE (non-negotiable):\n"
        "- All content is for research purposes only — never suggest human consumption\n"
        "- Never make medical claims or dosage recommendations for humans\n"
        "- Always run check_compliance before publishing any post\n"
        "- If compliance check returns issues, fix the content before publishing\n\n"
        "WORKFLOW:\n"
        "- Default platform is instagram unless the user specifies otherwise\n"
        "- Default content_type is compound_spotlight or educational for peptide topics\n"
        "- For any publish or schedule request: generate content → check compliance → publish/schedule\n"
        "- Always use the available tools to complete tasks rather than just describing what to do\n"
        "- After using tools, summarise what was done in clear, concise language"
    )

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=config.agent.anthropic_api_key)
        self._history: list[dict] = []
        storage.init_db()

    def reset(self):
        self._history = []

    def run(self, user_message: str) -> str:
        """Process a single user message through the agentic loop and return the final response."""
        self._history.append({"role": "user", "content": user_message})

        while True:
            response = self._client.messages.create(
                model=config.agent.model,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": self.SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=TOOLS,
                messages=self._history,
            )

            # Collect text and tool-use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            # Append assistant turn (raw blocks) to history
            self._history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn" or not tool_use_blocks:
                # Final text response
                return "\n".join(b.text for b in text_blocks).strip()

            # Execute each tool and build tool_result turn
            tool_results = []
            for block in tool_use_blocks:
                logger.info("Executing tool: %s with %s", block.name, block.input)
                result = _execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    }
                )

            self._history.append({"role": "user", "content": tool_results})


# Module-level convenience instance
_agent: Optional[SocialMediaAgent] = None


def get_agent() -> SocialMediaAgent:
    global _agent
    if _agent is None:
        _agent = SocialMediaAgent()
    return _agent


def chat(message: str) -> str:
    return get_agent().run(message)
