#!/usr/bin/env python3
"""
Genera data/indicadores.json para la marquesina de indicadores.

Diseño:
  - Cada indicador tiene una función que devuelve (valor, anterior).
  - Si la fuente no entrega el valor anterior, se usa el que quedó guardado
    en la corrida previa. Por eso el JSON anterior se lee antes de empezar.
  - Si una fuente falla, NO se borra el dato: se conserva el último bueno y
    se marca con "obsoleto": true para que el front lo muestre atenuado.
  - Los indicadores que cambian poco (usura, COLCAP) se leen de
    data/manual.json, que se edita a mano o por otro proceso.

Ejecutar:  python scripts/actualizar_indicadores.py
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import sys
from datetime import datetime, timezone, timedelta

import requests

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "indicadores.json"
MANUAL = RAIZ / "data" / "manual.json"

TIMEOUT = 20
UA = {"User-Agent": "marquesina-indicadores/1.0 (contacto: tu-correo@dominio.co)"}
BOGOTA = timezone(timedelta(hours=-5))


# --------------------------------------------------------------------------
# FUENTES
# Cada función devuelve (valor, anterior_o_None) o lanza una excepción.
# --------------------------------------------------------------------------

def trm():
    """TRM oficial. Datos Abiertos Colombia (dataset de la Superfinanciera)."""
    url = "https://www.datos.gov.co/resource/32sa-8pi3.json"
    params = {"$select": "valor,vigenciadesde",
              "$order": "vigenciadesde DESC",
              "$limit": 2}
    d = requests.get(url, params=params, headers=UA, timeout=TIMEOUT).json()
    return float(d[0]["valor"]), float(d[1]["valor"])


def bitcoin():
    """Bitcoin en USD. CoinGecko, plan gratuito sin llave."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd",
              "include_24hr_change": "true"}
    d = requests.get(url, params=params, headers=UA, timeout=TIMEOUT).json()["bitcoin"]
    valor = float(d["usd"])
    anterior = valor / (1 + float(d["usd_24h_change"]) / 100)
    return valor, anterior


def yahoo(simbolo: str):
    """Precio y cierre anterior desde Yahoo Finance (sin llave, sin CORS).

    Sustituye a Stooq, que bloquea las IPs de los servidores de GitHub.
      CL=F -> WTI    GC=F -> oro onza troy    KC=F -> café arábica ICE
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
    r = requests.get(url, params={"range": "5d", "interval": "1d"},
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    meta = r.json()["chart"]["result"][0]["meta"]
    valor = float(meta["regularMarketPrice"])
    anterior = meta.get("previousClose") or meta.get("chartPreviousClose")
    return valor, (float(anterior) if anterior else None)


def wti():
    return yahoo("CL=F")


def oro_internacional():
    return yahoo("GC=F")


def cafe():
    # Contrato KC de ICE (arábica), no el "Colombian Milds" interno.
    return yahoo("KC=F")


FUENTES = {
    "trm": trm,
    "bitcoin": bitcoin,
    "wti": wti,
    "oro": oro_internacional,
    "cafe": cafe,
}

# Todo lo que la cinta necesita mostrar.
CLAVES = ["trm", "colcap", "wti", "cafe", "oro", "usura", "dtf", "uvr", "bitcoin"]

# Respaldo para lo que las fuentes de arriba no cubren (colcap, usura, dtf, uvr).
# Ver scripts/fuente_larepublica.py y la nota del README antes de activarlo.
USAR_RESPALDO_LR = True


# --------------------------------------------------------------------------
# MOTOR
# --------------------------------------------------------------------------

def leer_json(ruta: pathlib.Path) -> dict:
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"aviso: {ruta.name} ilegible, se ignora", file=sys.stderr)
    return {}


def main() -> int:
    previo = leer_json(SALIDA)
    manual = leer_json(MANUAL)
    ahora = datetime.now(BOGOTA)
    salida: dict = {}
    fallidos: list[str] = []

    for clave, fn in FUENTES.items():
        anterior_guardado = (previo.get(clave) or {}).get("valor")
        try:
            valor, anterior = fn()
            if anterior is None:
                anterior = anterior_guardado
            # Si el valor no cambió, conserva el "anterior" viejo para no
            # borrar la variación del día.
            if anterior is not None and float(anterior) == float(valor):
                anterior = (previo.get(clave) or {}).get("anterior", anterior)
            salida[clave] = {
                "valor": round(float(valor), 4),
                "anterior": round(float(anterior), 4) if anterior is not None else None,
                "actualizado": ahora.isoformat(timespec="seconds"),
            }
            print(f"ok   {clave:8} {valor}")
        except Exception as e:                      # noqa: BLE001
            fallidos.append(clave)
            print(f"FALL {clave:8} {type(e).__name__}: {e}", file=sys.stderr)
            if clave in previo:
                salida[clave] = {**previo[clave], "obsoleto": True}

    # Paso 2: respaldo. Solo para lo que quedó sin dato fresco.
    faltantes = [c for c in CLAVES
                 if c not in salida or salida[c].get("obsoleto")]
    if USAR_RESPALDO_LR and faltantes:
        try:
            from fuente_larepublica import descargar as leer_lr
            lr = leer_lr(faltantes)
            for clave in faltantes:
                if clave in lr:
                    salida[clave] = {
                        **lr[clave],
                        "actualizado": ahora.isoformat(timespec="seconds"),
                        "fuente": "larepublica",
                    }
                    if clave in fallidos:
                        fallidos.remove(clave)
                    print(f"resp {clave:8} {lr[clave]['valor']}")
        except Exception as e:                      # noqa: BLE001
            print(f"FALL respaldo LR: {type(e).__name__}: {e}", file=sys.stderr)

    # Paso 3: manuales. Solo rellenan lo que siga faltando.
    for clave, dato in manual.items():
        if clave not in salida or salida[clave].get("obsoleto"):
            salida[clave] = dato

    salida["_meta"] = {
        "generado": ahora.isoformat(timespec="seconds"),
        "fuentes_fallidas": fallidos,
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"escrito {SALIDA} ({len(salida) - 1} indicadores)")

    # Nunca falla el job por una fuente caída: el JSON anterior sigue sirviendo.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
