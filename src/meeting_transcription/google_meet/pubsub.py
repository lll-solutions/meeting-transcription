"""
Cloud Pub/Sub setup and management for Google Meet transcript events.

Creates and configures the Pub/Sub topic and push subscription
that receives Meet transcript notifications.
"""

import os

from .config import get_google_oauth_config

try:
    from google.api_core.exceptions import AlreadyExists, NotFound
    from google.cloud import pubsub_v1

    HAS_PUBSUB = True
except ImportError:
    HAS_PUBSUB = False


def ensure_pubsub_resources(push_endpoint: str | None = None) -> dict[str, str]:
    """
    Create Pub/Sub topic and push subscription if they don't exist.

    Args:
        push_endpoint: HTTPS endpoint for push subscription.
            Defaults to {SERVICE_URL}/webhook/google-meet.

    Returns:
        Dict with 'topic' and 'subscription' paths.

    Raises:
        RuntimeError: If Pub/Sub libraries are not installed.
    """
    if not HAS_PUBSUB:
        raise RuntimeError(
            "google-cloud-pubsub is required. "
            "Install with: pip install google-cloud-pubsub"
        )

    config = get_google_oauth_config()

    if not push_endpoint:
        service_url = os.getenv("SERVICE_URL", "")
        if not service_url:
            raise ValueError("SERVICE_URL or push_endpoint is required")
        push_endpoint = f"{service_url.rstrip('/')}/webhook/google-meet"

    topic_path = config.pubsub_topic_path
    subscription_path = config.pubsub_subscription_path

    # Create topic
    publisher = pubsub_v1.PublisherClient()
    try:
        publisher.create_topic(name=topic_path)
        print(f"Created Pub/Sub topic: {topic_path}")
    except AlreadyExists:
        print(f"Pub/Sub topic already exists: {topic_path}")

    # Create push subscription
    subscriber = pubsub_v1.SubscriberClient()
    try:
        subscriber.create_subscription(
            request={
                "name": subscription_path,
                "topic": topic_path,
                "push_config": {"push_endpoint": push_endpoint},
                "ack_deadline_seconds": 60,
                "message_retention_duration": {"seconds": 86400},  # 1 day
            }
        )
        print(f"Created Pub/Sub subscription: {subscription_path}")
        print(f"  Push endpoint: {push_endpoint}")
    except AlreadyExists:
        # Update the push endpoint if subscription already exists
        subscriber.modify_push_config(
            request={
                "subscription": subscription_path,
                "push_config": {"push_endpoint": push_endpoint},
            }
        )
        print(f"Updated Pub/Sub subscription push endpoint: {push_endpoint}")

    return {
        "topic": topic_path,
        "subscription": subscription_path,
        "push_endpoint": push_endpoint,
    }


def delete_pubsub_resources() -> None:
    """Delete Pub/Sub topic and subscription (for cleanup)."""
    if not HAS_PUBSUB:
        return

    config = get_google_oauth_config()

    subscriber = pubsub_v1.SubscriberClient()
    try:
        subscriber.delete_subscription(
            request={"subscription": config.pubsub_subscription_path}
        )
        print(f"Deleted subscription: {config.pubsub_subscription_path}")
    except NotFound:
        pass

    publisher = pubsub_v1.PublisherClient()
    try:
        publisher.delete_topic(request={"topic": config.pubsub_topic_path})
        print(f"Deleted topic: {config.pubsub_topic_path}")
    except NotFound:
        pass


def get_pubsub_status() -> dict[str, bool | str]:
    """Check if Pub/Sub resources exist and are configured."""
    if not HAS_PUBSUB:
        return {"available": False, "reason": "google-cloud-pubsub not installed"}

    config = get_google_oauth_config()
    result: dict[str, bool | str] = {"available": True}

    subscriber = pubsub_v1.SubscriberClient()
    try:
        sub = subscriber.get_subscription(
            request={"subscription": config.pubsub_subscription_path}
        )
        result["subscription_exists"] = True
        result["push_endpoint"] = sub.push_config.push_endpoint
    except NotFound:
        result["subscription_exists"] = False
    except Exception as e:
        result["subscription_exists"] = False
        result["subscription_error"] = str(e)

    publisher = pubsub_v1.PublisherClient()
    try:
        publisher.get_topic(request={"topic": config.pubsub_topic_path})
        result["topic_exists"] = True
    except NotFound:
        result["topic_exists"] = False
    except Exception as e:
        result["topic_exists"] = False
        result["topic_error"] = str(e)

    return result
