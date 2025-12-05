"""
MongoDB Database Layer for Broadway Lottery Application
Provides a MongoDB-backed replacement for the mock database layer.
Uses Streamlit secrets for secure MongoDB URI configuration.
"""

import streamlit as st
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError
from typing import Optional
from datetime import datetime, timezone


@st.cache_resource
def get_mongo_client():
    """
    Get or create a MongoDB client connection.
    Uses Streamlit secrets for the MongoDB URI.
    Caches the connection to reuse across app reruns.

    Returns:
        MongoClient: Connected MongoDB client

    Raises:
        ValueError: If MONGO_URI is not found in Streamlit secrets
        ServerSelectionTimeoutError: If unable to connect to MongoDB
    """
    try:
        mongo_uri = st.secrets.get("MONGO_URI")
        if not mongo_uri:
            raise ValueError(
                "MONGO_URI not found in Streamlit secrets. "
                "Please add it to .streamlit/secrets.toml"
            )

        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Verify connection
        client.admin.command("ping")
        return client
    except ValueError as e:
        st.error(f"Configuration Error: {str(e)}")
        raise
    except ServerSelectionTimeoutError:
        st.error("Unable to connect to MongoDB. Please verify the connection string.")
        raise
    except PyMongoError as e:
        st.error(f"MongoDB Error: {str(e)}")
        raise


def get_database():
    """
    Get the Broadway lottery database.

    Returns:
        Database: MongoDB database object
    """
    client = get_mongo_client()
    return client["broadway_lottery"]


def get_entries_collection():
    """
    Get the entries collection from the database.

    Returns:
        Collection: MongoDB collection for entries
    """
    db = get_database()
    collection = db["entries"]
    return collection


def get_logs_collection():
    """
    Get the logs collection from the database.
    Logs track all user actions (submissions, cancellations, updates).

    Returns:
        Collection: MongoDB collection for action logs
    """
    db = get_database()
    collection = db["logs"]
    return collection


def save_entry(email: str, show: str, quantity: int = 2) -> bool:
    """
    Save or overwrite an entry in MongoDB.
    Email serves as the unique key; submitting again overwrites the show and quantity.
    Includes NoSQL injection prevention through parameterized queries.
    Also logs the action with timestamp.

    Args:
        email: User's email address (will be lowercased and used as unique key)
        show: Selected Broadway show name
        quantity: Number of tickets (1 or 2, defaults to 2)

    Returns:
        bool: True if entry was saved successfully

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        collection = get_entries_collection()
        logs_collection = get_logs_collection()
        current_time = datetime.now(timezone.utc)

        # Check if this is an update or new entry
        existing_entry = collection.find_one({"email": email.lower()})
        action = "updated" if existing_entry else "submitted"

        # Use replace_one with upsert to handle both insert and update
        result = collection.replace_one(
            {"email": email.lower()},
            {
                "email": email.lower(),
                "show": show,
                "quantity": quantity,
                "timestamp": current_time,
            },
            upsert=True,
        )

        # Log the action
        if result.matched_count > 0 or result.upserted_id is not None:
            logs_collection.insert_one(
                {
                    "email": email.lower(),
                    "show": show,
                    "quantity": quantity,
                    "action": action,
                    "timestamp": current_time,
                }
            )
            return True

        return False
    except PyMongoError as e:
        st.error(f"Failed to save entry: {str(e)}")
        return False


def get_entry(email: str) -> Optional[dict]:
    """
    Retrieve the entry (show and quantity) for a given email from MongoDB.

    Args:
        email: User's email address to look up

    Returns:
        Optional[dict]: A dictionary with 'show' and 'quantity' keys if found, None otherwise

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        collection = get_entries_collection()
        entry = collection.find_one({"email": email.lower()})

        if entry:
            return {"show": entry.get("show"), "quantity": entry.get("quantity", 2)}
        return None
    except PyMongoError as e:
        st.error(f"Failed to retrieve entry: {str(e)}")
        return None


def delete_entry(email: str) -> bool:
    """
    Delete an entry from MongoDB.
    Also logs the cancellation action with timestamp.

    Args:
        email: User's email address to delete

    Returns:
        bool: True if entry existed and was deleted, False if not found

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        collection = get_entries_collection()
        logs_collection = get_logs_collection()

        # Get the entry before deleting to know what show was deleted
        entry = collection.find_one({"email": email.lower()})

        if entry:
            result = collection.delete_one({"email": email.lower()})

            if result.deleted_count > 0:
                # Log the cancellation
                logs_collection.insert_one(
                    {
                        "email": email.lower(),
                        "show": entry.get("show"),
                        "quantity": entry.get("quantity", 2),
                        "action": "cancelled",
                        "timestamp": datetime.now(timezone.utc),
                    }
                )
                return True

        return False
    except PyMongoError as e:
        st.error(f"Failed to delete entry: {str(e)}")
        return False


def get_all_entries() -> list:
    """
    Retrieve all entries from the database.
    Useful for admin purposes or analytics.

    Returns:
        list: List of all entries with email and show information

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        collection = get_entries_collection()
        entries = list(collection.find({}, {"_id": 0}))
        return entries
    except PyMongoError as e:
        st.error(f"Failed to retrieve entries: {str(e)}")
        return []


def get_show_statistics() -> dict:
    """
    Get statistics about entries per show.
    Useful for analytics and admin dashboards.

    Returns:
        dict: Dictionary with show names as keys and entry counts as values

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        collection = get_entries_collection()
        pipeline = [
            {"$group": {"_id": "$show", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        results = collection.aggregate(pipeline)
        stats = {result["_id"]: result["count"] for result in results}
        return stats
    except PyMongoError as e:
        st.error(f"Failed to retrieve statistics: {str(e)}")
        return {}


def clear_all_entries() -> bool:
    """
    Delete all entries from the database.
    WARNING: This is a destructive operation, use with caution!

    Returns:
        bool: True if all entries were deleted successfully

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        collection = get_entries_collection()
        result = collection.delete_many({})
        return result.deleted_count >= 0
    except PyMongoError as e:
        st.error(f"Failed to clear entries: {str(e)}")
        return False


def get_user_activity_log(email: str) -> list:
    """
    Retrieve the complete activity log for a specific user.
    Shows all actions (submissions, updates, cancellations) with timestamps.

    Args:
        email: User's email address to retrieve activity for

    Returns:
        list: List of log entries sorted by timestamp (newest first)

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        logs_collection = get_logs_collection()
        logs = list(
            logs_collection.find({"email": email.lower()}, {"_id": 0}).sort(
                "timestamp", -1
            )
        )
        return logs
    except PyMongoError as e:
        st.error(f"Failed to retrieve user activity log: {str(e)}")
        return []


def get_all_logs() -> list:
    """
    Retrieve all activity logs from the database.
    Useful for auditing and analytics.

    Returns:
        list: List of all log entries sorted by timestamp (newest first)

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        logs_collection = get_logs_collection()
        logs = list(logs_collection.find({}, {"_id": 0}).sort("timestamp", -1))
        return logs
    except PyMongoError as e:
        st.error(f"Failed to retrieve all logs: {str(e)}")
        return []


def get_logs_by_action(action: str) -> list:
    """
    Retrieve all logs for a specific action type.

    Args:
        action: Action type to filter by ('submitted', 'updated', 'cancelled')

    Returns:
        list: List of log entries for the specified action, sorted by timestamp

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        logs_collection = get_logs_collection()
        logs = list(
            logs_collection.find({"action": action}, {"_id": 0}).sort("timestamp", -1)
        )
        return logs
    except PyMongoError as e:
        st.error(f"Failed to retrieve logs by action: {str(e)}")
        return []


def get_activity_statistics() -> dict:
    """
    Get statistics about user activities.
    Includes counts by action type and other useful metrics.

    Returns:
        dict: Dictionary with activity statistics

    Raises:
        PyMongoError: If database operation fails
    """
    try:
        logs_collection = get_logs_collection()
        pipeline = [
            {"$group": {"_id": "$action", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        results = list(logs_collection.aggregate(pipeline))
        stats = {result["_id"]: result["count"] for result in results}

        # Add total count
        stats["total"] = sum(stats.values())

        return stats
    except PyMongoError as e:
        st.error(f"Failed to retrieve activity statistics: {str(e)}")
        return {}
