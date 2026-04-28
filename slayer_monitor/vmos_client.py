"""VMOS Cloud OpenAPI client with HMAC-SHA256 (AK/SK) request signing.

Reference: https://cloud.vmoscloud.com/vmoscloud/doc/en/server/OpenAPI.html

Signing pipeline:
  1. canonicalString = host\\nx-date\\ncontent-type\\nsignedHeaders\\nx-content-sha256
  2. stringToSign    = "HMAC-SHA256\\n{xDate}\\n{credentialScope}\\n{sha256(canonical)}"
  3. signingKey      = HMAC(HMAC(HMAC(SK, shortDate), "armcloud-paas"), "request")
  4. signature       = HMAC(signingKey, stringToSign).hex()
  5. Authorization   = "HMAC-SHA256 Credential=AK, SignedHeaders=..., Signature=..."
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


SIGNED_HEADERS = "content-type;host;x-content-sha256;x-date"
SERVICE_NAME = "armcloud-paas"
CONTENT_TYPE = "application/json;charset=UTF-8"


@dataclass
class PadStatus:
    pad_code: str
    online: bool
    pad_status: int
    device_status: int
    raw: Dict[str, Any]

    @property
    def is_running(self) -> bool:
        # padStatus 10 == running per VMOS docs.
        return self.online and self.pad_status == 10


class VmosApiError(RuntimeError):
    """Raised when the VMOS API returns a non-success response."""


class VmosClient:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        api_host: str = "api.vmoscloud.com",
        timeout: int = 20,
    ) -> None:
        self._ak = access_key
        self._sk = secret_key.encode("utf-8")
        self._host = api_host
        self._timeout = timeout
        self._base_url = f"https://{api_host}"

    # ------------------------------------------------------------------ signing

    @staticmethod
    def _utc_iso_basic() -> str:
        # Format documented as 20201103T104027Z (basic ISO 8601, UTC).
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _sign(self, body: str, x_date: str) -> str:
        x_content_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()

        canonical = (
            f"host:{self._host}\n"
            f"x-date:{x_date}\n"
            f"content-type:{CONTENT_TYPE}\n"
            f"signedHeaders:{SIGNED_HEADERS}\n"
            f"x-content-sha256:{x_content_sha256}"
        )

        short_date = x_date[:8]
        credential_scope = f"{short_date}/{SERVICE_NAME}/request"
        canonical_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        string_to_sign = (
            f"HMAC-SHA256\n{x_date}\n{credential_scope}\n{canonical_hash}"
        )

        k_date = hmac.new(self._sk, short_date.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_date, SERVICE_NAME.encode(), hashlib.sha256).digest()
        signing_key = hmac.new(k_service, b"request", hashlib.sha256).digest()
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return (
            f"HMAC-SHA256 Credential={self._ak}, "
            f"SignedHeaders={SIGNED_HEADERS}, "
            f"Signature={signature}"
        )

    # ----------------------------------------------------------------- transport

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # JSON serialisation must match what was hashed → use the same separators.
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        x_date = self._utc_iso_basic()
        authorization = self._sign(body, x_date)

        headers = {
            "Content-Type": CONTENT_TYPE,
            "x-date": x_date,
            "x-host": self._host,
            "Host": self._host,
            "Authorization": authorization,
        }

        url = f"{self._base_url}{path}"
        response = requests.post(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=self._timeout,
        )

        if response.status_code != 200:
            raise VmosApiError(
                f"HTTP {response.status_code} em {path}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise VmosApiError(f"Resposta não-JSON em {path}: {response.text[:300]}") from exc

        if isinstance(data, dict) and data.get("code") not in (None, 200, 0, "0"):
            raise VmosApiError(
                f"VMOS retornou erro {data.get('code')}: {data.get('msg') or data}"
            )
        return data

    # ------------------------------------------------------------------ endpoints

    def pad_details(self, pad_codes: List[str]) -> List[PadStatus]:
        data = self._post(
            "/vcpcloud/api/padApi/padDetails",
            {"padCodes": pad_codes},
        )
        rows = _extract_rows(data)
        result: List[PadStatus] = []
        for row in rows:
            result.append(
                PadStatus(
                    pad_code=str(row.get("padCode", "")),
                    online=int(row.get("online", 0)) == 1,
                    pad_status=int(row.get("padStatus", -1)),
                    device_status=int(row.get("deviceStatus", -1)),
                    raw=row,
                )
            )
        return result

    def list_installed_apps(self, pad_codes: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        data = self._post(
            "/vcpcloud/api/padApi/listInstalledApp",
            {"padCodes": pad_codes},
        )
        rows = _extract_rows(data)
        installed: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            installed[str(row.get("padCode", ""))] = list(row.get("apps") or [])
        return installed

    def has_package_installed(
        self,
        pad_code: str,
        package_name: str,
        cached: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> bool:
        installed = cached if cached is not None else self.list_installed_apps([pad_code])
        for app in installed.get(pad_code, []):
            if str(app.get("packageName", "")).lower() == package_name.lower():
                return True
        return False

    def start_app(self, pad_code: str, package_name: str) -> Dict[str, Any]:
        return self._post(
            "/vcpcloud/api/padApi/startApp",
            {"padCodes": [pad_code], "packageName": package_name},
        )

    def get_screenshot_url(
        self,
        pad_code: str,
        *,
        width: int = 720,
        height: int = 1280,
        quality: int = 60,
        fmt: str = "png",
    ) -> Optional[str]:
        """Retorna a URL de um screenshot atual da instância (vence em alguns minutos)."""
        data = self._post(
            "/vcpcloud/api/padApi/getLongGenerateUrl",
            {
                "padCodes": [pad_code],
                "format": fmt,
                "height": height,
                "width": width,
                "quality": quality,
            },
        )
        rows = _extract_rows(data)
        for row in rows:
            if row.get("padCode") == pad_code and row.get("success", True):
                url = row.get("url")
                if url:
                    return str(url)
        return None

    def fetch_screenshot(
        self,
        pad_code: str,
        *,
        width: int = 720,
        height: int = 1280,
        quality: int = 60,
    ) -> Optional[bytes]:
        """Baixa o PNG/JPG do screenshot atual. Retorna None se a API não fornecer URL."""
        url = self.get_screenshot_url(
            pad_code, width=width, height=height, quality=quality
        )
        if not url:
            return None
        response = requests.get(url, timeout=self._timeout)
        if response.status_code != 200:
            return None
        return response.content


def _extract_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """VMOS responses wrap the payload under data.{pageData|list|data} or data."""
    payload = data.get("data") if isinstance(data, dict) else None
    if payload is None:
        return []
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        for key in ("pageData", "list", "data", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return list(value)
    return []
