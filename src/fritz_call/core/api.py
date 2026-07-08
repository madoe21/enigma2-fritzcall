# -*- coding: utf-8 -*-
"""
Platform-neutral FritzBox HTTP/TR-064 client.

Authentication uses the FritzBox SID (session-ID) challenge-response scheme.
The phonebook is fetched via a TR-064 SOAP call; the call list via the
built-in CSV export URL.

No Enigma2 or Kodi imports – safe to unit-test standalone.
"""
from __future__ import absolute_import

import base64
import hashlib
import xml.etree.ElementTree as ET

try:
    from urllib2 import HTTPError, Request, urlopen
    from urllib import urlencode
    _PY2 = True
except ImportError:
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    _PY2 = False

from . import normalize_call, normalize_number, parse_call_list_csv

_SOAP_TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
    ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    "<s:Body>"
    '<u:{action} xmlns:u="{ns}">'
    "{params}"
    "</u:{action}>"
    "</s:Body>"
    "</s:Envelope>"
)


class FritzBoxClient(object):
    """FritzBox HTTP client.

    Parameters
    ----------
    host : str
        Hostname or IP of the FritzBox (e.g. "fritz.box" or "192.168.178.1").
    username : str
        FritzBox user name (may be empty for single-user setups on old
        firmware, but a dedicated user is recommended).
    password : str
        FritzBox password.
    timeout : int
        HTTP timeout in seconds.
    """

    def __init__(self, host="fritz.box", username="", password="", timeout=12):
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self._sid = None
        self._phonebook_cache = {}  # number → name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self):
        """Return True if a SID can be obtained (credentials OK)."""
        try:
            sid = self._acquire_sid()
            return bool(sid and sid != "0000000000000000")
        except Exception:
            return False

    def get_call_list(self, max_entries=250):
        """Return a list of normalized call dicts (newest first).

        Tries multiple CSV endpoint variants (newer and older firmware).
        """
        sid = self._get_valid_sid()
        if not sid:
            return []

        urls = [
            "http://%s/fon_num/foncalls_list.lua?sid=%s&csv=&max=%d" % (
                self.host, sid, max_entries),
            "http://%s/fon_num/foncalls_list.lua?sid=%s&csv=" % (
                self.host, sid),
            "http://%s/fon_num/foncalls.lua?csv=&sid=%s&max=%d" % (
                self.host, sid, max_entries),
            "http://%s/fon_num/foncalls.lua?csv=1&sid=%s" % (self.host, sid),
        ]
        csv_text = None
        for url in urls:
            try:
                resp = urlopen(url, timeout=self.timeout)
                raw = resp.read()
                if isinstance(raw, bytes):
                    try:
                        csv_text = raw.decode("utf-8")
                    except Exception:
                        csv_text = raw.decode("latin-1")
                else:
                    csv_text = raw
                # Verify we got CSV, not an HTML error/login page
                if csv_text and not csv_text.strip().startswith("<"):
                    break
                csv_text = None
            except Exception:
                continue

        if not csv_text:
            return []

        rows = parse_call_list_csv(csv_text)
        calls = [normalize_call(r) for r in rows]
        # Populate phonebook cache from entries that already have names
        for call in calls:
            name = call.get("name", "")
            number = normalize_number(call.get("number", ""))
            if name and number and number not in self._phonebook_cache:
                self._phonebook_cache[number] = name
        return calls

    def refresh_phonebook(self):
        """Fetch the first internal phonebook via TR-064 and cache number→name.

        Returns the cache dict.  Silently returns the current cache on error.
        """
        try:
            url = self._get_phonebook_url(phonebook_id=0)
            if not url:
                return self._phonebook_cache
            resp = urlopen(url, timeout=self.timeout)
            raw = resp.read()
            xml_text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            self._parse_phonebook_xml(xml_text)
        except Exception:
            pass
        return self._phonebook_cache

    def resolve_number(self, number):
        """Look up *number* in the cached phonebook.

        Returns the contact name, or the original number if not found.
        """
        if not number:
            return number
        key = normalize_number(number)
        # Exact match
        if key in self._phonebook_cache:
            return self._phonebook_cache[key]
        # Try suffix match (local vs. international format)
        for cached_num, name in self._phonebook_cache.items():
            if cached_num and key and (
                cached_num.endswith(key) or key.endswith(cached_num)
            ):
                return name
        return number

    # ------------------------------------------------------------------
    # SID authentication helpers
    # ------------------------------------------------------------------

    def _get_valid_sid(self):
        """Return cached SID if still valid, else acquire a new one."""
        if self._sid and self._sid != "0000000000000000":
            return self._sid
        self._sid = self._acquire_sid()
        return self._sid

    def _acquire_sid(self):
        """Perform the two-step SID login and return the SID string."""
        login_url = "http://%s/login_sid.lua" % self.host
        try:
            resp = urlopen(login_url, timeout=self.timeout)
            xml_text = resp.read()
            if isinstance(xml_text, bytes):
                xml_text = xml_text.decode("utf-8")
        except Exception:
            return None

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None

        sid = (root.findtext("SID") or "").strip()
        if sid and sid != "0000000000000000":
            return sid

        challenge = (root.findtext("Challenge") or "").strip()
        if not challenge:
            return None

        # MD5 challenge-response (UTF-16LE as required by AVM)
        response_str = "%s-%s" % (challenge, self.password)
        try:
            md5 = hashlib.md5(response_str.encode("utf-16-le")).hexdigest()
        except Exception:
            return None
        response = "%s-%s" % (challenge, md5)

        payload = urlencode({
            "username": self.username,
            "response": response,
        })
        if _PY2:
            payload = payload.encode("utf-8") if isinstance(payload, str) else payload
        else:
            payload = payload.encode("utf-8")

        try:
            req = Request(login_url, payload)
            resp = urlopen(req, timeout=self.timeout)
            xml_text = resp.read()
            if isinstance(xml_text, bytes):
                xml_text = xml_text.decode("utf-8")
            root = ET.fromstring(xml_text)
            return (root.findtext("SID") or "").strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # TR-064 / phonebook helpers
    # ------------------------------------------------------------------

    def _basic_auth_header(self):
        credentials = "%s:%s" % (self.username, self.password)
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        return "Basic %s" % encoded

    def _soap_request(self, service_path, action, namespace, params=None):
        """Execute a TR-064 SOAP call; return parsed ElementTree root or None."""
        params_xml = ""
        for key, value in (params or {}).items():
            params_xml += "<%s>%s</%s>" % (key, value, key)

        body = _SOAP_TEMPLATE.format(
            action=action, ns=namespace, params=params_xml
        )

        url = "http://%s:49000%s" % (self.host, service_path)
        body_bytes = body.encode("utf-8")
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": '"%s#%s"' % (namespace, action),
            "Authorization": self._basic_auth_header(),
        }
        req = Request(url, body_bytes, headers)
        try:
            resp = urlopen(req, timeout=self.timeout)
            raw = resp.read()
            xml_text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            return ET.fromstring(xml_text)
        except Exception:
            return None

    def _get_phonebook_url(self, phonebook_id=0):
        """Return the download URL for a FritzBox internal phonebook."""
        ns = "urn:dslforum-org:service:X_AVM-DE_OnTel:1"
        root = self._soap_request(
            "/upnp/control/x_contact",
            "GetPhonebook",
            ns,
            {"NewPhonebookID": str(phonebook_id)},
        )
        if root is None:
            return None
        # The URL is in NewPhonebookURL (may be namespaced)
        for elem in root.iter():
            if elem.tag.endswith("NewPhonebookURL"):
                return (elem.text or "").strip()
        return None

    def _parse_phonebook_xml(self, xml_text):
        """Parse Fritz!Box phonebook XML and update the internal cache."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return

        for contact in root.iter("contact"):
            name_elem = contact.find("person/realName")
            if name_elem is None:
                continue
            name = (name_elem.text or "").strip()
            if not name:
                continue
            for number_elem in contact.iter("number"):
                raw_number = (number_elem.text or "").strip()
                key = normalize_number(raw_number)
                if key:
                    self._phonebook_cache[key] = name
