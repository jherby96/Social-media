#!/usr/bin/env python3
"""
Social Media AI Agent — CLI
Usage: python cli.py [COMMAND] [OPTIONS]
"""
import json
import logging
import sys
from typing import Optional

import click

# Set up logging before imports that might log
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """AI Social Media Agent — generate, schedule, and cross-post content."""
    if verbose:
        logging.getLogger().setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Chat / interactive mode
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--message", "-m", default=None, help="Single message to send to the agent")
def chat(message: Optional[str]):
    """Chat with the AI agent in natural language."""
    import agent as ag
    a = ag.get_agent()

    if message:
        click.echo(click.style("You: ", fg="cyan") + message)
        response = a.run(message)
        click.echo(click.style("Agent: ", fg="green") + response)
        return

    click.echo(click.style("Social Media AI Agent", fg="bright_blue", bold=True))
    click.echo("Type your request (e.g. 'Create a LinkedIn post about AI trends').")
    click.echo("Commands: 'quit' / 'exit' to leave, 'reset' to clear history.\n")

    while True:
        try:
            user_input = click.prompt(click.style("You", fg="cyan"))
        except (EOFError, click.exceptions.Abort):
            click.echo("\nGoodbye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            click.echo("Goodbye!")
            break
        if user_input.lower() == "reset":
            a.reset()
            click.echo(click.style("Conversation reset.", fg="yellow"))
            continue
        if not user_input.strip():
            continue

        response = a.run(user_input)
        click.echo(click.style("Agent: ", fg="green") + response + "\n")


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

@cli.command("generate")
@click.argument("topic")
@click.option("--platform", "-p", default="linkedin",
              type=click.Choice(["twitter", "linkedin", "facebook", "instagram", "bluesky"]),
              help="Target platform")
@click.option("--type", "-t", "content_type", default="educational",
              type=click.Choice(["educational", "promotional", "storytelling", "question",
                                 "tip", "trend", "behind_the_scenes", "announcement",
                                 "motivational", "curated"]),
              help="Content style")
@click.option("--extra", "-e", default=None, help="Extra instructions for the AI")
@click.option("--all-platforms", "-a", is_flag=True, help="Generate for all configured platforms")
def generate_content(topic: str, platform: str, content_type: str,
                     extra: Optional[str], all_platforms: bool):
    """Generate AI content for a topic."""
    from content.generator import ContentGenerator
    from platforms import get_available_platforms

    generator = ContentGenerator()

    if all_platforms:
        available = list(get_available_platforms().keys())
        if not available:
            click.echo(click.style("No platforms configured.", fg="red"))
            sys.exit(1)
        click.echo(f"Generating for: {', '.join(available)}\n")
        results = generator.generate_cross_platform(topic, available, content_type, extra)
        for plat, content in results.items():
            click.echo(click.style(f"=== {plat.upper()} ({len(content)} chars) ===", fg="bright_blue", bold=True))
            click.echo(content)
            click.echo()
    else:
        content = generator.generate(topic, platform, content_type, extra)
        click.echo(click.style(f"=== {platform.upper()} ({len(content)} chars) ===", fg="bright_blue", bold=True))
        click.echo(content)


# ---------------------------------------------------------------------------
# Post publishing
# ---------------------------------------------------------------------------

@cli.command("post")
@click.argument("topic")
@click.option("--platform", "-p", required=True,
              type=click.Choice(["twitter", "linkedin", "facebook", "instagram", "bluesky"]))
@click.option("--content", "-c", default=None, help="Post text (generated if omitted)")
@click.option("--type", "-t", "content_type", default="educational")
@click.option("--now", is_flag=True, help="Publish immediately (default: schedule)")
@click.option("--delay", "-d", default=0, type=int, help="Delay in minutes before publishing")
def post(topic: str, platform: str, content: Optional[str], content_type: str,
         now: bool, delay: int):
    """Generate and publish/schedule a post."""
    from content.generator import ContentGenerator
    from platforms import get_available_platforms
    import storage as st
    import scheduler as s

    st.init_db()

    if content is None:
        click.echo("Generating content...")
        generator = ContentGenerator()
        content = generator.generate(topic, platform, content_type)
        click.echo(click.style(f"\n{content}\n", fg="white"))

    if now:
        available = get_available_platforms()
        p = available.get(platform)
        if p is None:
            click.echo(click.style(f"Platform '{platform}' not configured.", fg="red"))
            sys.exit(1)
        result = p.post(content)
        if result.success:
            post_id = st.save_post(topic, platform, content)
            st.update_post_status(post_id, "posted", platform_post_id=result.platform_post_id)
            click.echo(click.style(f"Posted! {result.url}", fg="green"))
        else:
            click.echo(click.style(f"Failed: {result.error}", fg="red"))
            sys.exit(1)
    else:
        post_id = s.schedule_post(topic, platform, content, delay_minutes=delay)
        click.echo(click.style(f"Scheduled (post #{post_id}, delay={delay}m)", fg="yellow"))


# ---------------------------------------------------------------------------
# Cross-post
# ---------------------------------------------------------------------------

@cli.command("crosspost")
@click.argument("topic")
@click.option("--type", "-t", "content_type", default="educational")
@click.option("--extra", "-e", default=None)
@click.option("--schedule", "-s", is_flag=True, help="Schedule instead of publishing now")
@click.option("--delay", "-d", default=0, type=int, help="Minutes delay between each platform post")
def crosspost(topic: str, content_type: str, extra: Optional[str], schedule: bool, delay: int):
    """Generate and cross-post to all configured platforms."""
    from content.generator import ContentGenerator
    from platforms import get_available_platforms
    import storage as st
    import scheduler as s

    st.init_db()
    available = get_available_platforms()
    if not available:
        click.echo(click.style("No platforms configured. Set API keys in .env", fg="red"))
        sys.exit(1)

    platforms = list(available.keys())
    click.echo(f"Generating content for: {', '.join(platforms)}")
    generator = ContentGenerator()
    results = generator.generate_cross_platform(topic, platforms, content_type, extra)

    for i, (plat, content) in enumerate(results.items()):
        click.echo(click.style(f"\n[{plat.upper()}]", fg="bright_blue", bold=True))
        click.echo(content)

        if schedule:
            post_id = s.schedule_post(topic, plat, content, delay_minutes=delay * i)
            click.echo(click.style(f"  Scheduled #{post_id}", fg="yellow"))
        else:
            platform_obj = available[plat]
            result = platform_obj.post(content)
            if result.success:
                post_id = st.save_post(topic, plat, content)
                st.update_post_status(post_id, "posted", platform_post_id=result.platform_post_id)
                click.echo(click.style(f"  Posted: {result.url}", fg="green"))
            else:
                click.echo(click.style(f"  Failed: {result.error}", fg="red"))


# ---------------------------------------------------------------------------
# Content plan
# ---------------------------------------------------------------------------

@cli.command("plan")
@click.argument("topic")
@click.option("--count", "-n", default=5, type=int, help="Number of post ideas")
def content_plan(topic: str, count: int):
    """Generate a content calendar plan for a topic."""
    from content.generator import ContentGenerator
    generator = ContentGenerator()
    click.echo(f"Generating {count} post ideas for '{topic}'...\n")
    plan = generator.generate_content_plan(topic, count)
    for i, item in enumerate(plan, 1):
        click.echo(click.style(f"{i}. {item.get('title', 'Untitled')}", fg="bright_blue", bold=True))
        click.echo(f"   Type: {item.get('content_type', '?')} | Best platform: {item.get('best_platform', '?')}")
        click.echo(f"   {item.get('description', '')}\n")


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

@cli.command("schedule-run")
@click.option("--interval", "-i", default=60, type=int, help="Check interval in seconds")
def schedule_run(interval: int):
    """Start the scheduler daemon — publishes due posts on an interval."""
    import storage as st
    st.init_db()
    click.echo(click.style(f"Scheduler running (interval={interval}s). Ctrl-C to stop.", fg="yellow"))
    from scheduler import start_scheduler
    start_scheduler(interval_seconds=interval)


@cli.command("flush")
def flush():
    """Immediately publish all due scheduled posts."""
    import storage as st
    st.init_db()
    from scheduler import flush_due_posts
    results = flush_due_posts()
    if not results:
        click.echo("No due posts found.")
        return
    for r in results:
        status = r.get("result", "?")
        color = {"posted": "green", "failed": "red", "skipped": "yellow"}.get(status, "white")
        label = click.style(status.upper(), fg=color)
        click.echo(f"[{label}] #{r['id']} {r['platform']}: {r.get('url') or r.get('error', '')}")


# ---------------------------------------------------------------------------
# Posts / analytics
# ---------------------------------------------------------------------------

@cli.command("posts")
@click.option("--platform", "-p", default=None)
@click.option("--status", "-s", default=None,
              type=click.Choice(["pending", "posted", "failed", "skipped"]))
@click.option("--limit", "-n", default=20, type=int)
def list_posts(platform: Optional[str], status: Optional[str], limit: int):
    """List posts from the database."""
    import storage as st
    st.init_db()
    posts = st.get_posts(platform=platform, status=status, limit=limit)
    if not posts:
        click.echo("No posts found.")
        return
    for p in posts:
        status_color = {"posted": "green", "failed": "red", "pending": "yellow", "skipped": "white"}
        color = status_color.get(p["status"], "white")
        s = click.style(p["status"].upper(), fg=color)
        scheduled = p.get("scheduled_at", "")[:16] if p.get("scheduled_at") else "-"
        click.echo(f"#{p['id']:4d} [{s}] {p['platform']:12s} {scheduled}  {p['content'][:60]}...")


@cli.command("analytics")
def analytics():
    """Show engagement analytics summary."""
    import storage as st
    st.init_db()
    summary = st.get_analytics_summary()
    if not summary:
        click.echo("No analytics data yet.")
        return
    click.echo(click.style("Platform Analytics", bold=True))
    click.echo(f"{'Platform':<14} {'Posts':>6} {'Likes':>8} {'Comments':>10} {'Shares':>8} {'Impressions':>12}")
    click.echo("-" * 62)
    for row in summary:
        click.echo(
            f"{row['platform']:<14} {row['total_posts']:>6} "
            f"{(row['total_likes'] or 0):>8} {(row['total_comments'] or 0):>10} "
            f"{(row['total_shares'] or 0):>8} {(row['total_impressions'] or 0):>12}"
        )


# ---------------------------------------------------------------------------
# Platform status
# ---------------------------------------------------------------------------

@cli.command("status")
def status():
    """Show which platforms are configured and ready."""
    import config as cfg
    platforms = {
        "twitter": cfg.twitter,
        "linkedin": cfg.linkedin,
        "facebook": cfg.facebook,
        "instagram": cfg.instagram,
        "bluesky": cfg.bluesky,
    }
    click.echo(click.style("Platform Configuration Status", bold=True))
    click.echo("-" * 30)
    for name, p_cfg in platforms.items():
        icon = click.style("✓", fg="green") if p_cfg.is_configured else click.style("✗", fg="red")
        click.echo(f"  {icon}  {name.capitalize()}")
    agent_ok = click.style("✓", fg="green") if cfg.agent.is_configured else click.style("✗", fg="red")
    click.echo(f"\n  {agent_ok}  Anthropic API (Claude)")
    click.echo(f"\n  Brand: {cfg.agent.brand_name}")
    click.echo(f"  Model: {cfg.agent.model}")


if __name__ == "__main__":
    cli()
