# Proyecto DAM: auditar e integrar un detector de intrusiones con IA

Detector de intrusiones SSH basado en Machine Learning, expuesto como API REST (FastAPI) y consumido desde una interfaz web.

**Semilla del grupo: `123`** (todos generamos los datos con esta semilla; solo E5 usa la 999 y E6 la 5).

## Cómo funciona

    auth.log ──► eventos ──► características por IP ──► modelo ──► IPs sospechosas ──► una persona decide
                (logtools)    (logtools)                 (modelo.joblib)  (API)

1. **Log:** el servidor `srv-web01` registra cada intento de acceso SSH en `auth.log`.
2. **Eventos:** `logtools.py` convierte cada línea en un evento (fecha, tipo, usuario, IP, puerto). Las líneas que no entiende las ignora y las cuenta.
3. **Características:** agrupa los eventos por IP y calcula 11 números por cada una: fallos, accesos correctos, usuarios distintos, fallos en 5 minutos, etc.
4. **Modelo:** un bosque aleatorio (`RandomForestClassifier`) da a cada IP una probabilidad de ser atacante.
5. **Decisión:** la API devuelve las IPs que superan el umbral y no están en la lista blanca, con un motivo en lenguaje humano. **No bloquea nada:** la decisión final es de una persona.

## Instalación

    python -m venv .venv
    # Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
    pip install -r requirements.txt

## Generar datos y entrenar el modelo

    python generar_logs.py --seed 123 --salida auth.log --etiquetas etiquetas.csv
    python entrenar.py --log auth.log --etiquetas etiquetas.csv --salida modelo.joblib

Los logs, etiquetas y modelos no se suben al repositorio: se regeneran con estos comandos. El modelo solo es fiable con la misma versión de scikit-learn con la que se entrenó: si cambias de ordenador, vuelve a ejecutar `entrenar.py`.

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

1. Arranca la API (apartado anterior).
2. En otra terminal, sirve la página:

       python -m http.server 5500

3. Abre http://127.0.0.1:5500/index.html (también funciona abriendo `index.html` con doble clic).
4. Sube un fichero de log o pega líneas, ajusta el umbral y la lista blanca (una IP por línea) y pulsa **Analizar log**.

La página no carga el modelo: solo llama a `POST /analizar` con `fetch` y muestra la tabla de IPs sospechosas o el mensaje de error de la API.

## Ejemplos de peticiones

### curl (macOS / Linux)

    curl http://127.0.0.1:8000/salud

    curl -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" \
      -d '{"lineas": ["Oct  7 03:00:01 srv-web01 sshd[1234]: Failed password for invalid user admin from 203.0.113.5 port 40000 ssh2"], "umbral": 0.7, "lista_blanca": []}'

Enviar el `auth.log` completo (primero se convierte a JSON con Python):

    python -c "import json; print(json.dumps({'lineas': open('auth.log').read().splitlines(), 'umbral': 0.7, 'lista_blanca': []}))" > peticion.json
    curl -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" -d @peticion.json

### curl (Windows, cmd)

    curl -X POST http://127.0.0.1:8000/analizar -H "Content-Type: application/json" -d "{\"lineas\": [\"Oct  7 03:00:01 srv-web01 sshd[1234]: Failed password for invalid user admin from 203.0.113.5 port 40000 ssh2\"], \"umbral\": 0.7, \"lista_blanca\": []}"

### PowerShell, con el `auth.log` completo

Hay que leerlo con `ReadAllLines`: `Get-Content` añade propiedades a cada línea y la API lo rechaza.

    $lineas = [System.IO.File]::ReadAllLines("$PWD\auth.log")
    $body = @{ lineas = $lineas; umbral = 0.7; lista_blanca = @() } | ConvertTo-Json
    Invoke-RestMethod -Uri http://127.0.0.1:8000/analizar -Method Post -Body $body -ContentType "application/json; charset=utf-8"

### Respuesta (resumida)

    {
      "lineas_ignoradas": 0,
      "ips_analizadas": 384,
      "sospechosas": [
        {"ip": "192.168.2.105", "probabilidad": 1.0, "motivo": "prueba 12 usuarios distintos; 206 eventos con usuarios inexistentes; 103 fallos de contrasena en 5 minutos"},
        ...
      ]
    }

## Pruebas

- Pruebas manuales documentadas (petición correcta, lista blanca, umbral fuera de rango, líneas basura y 4 extra): `PRUEBAS_API.md`.
- Pruebas automáticas con pytest y el `TestClient` de FastAPI (necesitan `modelo.joblib` y `auth.log`). Resultado actual: **14 de 14 correctas**.

      pytest -v

## Estructura del repositorio

| Archivo | Qué es |
|---|---|
| `generar_logs.py` | Genera `auth.log` y `etiquetas.csv` sintéticos (kit, no se modifica). |
| `logtools.py` | Lee el log y construye las características por IP (kit, no se modifica). |
| `entrenar.py` | Entrena el bosque aleatorio y guarda `modelo.joblib`. |
| `analisis.ipynb` | Cuaderno con P1–P13 y la tabla de experimentos E1–E8. |
| `api.py` | API REST (FastAPI): `GET /salud` y `POST /analizar`. |
| `index.html` | Interfaz web que consume la API con `fetch`. |
| `test_api.py` | Pruebas automáticas de la API. |
| `PRUEBAS_API.md` | Documento de pruebas manuales. |
| `resultados.md` | Resumen de los resultados de los experimentos. |
| `requirements.txt` | Librerías necesarias. |
