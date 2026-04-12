# -*- coding: utf-8 -*-
"""
Call-cache persistence.

Call history is stored as JSON under /etc/enigma2/ (default).
Settings are now managed via the Enigma2 config system
(config.plugins.fritzcall.*) and persisted in /etc/enigma2/settings.
"""
from __future__ import absolute_import

import json
import os

CALL_CACHE_FILE = "/etc/enigma2/fritzcall_calls.json"


class FritzCallStore(object):
    def __init__(self, call_cache_file=CALL_CACHE_FILE):
        self.call_cache_file = call_cache_file

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_json(self, path, fallback):
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except Exception:
            return fallback

    def _write_json(self, path, data):
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            try:
                os.makedirs(folder)
            except Exception:
                pass
        try:
            with open(path, "w") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Call cache  (last N calls fetched from the FritzBox)
    # ------------------------------------------------------------------

    def get_call_cache(self):
        data = self._read_json(self.call_cache_file, [])
        if isinstance(data, list):
            return data
        return []

    def save_call_cache(self, calls):
        # Keep at most 500 entries to avoid huge files
        self._write_json(self.call_cache_file, (calls or [])[:500])
