"""Diagnóstico rápido: descobre padCodes e testa o Telegram.

Uso:
    python tools/diagnose.py
"""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import requests
from slayer_monitor.vmos_client import VmosClient, VmosApiError, CONTENT_TYPE, SIGNED_HEADERS, SERVICE_NAME
import hashlib, hmac
from datetime import datetime, timezone


def _utc_iso_basic() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sign_raw(ak: str, sk: str, host: str, body: str, x_date: str) -> str:
    x_content_sha256 = hashlib.sha256(body.encode()).hexdigest()
    canonical = (
        f"host:{host}\n"
        f"x-date:{x_date}\n"
        f"content-type:{CONTENT_TYPE}\n"
        f"signedHeaders:{SIGNED_HEADERS}\n"
        f"x-content-sha256:{x_content_sha256}"
    )
    short_date = x_date[:8]
    credential_scope = f"{short_date}/{SERVICE_NAME}/request"
    canonical_hash = hashlib.sha256(canonical.encode()).hexdigest()
    string_to_sign = f"HMAC-SHA256\n{x_date}\n{credential_scope}\n{canonical_hash}"
    k_date = hmac.new(sk.encode(), short_date.encode(), hashlib.sha256).digest()
    k_service = hmac.new(k_date, SERVICE_NAME.encode(), hashlib.sha256).digest()
    signing_key = hmac.new(k_service, b"request", hashlib.sha256).digest()
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return (
        f"HMAC-SHA256 Credential={ak}, "
        f"SignedHeaders={SIGNED_HEADERS}, "
        f"Signature={signature}"
    )


def post_raw(ak, sk, host, path, payload):
    body = json.dumps(payload, separators=(",", ":"))
    x_date = _utc_iso_basic()
    auth = _sign_raw(ak, sk, host, body, x_date)
    headers = {
        "Content-Type": CONTENT_TYPE,
        "x-date": x_date,
        "x-host": host,
        "Host": host,
        "Authorization": auth,
    }
    r = requests.post(f"https://{host}{path}", data=body.encode(), headers=headers, timeout=20)
    return r.status_code, r.text


def main():
    from slayer_monitor.config import PROVIDER_PROFILES

    provider = os.getenv("CLOUD_PROVIDER", "vmos").strip().lower() or "vmos"
    if provider not in PROVIDER_PROFILES:
        print(f"❌  CLOUD_PROVIDER inválido: {provider!r}")
        return
    prefix_env = provider.upper()  # ex: "VMOS", "VSPHONE"
    profile = PROVIDER_PROFILES[provider]
    path_prefix = profile["path_prefix"]

    ak = os.getenv(f"{prefix_env}_ACCESS_KEY", "")
    sk = os.getenv(f"{prefix_env}_SECRET_KEY", "")
    host = os.getenv(f"{prefix_env}_API_HOST", profile["default_host"])
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")

    if not ak or not sk:
        print(f"❌  {prefix_env}_ACCESS_KEY ou {prefix_env}_SECRET_KEY não definidos no .env")
        return

    print("=" * 60)
    print(f"DIAGNÓSTICO — {provider.upper()} (host={host}, prefix={path_prefix})")
    print("=" * 60)

    # Tenta buscar lista de instâncias sem filtrar por padCode
    endpoints_to_try = [
        (f"{path_prefix}/padList", {}),
        (f"{path_prefix}/padDetails", {}),
        (f"{path_prefix}/padDetails", {"padCodes": []}),
        (f"{path_prefix}/padProperties", {}),
    ]

    found_codes: list[str] = []
    for path, payload in endpoints_to_try:
        code, text = post_raw(ak, sk, host, path, payload)
        print(f"\n  Endpoint {path}")
        print(f"  HTTP {code} → {text[:400]}")
        try:
            data = json.loads(text)
            # Procura padCode em qualquer nível de aninhamento
            raw = json.dumps(data)
            import re
            hits = re.findall(r'"padCode"\s*:\s*"([^"]+)"', raw)
            if hits:
                found_codes.extend(hits)
                print(f"  ✅  padCodes encontrados: {hits}")
        except Exception:
            pass

    if found_codes:
        unique = list(dict.fromkeys(found_codes))
        print(f"\n🎯  Seus padCodes reais: {unique}")
        print(f"    Atualize {prefix_env}_PAD_CODES no .env com um desses valores.")
    else:
        print(
            f"\n⚠   Não encontrei padCodes automaticamente.\n"
            f"    Verifique no painel web do {provider.upper()} o 'Instance ID' ou\n"
            f"    'Device Code' da sua instância e atualize {prefix_env}_PAD_CODES no .env."
        )

    # ------------------------------------------------------------------ Apps instalados
    print("\n" + "=" * 60)
    print("APPS INSTALADOS NA INSTÂNCIA")
    print("=" * 60)

    pad_codes_env = os.getenv(f"{prefix_env}_PAD_CODES", "")
    pad_codes = [p.strip() for p in pad_codes_env.split(",") if p.strip()]

    if not pad_codes:
        print(f"⚠   {prefix_env}_PAD_CODES não definido no .env — pulando listagem de apps.")
    else:
        for pad_code in pad_codes:
            status, text = post_raw(ak, sk, host, f"{path_prefix}/listInstalledApp",
                                    {"padCodes": [pad_code]})
            print(f"\n  Instância: {pad_code}  (HTTP {status})")
            try:
                data = json.loads(text)
                # Navega na resposta para encontrar a lista de apps
                payload = data.get("data") or []
                if isinstance(payload, dict):
                    for k in ("pageData", "list", "data", "rows"):
                        if isinstance(payload.get(k), list):
                            payload = payload[k]
                            break

                all_apps: list[dict] = []
                for row in payload if isinstance(payload, list) else []:
                    all_apps.extend(row.get("apps") or [])

                if not all_apps:
                    print("  ⚠   Nenhum app retornado. Resposta bruta:")
                    print(f"  {text[:600]}")
                else:
                    slayer_hits = []
                    print(f"  {len(all_apps)} apps instalados:")
                    for app in sorted(all_apps, key=lambda a: a.get("packageName", "")):
                        pkg = app.get("packageName", "?")
                        name = app.get("appName", "")
                        print(f"    {pkg}  ({name})")
                        if "slayer" in pkg.lower() or "superplanet" in pkg.lower():
                            slayer_hits.append(pkg)
                    if slayer_hits:
                        print(f"\n  🎯  Pacote do Slayer Legend encontrado: {slayer_hits}")
                        print(f"      Atualize GAME_PACKAGE no .env com esse valor.")
                    else:
                        print("\n  ⚠   Nenhum pacote com 'slayer' ou 'superplanet' encontrado.")
                        print("      O jogo pode não estar instalado, ou pode ter outro nome.")
            except Exception as exc:
                print(f"  ❌  Erro ao parsear resposta: {exc}")
                print(f"  Resposta bruta: {text[:600]}")

    # ------------------------------------------------------------------ Telegram
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO — Telegram")
    print("=" * 60)

    if not tg_token:
        print("❌  TELEGRAM_BOT_TOKEN não definido.")
        return

    # Testa o token
    r = requests.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=10)
    if r.status_code != 200:
        print(f"❌  Token inválido: {r.text}")
        return

    bot_info = r.json().get("result", {})
    print(f"✅  Bot válido: @{bot_info.get('username')} ({bot_info.get('first_name')})")

    # Busca atualizações (mostra chat_id de quem enviou mensagem ao bot)
    r2 = requests.get(f"https://api.telegram.org/bot{tg_token}/getUpdates", timeout=10)
    updates = r2.json().get("result", [])

    if not updates:
        print(
            "\n⚠   Nenhuma mensagem encontrada para o bot.\n"
            "    👉  Vá ao Telegram, abra o chat com seu bot e envie qualquer\n"
            "        mensagem (ex: /start). Depois rode este script de novo."
        )
    else:
        print("\nChats que interagiram com o bot:")
        seen = set()
        for upd in updates:
            msg = upd.get("message") or upd.get("channel_post") or {}
            chat = msg.get("chat", {})
            cid = chat.get("id")
            cname = chat.get("username") or chat.get("title") or chat.get("first_name", "?")
            if cid and cid not in seen:
                seen.add(cid)
                print(f"  chat_id={cid}  ({cname})")
        print(
            "\n🎯  Copie o chat_id correto acima e coloque em TELEGRAM_CHAT_ID no .env."
        )

    # Testa envio para o chat_id configurado
    if tg_chat:
        r3 = requests.post(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            data={"chat_id": tg_chat, "text": "✅ Monitor Slayer Legend — teste de conexão OK!"},
            timeout=10,
        )
        if r3.status_code == 200:
            print(f"\n✅  Mensagem de teste enviada para chat_id={tg_chat}!")
        else:
            print(f"\n❌  Falha ao enviar para chat_id={tg_chat}: {r3.text}")


if __name__ == "__main__":
    main()
