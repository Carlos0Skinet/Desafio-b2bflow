#!/usr/bin/env python3

import os
import time
import logging
from typing import List, Dict, Any, Tuple

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_INSTANCE_TOKEN = os.getenv("ZAPI_INSTANCE_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

MESSAGE_TEMPLATE = os.getenv("MESSAGE_TEMPLATE")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

if not all([SUPABASE_URL, SUPABASE_KEY, ZAPI_INSTANCE_ID, ZAPI_INSTANCE_TOKEN, ZAPI_CLIENT_TOKEN]):
    logger.error("Variáveis de ambiente faltando. Verifique seu .env")
    raise SystemExit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def buscar_contatos(limit: int = 3) -> List[Dict[str, Any]]:
    try:
        resp = supabase.table("tabela_contatos").select("id, nome, numero, Status").limit(100).execute()
    except Exception:
        logger.exception("Erro ao consultar Supabase")
        return []

    data = resp.data if hasattr(resp, "data") else (resp.get("data") if isinstance(resp, dict) else None)
    if not data:
        logger.info("Nenhum dado retornado do Supabase.")
        return []

    pending = [r for r in data if (r.get("Status") is None or str(r.get("Status")).strip() == "")]
    logger.info("Contatos com Status pendente encontrados: %d", len(pending))
    return pending[:limit]


def marcar_status(contact_id: int, status_text: str) -> bool:
    try:
        upd = supabase.table("tabela_contatos").update({"Status": status_text}).eq("id", contact_id).execute()
    except Exception:
        logger.exception("Erro ao atualizar Status no Supabase para id=%s", contact_id)
        return False

    err = getattr(upd, "error", None) if hasattr(upd, "error") else (upd.get("error") if isinstance(upd, dict) else None)
    if err:
        logger.error("Supabase retornou erro ao atualizar id=%s: %s", contact_id, err)
        return False

    logger.debug("Status atualizado para id=%s -> %s", contact_id, status_text)
    return True


def enviar_mensagem(telefone: str, nome: str) -> Tuple[bool, str]:
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_INSTANCE_TOKEN}/send-text"
    payload = {
        "phone": telefone,
        "message": MESSAGE_TEMPLATE.format(nome=nome)  
    }
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_CLIENT_TOKEN
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
    except requests.RequestException as e:
        logger.exception("Erro de requisição ao Z-API para %s (%s)", nome, telefone)
        return False, str(e)

    if resp.status_code == 200:
        return True, "OK"
    else:
        try:
            txt = resp.text
        except Exception:
            txt = f"status_code={resp.status_code}"
        return False, f"{resp.status_code}: {txt}"


def main():
    contatos = buscar_contatos(limit=3)
    if not contatos:
        logger.info("Nenhum contato pendente. Encerrando.")
        return

    sent = 0
    for contato in contatos:
        contact_id = contato.get("id")
        nome = contato.get("nome") or "Contato"
        numero = contato.get("numero")

        if not numero:
            logger.warning("Contato sem número (ignorando): %s", contato)
            marcar_status(contact_id, "ERROR: missing number")
            continue

        ok, msg = enviar_mensagem(numero, nome)
        if ok:
            logger.info("Enviado para %s (%s)", nome, numero)
            marcado = marcar_status(contact_id, "feito")
            if not marcado:
                logger.warning("Não foi possível marcar Status='feito' para id=%s", contact_id)
            sent += 1
        else:
            logger.error("Falha ao enviar para %s (%s): %s", nome, numero, msg)
            marcado = marcar_status(contact_id, f"ERROR: {msg}")
            if not marcado:
                logger.warning("Não foi possível marcar Status=ERROR para id=%s", contact_id)

        time.sleep(1)

    logger.info("Execução finalizada. Mensagens enviadas: %d", sent)


if __name__ == "__main__":
    main()
