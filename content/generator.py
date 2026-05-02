"""AI content generator powered by Claude with prompt caching."""
from typing import Optional
import anthropic
import config
from .templates import PLATFORM_PROMPTS, CONTENT_TYPES


class ContentGenerator:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=config.agent.anthropic_api_key)

    def generate(
        self,
        topic: str,
        platform: str,
        content_type: str = "educational",
        extra_instructions: Optional[str] = None,
        existing_content: Optional[str] = None,
    ) -> str:
        """Generate platform-optimised content for a given topic."""
        platform_prompt = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["linkedin"])
        content_brief = CONTENT_TYPES.get(content_type, CONTENT_TYPES["educational"]).format(topic=topic)

        system = (
            f"You are an expert social media manager for {config.agent.brand_name}.\n"
            f"Brand voice: {config.agent.brand_voice}\n"
            f"Core topics: {config.agent.brand_topics}\n\n"
            f"Platform-specific rules for {platform.capitalize()}:\n{platform_prompt}\n\n"
            "Return ONLY the post text. No labels, no explanations, no quotes around the output."
        )

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
                    "text": system,
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
        """Generate platform-specific versions of the same post in one call using a two-step approach."""
        results: dict[str, str] = {}

        # Generate the long-form anchor first (LinkedIn or Facebook), then adapt
        anchor_platform = next(
            (p for p in ["linkedin", "facebook"] if p in platforms),
            platforms[0],
        )
        anchor_content = self.generate(topic, anchor_platform, content_type, extra_instructions)
        results[anchor_platform] = anchor_content

        # Adapt the anchor for each remaining platform
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
        """Ask Claude to build a content calendar plan."""
        response = self._client.messages.create(
            model=config.agent.model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": (
                        f"You are an expert social media strategist for {config.agent.brand_name}.\n"
                        f"Brand voice: {config.agent.brand_voice}\n"
                        f"Core topics: {config.agent.brand_topics}"
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Create a content plan with {num_posts} post ideas about '{topic}'.\n"
                        "For each idea output a JSON object on its own line with keys: "
                        '"title", "content_type", "description", "best_platform".\n'
                        "Output ONLY the JSON lines, nothing else."
                    ),
                }
            ],
        )
        import json
        lines = response.content[0].text.strip().splitlines()
        plans = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                plans.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return plans

    def suggest_hashtags(self, topic: str, platform: str, count: int = 10) -> list[str]:
        """Return a list of relevant hashtags for a topic and platform."""
        response = self._client.messages.create(
            model=config.agent.model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"List {count} highly relevant hashtags for a {platform} post about '{topic}'.\n"
                        "One hashtag per line. Include the # prefix. No explanations."
                    ),
                }
            ],
        )
        return [
            line.strip()
            for line in response.content[0].text.strip().splitlines()
            if line.strip().startswith("#")
        ]
