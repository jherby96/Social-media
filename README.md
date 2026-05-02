# Social Media AI Agent

An AI-powered social media manager built with Claude. It generates platform-optimised content, cross-posts to multiple networks, schedules posts, and tracks analytics — all from a CLI or via natural language chat.

## Features

- **AI Content Generation** — Claude generates platform-specific posts (Twitter, LinkedIn, Facebook, Instagram, Bluesky)
- **Cross-posting** — One topic, adapted intelligently for every platform
- **Content Planning** — Generate a full content calendar with post ideas
- **Scheduling** — Queue posts for future publishing with a lightweight scheduler daemon
- **Analytics** — Track likes, comments, shares, and impressions per platform
- **Natural Language Agent** — Chat with the agent in plain English to run your socials
- **Prompt Caching** — Uses Claude's prompt caching for efficiency on repeated calls

## Supported Platforms

| Platform | Post | Image | Video |
|----------|------|-------|-------|
| Twitter/X | ✓ | ✓ | ✓ |
| LinkedIn | ✓ | ✓ | - |
| Facebook | ✓ | ✓ | ✓ |
| Instagram | ✓ | ✓ | ✓ |
| Bluesky | ✓ | ✓ | - |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

At minimum you need `ANTHROPIC_API_KEY`. Add social platform credentials for each platform you want to use.

### 3. Check status

```bash
python cli.py status
```

## CLI Usage

### Chat with the agent (natural language)

```bash
# Interactive REPL
python cli.py chat

# Single command
python cli.py chat -m "Create a LinkedIn post about AI trends and schedule it for 2 hours from now"
```

### Generate content

```bash
# Single platform
python cli.py generate "the future of remote work" --platform linkedin --type educational

# All configured platforms at once
python cli.py generate "the future of remote work" --all-platforms
```

### Publish immediately

```bash
python cli.py post "AI productivity tips" --platform twitter --now
```

### Cross-post to all platforms

```bash
# Post now
python cli.py crosspost "our product launch"

# Schedule with 30-minute gaps between platforms
python cli.py crosspost "our product launch" --schedule --delay 30
```

### Content planning

```bash
python cli.py plan "sustainable technology" --count 7
```

### Scheduling

```bash
# Schedule a post (60-minute delay by default)
python cli.py post "AI news" --platform linkedin --delay 120

# Start the scheduler daemon
python cli.py schedule-run --interval 60

# Manually flush due posts
python cli.py flush
```

### Analytics & history

```bash
python cli.py posts                          # All recent posts
python cli.py posts --platform twitter --status posted
python cli.py analytics
```

## Getting API Credentials

### Twitter/X
1. Go to [developer.twitter.com](https://developer.twitter.com/)
2. Create a project and app with Read + Write permissions
3. Generate API Key, Secret, Access Token, and Access Secret

### LinkedIn
1. Go to [linkedin.com/developers](https://www.linkedin.com/developers/)
2. Create an app and request `w_member_social` permission
3. Complete OAuth 2.0 flow to get an access token

### Facebook / Instagram
1. Go to [developers.facebook.com](https://developers.facebook.com/)
2. Create an app, add the Pages API and Instagram Graph API
3. Generate a Page Access Token (long-lived)
4. For Instagram: connect your Instagram Business account to the Facebook Page

### Bluesky
1. Go to [bsky.app/settings/app-passwords](https://bsky.app/settings/app-passwords)
2. Create an App Password (do not use your main password)

## Project Structure

```
├── agent.py           # Main AI agent with Claude tool-use loop
├── cli.py             # Click CLI interface
├── config.py          # Credential configuration
├── scheduler.py       # Post scheduler
├── storage.py         # SQLite database layer
├── content/
│   ├── generator.py   # Claude-powered content generation
│   └── templates.py   # Per-platform prompts and content types
├── platforms/
│   ├── base.py        # Abstract platform base class
│   ├── twitter.py     # Twitter/X connector
│   ├── linkedin.py    # LinkedIn connector
│   ├── facebook.py    # Facebook connector
│   ├── instagram.py   # Instagram connector
│   └── bluesky.py     # Bluesky connector
└── tests/             # Unit tests
```

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```
