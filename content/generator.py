"""AI content generator powered by Claude with prompt caching."""
from typing import Optional
import anthropic
import config
from .templates import PLATFORM_PROMPTS, CONTENT_TYPES, COMPLIANCE_RULES, INSTAGRAM_HASHTAG_SETS


class ContentGenerator:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=config.agent.anthropic_api_key)

    def _build_system(self, platform: str) -> str:
        platform_prompt = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["instagram"])
        return (
            f"You are an expert social media manager for {config.agent.brand_name}, "
            f"a peptide research company.\n"
            f"Brand voice: {config.agent.brand_voice}\n"
            f"Core topics: {config.agent.brand_topics}\n\n"
            f"Platform-specific rules for {platform.capitalize()}:\n{platform_prompt}\n\n"
            f"{COMPLIANCE_RULES}\n\n"
            "Return ONLY the post text. No labels, no explanations, no quotes around the output."
        )

    def generate(
        self,
        topic: str,
        platform: str,
        content_type: str = "educational",
        extra_instructions: Optional[str] = None,
        existing_content: Optional[str] = None,
    ) -> str:
        """Generate platform-optimised content for a given topic."""
        content_brief = CONTENT_TYPES.get(content_type, CONTENT_TYPES["educational"]).format(topic=topic)

        user_parts = [f"Create a {content_type} post about: {topic}\n\nContent brief: {content_brief}"]
        if existing_content:
            user_parts.append(f"\nAdapt this existing content for {platform}:\n{existing_content}")
        if extra_instructions:
            user_parts.append(f"\nAdditional instructions: {extra_instructions}")

        response = self._client.messages.create(
            model=config.agent.model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": self._build_system(platform),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": "\n".join(user_parts)}],
        )
        return response.content[0].text.strip()

    def generate_cross_platform(
        self,
        topic: str,
        platforms: list[str],
        content_type: str = "educational",
        extra_instructions: Optional[str] = None,
    ) -> dict[str, str]:
        """Generate platform-specific versions of the same post — Instagram first as the anchor."""
        results: dict[str, str] = {}

        # Prefer Instagram as anchor since that's the primary platform
        anchor_platform = next(
            (p for p in ["instagram", "linkedin", "facebook"] if p in platforms),
            platforms[0],
        )
        anchor_content = self.generate(topic, anchor_platform, content_type, extra_instructions)
        results[anchor_platform] = anchor_content

        for platform in platforms:
            if platform == anchor_platform:
                continue
            results[platform] = self.generate(
                topic,
                platform,
                content_type,
                extra_instructions,
                existing_content=anchor_content,
            )
        return results

    def generate_content_plan(self, topic: str, num_posts: int = 5) -> list[dict]:
        """Ask Claude to build a content calendar plan for the peptide research account."""
        response = self._client.messages.create(
            model=config.agent.model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": (
                        f"You are an expert social media strategist for {config.agent.brand_name}, "
                        f"a peptide research company focused on Instagram.\n"
                        f"Brand voice: {config.agent.brand_voice}\n"
                        f"Core topics: {config.agent.brand_topics}\n\n"
                        f"{COMPLIANCE_RULES}"
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Create a content plan with {num_posts} Instagram post ideas about '{topic}'.\n"
                        "Mix content types: compound_spotlight, research_update, mechanism_explainer, "
                        "study_breakdown, lab_insight, research_q_and_a.\n"
                        "For each idea output a JSON object on its own line with keys: "
                        '"title", "content_type", "description", "suggested_hashtags".\n'
                        "Output ONLY the JSON lines, nothing else."
                    ),
                }
            ],
        )
        import json
        plans = []
        for line in response.content[0].text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                plans.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return plans

    def suggest_hashtags(self, topic: str, platform: str = "instagram", count: int = 12) -> list[str]:
        """Return a curated list of research-appropriate hashtags for a peptide topic."""
        response = self._client.messages.create(
            model=config.agent.model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"List {count} highly relevant hashtags for a peptide research {platform} post "
                        f"about '{topic}'.\n"
                        "Include a mix of: compound-specific tags, research community tags, and science discovery tags.\n"
                        "One hashtag per line. Include the # prefix. No explanations.\n"
                        "Do NOT include generic spam hashtags like #fitness or #health."
                    ),
                }
            ],
        )
        return [
            line.strip()
            for line in response.content[0].text.strip().splitlines()
            if line.strip().startswith("#")
        ]

    def check_compliance(self, content: str) -> dict:
        """Review a post for compliance issues before publishing."""
        response = self._client.messages.create(
            model=config.agent.model,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are a regulatory compliance reviewer for a peptide research company. "
                        "You check social media posts for violations of research-only compliance rules.\n\n"
                        f"{COMPLIANCE_RULES}"
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Review this post for compliance issues:\n\n{content}\n\n"
                        "Output JSON with keys: "
                        '"compliant" (true/false), "issues" (list of strings), "suggestion" (string or null).\n'
                        "Output ONLY the JSON, nothing else."
                    ),
                }
            ],
        )
        import json
        try:
            return json.loads(response.content[0].text.strip())
        except json.JSONDecodeError:
            return {"compliant": None, "issues": ["Could not parse compliance review"], "suggestion": None}
