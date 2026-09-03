# Marquesina de indicadores

Cinta de indicadores económicos que se alimenta sola: un script en Python corre
en GitHub Actions, escribe `data/indicadores.json` y el front lo lee.

```
index.html                        la cinta
data/indicadores.json             lo genera el bot (no lo edites a mano)
data/manual.json                  lo editas tú: usura, DTF, UVR, COLCAP
scripts/actualizar_indicadores.py el orquestador
scripts/fuente_larepublica.py     respaldo: lee la cinta de larepublica.co
.github/workflows/indicadores.yml el cron
```

## Montaje

1. Crea un repo público y sube estos archivos.
2. Settings → Actions → General → Workflow permissions: **Read and write**.
   Sin esto el bot no puede hacer commit del JSON.
3. Settings → Pages → Source: *Deploy from a branch*, rama `main`, carpeta `/`.
4. Actions → *Actualizar indicadores* → **Run workflow** para la primera corrida.
5. Abre `https://USUARIO.github.io/REPO/`.

Prueba local antes de subir: `pip install requests && python scripts/actualizar_indicadores.py`

## Fuentes

| Indicador | Fuente | Estado |
|---|---|---|
| TRM | datos.gov.co, dataset `32sa-8pi3` (Superfinanciera) | automático, oficial |
| Bitcoin | CoinGecko, plan gratuito | automático |
| WTI, oro, café | Stooq (CSV) | automático, **verifica los símbolos** |
| DTF, UVR, usura, COLCAP | portada de larepublica.co (respaldo) | automático, frágil |
| lo que falle | `data/manual.json` | manual |

El orden de precedencia es: fuente oficial → respaldo de La República → valor
manual. Cada dato queda marcado con `"fuente"` para que sepas de dónde salió.

Los cuatro manuales cambian con baja frecuencia: la usura es mensual (resolución
de la Superfinanciera), la DTF semanal, la UVR mensual por boletín de la Junta.
Programar un scraper para ellos es posible, pero el portal de estadísticas del
Banrep es una app JavaScript y la Superfinanciera publica en Excel: son frágiles.
Editar un JSON una vez al mes cuesta menos que mantener ese scraper.

El café de Stooq es el contrato KC de ICE, no el "Colombian Milds". Si necesitas
el precio interno de referencia, la fuente es la Federación Nacional de Cafeteros.

## Reglas de robustez ya implementadas

- Si una fuente falla, se conserva el último valor bueno con `"obsoleto": true`
  y la cinta lo muestra atenuado. El job nunca queda en rojo por eso.
- El commit solo ocurre si el JSON cambió, para no llenar el historial de ruido.
- Si la fuente no da el valor anterior, se toma el de la corrida previa.

## Embeber la cinta en otro sitio

Copia el `<div class="cinta">`, el CSS y el `<script>`, y apunta `RUTA_JSON` a
`https://raw.githubusercontent.com/USUARIO/REPO/main/data/indicadores.json`,
que responde con cabecera CORS abierta.
