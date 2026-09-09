"""Supabase client.

Configuration and validation live in core.config, which is imported first so a
missing variable produces one complete, actionable error instead of failing on
whichever module happened to load first.
"""

import logging

from supabase import Client, create_client

from core import config

logger = logging.getLogger(__name__)

config.validate()

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

logger.info("Database connection initialized.")
