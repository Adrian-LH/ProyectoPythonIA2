# Documento de pruebas de la API

Pruebas sobre `POST /analizar` con el `auth.log` generado con la semilla del grupo, `--seed 123` (14.391 líneas, 384 IPs, 100 atacantes según `etiquetas.csv`). Al entrenar, `entrenar.py` dio precisión, recall y F1 de 1,000 en las 96 IPs de prueba.
La API se arrancó con `uvicorn api:app --reload` y las peticiones se lanzaron desde PowerShell con `Invoke-RestMethod`.

## Cómo repetirlas

```powershell
function Probar($nombre, $datos) {
    "===== $nombre ====="
    $json = $datos | ConvertTo-Json
    try {
        $res = Invoke-RestMethod -Uri http://127.0.0.1:8000/analizar -Method Post -Body $json -ContentType "application/json; charset=utf-8"
        "Codigo 200 | ignoradas: $($res.lineas_ignoradas) | analizadas: $($res.ips_analizadas) | sospechosas: $($res.sospechosas.Count)"
        $res.sospechosas | Select-Object -First 2 | Format-List | Out-String
    } catch {
        "Codigo $($_.Exception.Response.StatusCode.value__)"
        $_.ErrorDetails.Message
    }
}
$lineas = [System.IO.File]::ReadAllLines("$PWD\auth.log")
```

> En Windows PowerShell hay que leer el log con `ReadAllLines` y no con `Get-Content`: este último añade propiedades a cada línea y al pasarlo a JSON se envían como objetos, no como texto (la API lo rechaza con un 422).

## Prueba 1: petición correcta

```powershell
Probar "1. Peticion correcta" @{ lineas = $lineas; umbral = 0.7; lista_blanca = @() }
```

- **Esperado:** código 200, todas las líneas reconocidas, las 384 IPs analizadas y alrededor de 100 sospechosas, cada una con `ip`, `probabilidad` y `motivo`.
- **Obtenido:** código 200, `lineas_ignoradas: 0`, `ips_analizadas: 384`, **99 sospechosas**. La primera:
  ```
  ip           : 192.168.2.105
  probabilidad : 1,0
  motivo       : prueba 12 usuarios distintos; 206 eventos con usuarios inexistentes; 103 fallos de contrasena en 5 minutos
  ```
- **Conclusión:** correcto. El resultado es casi perfecto porque el modelo se entrenó con el 75 % de este mismo log; con datos nuevos sería peor (ver informe).

## Prueba 2: con lista blanca

```powershell
Probar "2. Con lista blanca (192.168.2.105)" @{ lineas = $lineas; umbral = 0.7; lista_blanca = @("192.168.2.105") }
```

- **Esperado:** código 200 y la misma respuesta que en la prueba 1, pero sin `192.168.2.105` (la primera sospechosa de la prueba 1) aunque su probabilidad sea 1,0.
- **Obtenido:** código 200, **98 sospechosas**. La lista empieza ya por `192.168.2.118`; `192.168.2.105` no aparece.
- **Conclusión:** correcto. La lista blanca se aplica después del modelo, así que una IP de la lista nunca se marca, sea cual sea su probabilidad.

## Prueba 3: umbral fuera de rango

```powershell
Probar "3. Umbral fuera de rango (1.5)" @{ lineas = $lineas; umbral = 1.5; lista_blanca = @() }
```

- **Esperado:** código 422 con un mensaje que indique qué campo está mal.
- **Obtenido:** código 422
  ```json
  {"error":"Datos de entrada no validos","detalles":["umbral: Input should be less than or equal to 1"]}
  ```
- **Conclusión:** correcto. La validación la hace pydantic antes de llegar al modelo, y el mensaje señala el campo `umbral`.

## Prueba 4: líneas basura

```powershell
Probar "4. Lineas basura" @{ lineas = @("hola que tal", "esto no es un log", "12345"); umbral = 0.7; lista_blanca = @() }
```

- **Esperado:** código 422, porque ninguna línea tiene formato de `auth.log` y no hay nada que analizar.
- **Obtenido:** código 422
  ```json
  {"error":"No hay nada que analizar","detalles":["Ninguna linea tiene el formato de auth.log de sshd"]}
  ```
- **Conclusión:** correcto. Si solo una parte de las líneas fuera basura, la API respondería 200 y las contaría en `lineas_ignoradas`.

## Resumen

| # | Prueba | Esperado | Obtenido | ¿OK? |
|---|--------|----------|----------|------|
| 1 | Petición correcta | 200, ~100 sospechosas | 200, 99 sospechosas, 0 ignoradas | Sí |
| 2 | Lista blanca | 200, sin la IP de la lista | 200, 98 sospechosas, IP excluida | Sí |
| 3 | Umbral = 1.5 | 422, error en `umbral` | 422, error en `umbral` | Sí |
| 4 | Líneas basura | 422, nada que analizar | 422, mensaje claro | Sí |

Todos los errores siguen el mismo formato: `{"error": "...", "detalles": [...]}`.

## Repetir las pruebas con curl (macOS / Linux)

```bash
python -c "import json; print(json.dumps({'lineas': open('auth.log').read().splitlines(), 'umbral': 0.7, 'lista_blanca': []}))" > peticion.json
curl -s -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" -d @peticion.json | head -c 600
curl -s -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" -d '{"lineas": ["x"], "umbral": 1.5}'
curl -s -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" -d '{"lineas": ["hola que tal", "esto no es un log", "12345"]}'
```

## Pruebas extra

Lanzadas con curl desde macOS, con la API arrancada con `uvicorn api:app`.

| # | Prueba | Petición | Esperado | Obtenido | ¿OK? |
|---|--------|----------|----------|----------|------|
| 5 | `GET /salud` | `curl http://127.0.0.1:8000/salud` | 200, `"estado": "ok"` y la lista de características | 200, `{"estado":"ok","modelo":"RandomForestClassifier","caracteristicas":[11 características],"max_lineas":50000}` | Sí |
| 6 | Cuerpo mal formado | `curl -X POST .../analizar -H "Content-Type: application/json" -d '{esto no es json'` | 422, `"Datos de entrada no validos"` | 422, `{"error":"Datos de entrada no validos","detalles":["1: JSON decode error"]}` | Sí |
| 7 | IP no válida en la lista blanca | `-d '{"lineas": ["x"], "lista_blanca": ["no-es-una-ip"]}'` | 422, `"lista_blanca: ... no es una IP valida"` | 422, `{"error":"Datos de entrada no validos","detalles":["lista_blanca: Value error, 'no-es-una-ip' no es una IP valida"]}` | Sí |
| 8 | Basura mezclada con una línea buena | una línea válida y dos de basura | 200, `lineas_ignoradas: 2`, `ips_analizadas: 1` | 200, `{"lineas_ignoradas":2,"ips_analizadas":1,"sospechosas":[]}` | Sí |

En la prueba 8 no sale ninguna sospechosa: un solo fallo de contraseña no basta para que el modelo marque la IP, y es lo razonable.

## Pruebas automáticas

`test_api.py` repite todas estas pruebas con pytest y el `TestClient` de FastAPI (sin arrancar el servidor), y además comprueba el límite de 50.000 líneas, la lista de líneas vacía y que con umbral 0 se marcan todas las IPs.

```bash
pytest -v
```

Resultado (modelo entrenado con la semilla 123):

```
test_api.py::test_salud PASSED
test_api.py::test_peticion_correcta PASSED
test_api.py::test_lista_blanca PASSED
test_api.py::test_umbral_cero_marca_todas_menos_lista_blanca PASSED
test_api.py::test_umbral_fuera_de_rango[1.5] PASSED
test_api.py::test_umbral_fuera_de_rango[-0.1] PASSED
test_api.py::test_umbral_fuera_de_rango[alto] PASSED
test_api.py::test_lineas_basura PASSED
test_api.py::test_mezcla_basura_y_lineas_validas PASSED
test_api.py::test_cuerpo_mal_formado PASSED
test_api.py::test_falta_lineas PASSED
test_api.py::test_lista_de_lineas_vacia PASSED
test_api.py::test_ip_no_valida_en_lista_blanca PASSED
test_api.py::test_demasiadas_lineas PASSED
14 passed in 3.21s
```