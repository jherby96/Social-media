"""Central configuration — loads from .env and validates required keys per platform."""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TwitterConfig:
    api_key: str = field(default_factory=lambda: os.getenv("TWITTER_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("TWITTER_API_SECRET", ""))
    access_token: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN", ""))
    access_secret: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_SECRET", ""))
    bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.api_key, self.api_secret, self.access_token, self.access_secret])


@dataclass
class LinkedInConfig:
    client_id: str = field(default_factory=lambda: os.getenv("LINKEDIN_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("LINKEDIN_CLIENT_SECRET", ""))
    access_token: str = field(default_factory=lambda: os.getenv("LINKEDIN_ACCESS_TOKEN", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)


@dataclass
class FacebookConfig:
    page_id: str = field(default_factory=lambda: os.getenv("FACEBOOK_PAGE_ID", ""))
    page_access_token: str = field(default_factory=lambda: os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.page_id, self.page_access_token])


@dataclass
class InstagramConfig:
    account_id: str = field(default_factory=lambda: os.getenv("INSTAGRAM_ACCOUNT_ID", ""))
    access_token: str = field(default_factory=lambda: os.getenv("INSTAGRAM_ACCESS_TOKEN", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.account_id, self.access_token])


@dataclass
class BlueskyConfig:
    handle: str = field(default_factory=lambda: os.getenv("BLUESKY_HANDLE", ""))
    password: str = field(default_factory=lambda: os.getenv("BLUESKY_APP_PASSWORD", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.handle, self.password])


@dataclass
class AgentConfig:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"))
    brand_name: str = field(default_factory=lambda: os.getenv("BRAND_NAME", "My Brand"))
    brand_voice: str = field(default_factory=lambda: os.getenv("BRAND_VOICE", "professional, engaging, and authentic"))
    brand_topics: str = field(default_factory=lambda: os.getenv("BRAND_TOPICS", "technology, innovation, business"))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "UTC"))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "social_media.db"))

    @property
    def is_configured(self) -> bool:
        return bool(self.anthropic_api_key)


@dataclass
class WooCommerceConfig:
    site_url: str = field(default_factory=lambda: os.getenv("WC_SITE_URL", ""))
    consumer_key: str = field(default_factory=lambda: os.getenv("WC_CONSUMER_KEY", ""))
    consumer_secret: str = field(default_factory=lambda: os.getenv("WC_CONSUMER_SECRET", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WC_WEBHOOK_SECRET", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.site_url, self.consumer_key, self.consumer_secret])


@dataclass
class EmailConfig:
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    from_email: str = field(default_factory=lambda: os.getenv("FROM_EMAIL", ""))
    from_name: str = field(default_factory=lambda: os.getenv("FROM_NAME", "Peptide Store"))
    support_email: str = field(default_factory=lambda: os.getenv("SUPPORT_EMAIL", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.smtp_user, self.smtp_password, self.from_email])


@dataclass
class ComplianceConfig:
    coa_directory: str = field(default_factory=lambda: os.getenv("COA_DIRECTORY", "coa_files"))
    backup_directory: str = field(default_factory=lambda: os.getenv("BACKUP_DIRECTORY", "backups"))
    backup_interval_hours: int = field(default_factory=lambda: int(os.getenv("BACKUP_INTERVAL_HOURS", "24")))

    @property
    def is_configured(self) -> bool:
        return True


@dataclass
class AccountingConfig:
    gst_rate: float = field(default_factory=lambda: float(os.getenv("GST_RATE", "0.10")))
    bas_period: str = field(default_factory=lambda: os.getenv("BAS_PERIOD", "quarterly"))
    currency: str = field(default_factory=lambda: os.getenv("CURRENCY", "AUD"))
    business_name: str = field(default_factory=lambda: os.getenv("BUSINESS_NAME", ""))
    abn: str = field(default_factory=lambda: os.getenv("ABN", ""))


@dataclass
class DashboardConfig:
    host: str = field(default_factory=lambda: os.getenv("DASHBOARD_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "5000")))
    secret_key: str = field(default_factory=lambda: os.getenv("DASHBOARD_SECRET_KEY", "change-me-in-production"))
    debug: bool = field(default_factory=lambda: os.getenv("DASHBOARD_DEBUG", "false").lower() == "true")


# Singletons
twitter = TwitterConfig()
linkedin = LinkedInConfig()
facebook = FacebookConfig()
instagram = InstagramConfig()
bluesky = BlueskyConfig()
agent = AgentConfig()
woocommerce = WooCommerceConfig()
email = EmailConfig()
compliance = ComplianceConfig()
accounting = AccountingConfig()
dashboard = DashboardConfig()
