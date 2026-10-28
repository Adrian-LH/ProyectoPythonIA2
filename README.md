# Proyecto DAM: auditar e integrar un detector de intrusiones con IA

Detector de intrusiones SSH basado en Machine Learning, expuesto como API REST (FastAPI) y consumido desde una interfaz.

**Semilla del grupo: `123`** (todos generamos los datos con esta semilla).

## Instalación

    python -m venv .venv
    # Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
    pip install -r requirements.txt

## Generar datos y entrenar el modelo

    python generar_logs.py --seed 123 --salida auth.log --etiquetas etiquetas.csv
    python entrenar.py --log auth.log --etiquetas etiquetas.csv --salida modelo.joblib

Los logs, etiquetas y modelos no se suben al repositorio: se regeneran con estos comandos.

## Cuaderno de análisis

    jupyter notebook analisis.ipynb

## Arrancar la API

Necesita `modelo.joblib` (ver el apartado anterior). Con el entorno activado:

    uvicorn api:app --reload

- Documentación interactiva: http://127.0.0.1:8000/docs
- El modelo se carga una sola vez al arrancar: si se vuelve a entrenar, hay que reiniciar la API.
- La API solo informa de IPs sospechosas; no bloquea nada. La decisión final es de una persona.

| Método y ruta | Qué hace |
|---|---|
| `GET /salud` | Devuelve `{"estado": "ok"}`, el modelo cargado, las características que espera y el límite de líneas. |
| `POST /analizar` | Recibe `lineas` (lista de líneas de `auth.log`, máximo 50.000), `umbral` (0 a 1, por defecto 0.7) y `lista_blanca` (IPs que nunca se marcan). Devuelve `lineas_ignoradas`, `ips_analizadas` y `sospechosas` (cada una con `ip`, `probabilidad` y `motivo`). |

Errores: los datos inválidos (umbral fuera de rango, cuerpo mal formado, IP no válida en la lista blanca, demasiadas líneas o ninguna línea reconocible) devuelven **422** con este formato:

    {"error": "Datos de entrada no validos", "detalles": ["umbral: Input should be less than or equal to 1"]}

## Usar la interfaz

(pendiente)

## Ejemplos de peticiones

Con curl:

    curl http://127.0.0.1:8000/salud

    curl -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" -d "{\"lineas\": [\"Oct  7 03:00:01 srv-web01 sshd[1234]: Failed password for invalid user admin from 203.0.113.5 port 40000 ssh2\"], \"umbral\": 0.7, \"lista_blanca\": []}"

Con PowerShell, enviando el `auth.log` completo (hay que leerlo con `ReadAllLines`; `Get-Content` añade propiedades a cada línea y la API lo rechaza):

    $lineas = [System.IO.File]::ReadAllLines("$PWD\auth.log")
    $body = @{ lineas = $lineas; umbral = 0.7; lista_blanca = @() } | ConvertTo-Json
    Invoke-RestMethod -Uri http://127.0.0.1:8000/analizar -Method Post -Body $body -ContentType "application/json; charset=utf-8"

Respuesta (resumida):

    {
      "lineas_ignoradas": 0,
      "ips_analizadas": 384,
      "sospechosas": [
        {"ip": "192.168.2.105", "probabilidad": 1.0, "motivo": "prueba 12 usuarios distintos; 206 eventos con usuarios inexistentes; 103 fallos de contrasena en 5 minutos"},
        ...
      ]
    }

Las pruebas documentadas (petición correcta, lista blanca, umbral fuera de rango y líneas basura) están en `PRUEBAS_API.md`.

## Estructura del repositorio

(pendiente)
