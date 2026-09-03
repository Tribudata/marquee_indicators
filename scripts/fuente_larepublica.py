"""
Fuente alterna: lee los nueve indicadores de la marquesina de larepublica.co
en una sola petición.

Por qué la portada y no las páginas individuales: la cinta de la portada trae
los nueve valores con su variación en un solo HTML, así que se hace 1 request
en vez de 9. La estructura es <ul class="list-first"> con un <li> por indicador
y cuatro <span>: nombre, valor, variación absoluta, variación porcentual.

Advertencia: esto depende del maquetado de un sitio de terceros y se rompe
cuando ellos lo cambien. Úsalo como respaldo, no como fuente principal, y cita
siempre el origen real del dato (Banco de la República, Superfinanciera, BVC).
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

PORTADA = "https://www.larepublica.co/"
UA = {"User-Agent": "marquesina-indicadores/1.0 (contacto: tu-correo@dominio.co)"}

# Cómo se llama cada indicador en la cinta -> clave interna del proyecto.
# La comparación se hace en mayúsculas y sin tildes, por si retocan el texto.
EQUIVALENCIAS = {
    "TRM": "trm",
    "MSCI COLCAP": "colcap",
    "PETROLEO WTI": "wti",
    "CAFE COLOMBIAN MILDS": "cafe",
    "ORO COMPRA BANCO DE LA REPUBLICA": "oro",
    "TASA DE USURA CREDITO CONSUMO": "usura",
    "DTF": "dtf",
    "UVR": "uvr",
    "BITCOIN": "bitcoin",
}

TILDES = str.maketrans("ÁÉÍÓÚÜÑ", "AEIOUUN")


def normalizar(texto: str) -> str:
    return " ".join(texto.strip().upper().translate(TILDES).split())


def a_numero(texto: str) -> float:
    """'$ 3.140,55' -> 3140.55   'US$ -1,14' -> -1.14   '-0,20%' -> -0.2"""
    limpio = re.sub(r"[^\d,.\-+]", "", texto)      # quita $, US$, %, espacios
    limpio = limpio.replace(".", "").replace(",", ".")   # formato colombiano
    if limpio in ("", "-", "+"):
        raise ValueError(f"no es número: {texto!r}")
    return float(limpio)


def leer_marquesina(html: str) -> dict[str, dict]:
    """Devuelve {clave: {'valor': float, 'anterior': float}} a partir del HTML."""
    sopa = BeautifulSoup(html, "html.parser")
    lista = sopa.select_one("ul.list-first") or sopa.select_one(".quote-banner ul")
    if lista is None:
        raise ValueError("no se encontró la cinta; cambió el maquetado")

    datos: dict[str, dict] = {}
    for li in lista.select("li"):
        spans = li.select("span")
        if len(spans) < 3:
            continue
        nombre = normalizar(spans[0].get_text())
        clave = EQUIVALENCIAS.get(nombre)
        if clave is None:
            continue
        try:
            valor = a_numero(spans[1].get_text())
            cambio = a_numero(spans[2].get_text())
        except ValueError:
            continue
        # El signo del cambio viene por la clase CSS, no siempre por el texto.
        clases = spans[2].get("class", [])
        if "down" in clases:
            cambio = -abs(cambio)
        elif "up" in clases:
            cambio = abs(cambio)
        datos[clave] = {"valor": valor, "anterior": valor - cambio}
    if not datos:
        raise ValueError("la cinta se leyó pero no coincidió ningún indicador")
    return datos


def descargar(timeout: int = 20) -> dict[str, dict]:
    r = requests.get(PORTADA, headers=UA, timeout=timeout)
    r.raise_for_status()
    return leer_marquesina(r.text)


if __name__ == "__main__":
    import json
    print(json.dumps(descargar(), ensure_ascii=False, indent=2))
