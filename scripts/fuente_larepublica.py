"""
Respaldo: lee indicadores desde las páginas individuales de larepublica.co.

Por qué no la portada: la marquesina de la home la arma JavaScript en el
navegador, así que el HTML crudo no la trae. Las páginas de cada indicador,
en cambio, vienen renderizadas desde el servidor.

Cómo se leen: no por clase CSS (cambian sin aviso) sino por ancla de texto.
Se busca el encabezado del indicador y se toman los tres números que vienen
inmediatamente después: valor, variación absoluta y variación porcentual.

    TASA DE USURA CRÉDITO CONSUMO   29,24%   -0,42%   -1,42%
                                    valor    cambio   porcentaje

Cita siempre la fuente real del dato (Banco de la República, Superfinanciera,
BVC), no este intermediario.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

BASE = "https://www.larepublica.co/indicadores-economicos"
UA = {"User-Agent": "marquesina-indicadores/1.0 (contacto: tu-correo@dominio.co)"}

# clave interna -> (ruta, texto que antecede a los números en la página)
PAGINAS = {
    "colcap": ("/movimiento-accionario/msci-colcap", "MSCI COLCAP"),
    "dtf":    ("/bancos/dtf", "DTF"),
    "uvr":    ("/bancos/uvr", "UVR"),
    "usura":  ("/bancos/tasa-de-usura", "TASA DE USURA CRÉDITO CONSUMO"),
}

# Un número al estilo colombiano, con o sin moneda, signo o porcentaje:
#   $ 3.140,55   -US$ 0,12   +45,07   -1,42%   29,24%
NUM = r"[-+]?\s?(?:US\$|\$)?\s?\d{1,3}(?:\.\d{3})*(?:,\d+)?\s?%?"
TRIO = re.compile(NUM + r"\s+" + NUM + r"\s+" + NUM)
UNO = re.compile(NUM)

TILDES = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")


def normalizar(t: str) -> str:
    return " ".join(t.upper().translate(TILDES).split())


def a_numero(texto: str) -> float:
    limpio = re.sub(r"[^\d,.\-+]", "", texto)
    limpio = limpio.replace(".", "").replace(",", ".")
    if limpio in ("", "-", "+"):
        raise ValueError("no es numero: " + repr(texto))
    return float(limpio)


def extraer(texto_plano: str, encabezado: str) -> dict:
    """Busca el encabezado y devuelve {'valor':…, 'anterior':…}."""
    plano = normalizar(texto_plano)
    ancla = normalizar(encabezado)

    # El encabezado puede aparecer varias veces (menú, título, tabla). Se
    # prueba cada ocurrencia hasta que una traiga tres números detrás.
    for m in re.finditer(re.escape(ancla), plano):
        ventana = plano[m.end(): m.end() + 120]
        trio = TRIO.search(ventana)
        if not trio:
            continue
        partes = UNO.findall(trio.group(0))
        if len(partes) < 2:
            continue
        try:
            valor = a_numero(partes[0])
            cambio = a_numero(partes[1])
        except ValueError:
            continue
        return {"valor": valor, "anterior": valor - cambio}
    raise ValueError("no se encontraron valores para " + repr(encabezado))


def leer_pagina(clave: str, timeout: int = 20) -> dict:
    ruta, encabezado = PAGINAS[clave]
    r = requests.get(BASE + ruta, headers=UA, timeout=timeout)
    r.raise_for_status()
    texto = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    return extraer(texto, encabezado)


def descargar(claves=None) -> dict:
    """Lee las claves pedidas. Lo que falle se omite, no rompe el resto."""
    datos = {}
    for clave in (claves or PAGINAS):
        if clave not in PAGINAS:
            continue
        try:
            datos[clave] = leer_pagina(clave)
        except Exception as e:                      # noqa: BLE001
            print("     LR " + clave + ": " + type(e).__name__ + ": " + str(e))
    return datos


if __name__ == "__main__":
    import json
    print(json.dumps(descargar(), ensure_ascii=False, indent=2))
