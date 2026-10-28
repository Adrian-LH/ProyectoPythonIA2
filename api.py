"""API REST del detector de intrusiones (Fase 3 del Proyecto DAM).

Arrancar:  uvicorn api:app --reload
Probar:    http://127.0.0.1:8000/docs

La API solo informa de IPs sospechosas: nunca bloquea nada. La decision es de una persona.
"""
import ipaddress
from pathlib import Path

import joblib
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from logtools import cargar_lineas, construir_features

# 1. Configuracion: ruta del modelo y limite de lineas por peticion
RUTA_MODELO = Path(__file__).parent / "modelo.joblib"
MAX_LINEAS = 50000

# 2. Carga del modelo UNA sola vez, al arrancar el servicio
if not RUTA_MODELO.exists():
    raise RuntimeError("No existe modelo.joblib: ejecuta antes entrenar.py")
modelo = joblib.load(RUTA_MODELO)
CARACTERISTICAS = list(modelo.feature_names_in_)

app = FastAPI(title="Detector de intrusiones SSH",
              description="Analiza lineas de auth.log y senala IPs sospechosas. Solo informa, no bloquea.")

# 2.1 CORS: permite que la interfaz web (otro origen) llame a la API desde el navegador
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


# 3. Formato de la peticion: pydantic valida tipos, rango del umbral y numero de lineas
class Peticion(BaseModel):
    lineas: list[str] = Field(min_length=1, max_length=MAX_LINEAS,
                              description="Lineas de auth.log")
    umbral: float = Field(0.7, ge=0, le=1, description="Probabilidad minima para marcar una IP")
    lista_blanca: list[str] = Field(default_factory=list, description="IPs que nunca se marcan")

    # 3.1 Cada IP de la lista blanca tiene que ser una IP valida
    @field_validator("lista_blanca")
    @classmethod
    def comprobar_ips(cls, ips):
        for ip in ips:
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                raise ValueError(f"'{ip}' no es una IP valida")
        return ips


# 4. Errores de validacion: 422 con mensajes faciles de leer (como mucho 5, y cuantos mas hay)
@app.exception_handler(RequestValidationError)
async def error_validacion(request: Request, exc: RequestValidationError):
    errores = exc.errors()
    detalles = []
    for e in errores[:5]:
        campo = ".".join(str(p) for p in e["loc"] if p != "body") or "cuerpo"
        detalles.append(f"{campo}: {e['msg']}")
    if len(errores) > 5:
        detalles.append(f"... y {len(errores) - 5} errores mas del mismo tipo")
    return JSONResponse(status_code=422,
                        content={"error": "Datos de entrada no validos", "detalles": detalles})


# 5. Motivo legible: reglas sencillas sobre las caracteristicas de la IP
def explicar(fila):
    motivos = []
    if fila["n_usuarios"] >= 3:
        motivos.append(f"prueba {int(fila['n_usuarios'])} usuarios distintos")
    if fila["n_inv"] > 0:
        motivos.append(f"{int(fila['n_inv'])} eventos con usuarios inexistentes")
    if fila["max_fallos_5min"] >= 5:
        motivos.append(f"{int(fila['max_fallos_5min'])} fallos de contrasena en 5 minutos")
    if fila["ratio_fallos"] >= 0.8 and fila["n_ok"] == 0:
        motivos.append("ningun acceso correcto, casi todo son fallos")
    if not motivos:
        motivos.append("su patron se parece al de los atacantes segun el modelo")
    return "; ".join(motivos)


# 6. GET /salud: comprobar que el servicio esta vivo y que espera el modelo
@app.get("/salud")
def salud():
    return {"estado": "ok",
            "modelo": type(modelo).__name__,
            "caracteristicas": CARACTERISTICAS,
            "max_lineas": MAX_LINEAS}


# 7. POST /analizar: lineas -> eventos -> caracteristicas por IP -> probabilidad -> sospechosas
@app.post("/analizar")
def analizar(peticion: Peticion):
    # 7.1 Parsear las lineas reutilizando logtools (sin copiar su codigo)
    eventos, ignoradas = cargar_lineas(peticion.lineas)
    if eventos.empty:
        return JSONResponse(status_code=422,
                            content={"error": "No hay nada que analizar",
                                     "detalles": ["Ninguna linea tiene el formato de auth.log de sshd"]})

    # 7.2 Una fila por IP, con las columnas en el mismo orden que en el entrenamiento
    X = construir_features(eventos)[CARACTERISTICAS]
    probabilidades = modelo.predict_proba(X)[:, 1]

    # 7.3 Quedarse con las que superan el umbral y no estan en la lista blanca
    blanca = set(peticion.lista_blanca)
    sospechosas = []
    for ip, prob in zip(X.index, probabilidades):
        if prob >= peticion.umbral and ip not in blanca:
            sospechosas.append({"ip": ip,
                                "probabilidad": round(float(prob), 3),
                                "motivo": explicar(X.loc[ip])})

    # 7.4 Las mas peligrosas primero
    sospechosas.sort(key=lambda s: s["probabilidad"], reverse=True)
    return {"lineas_ignoradas": ignoradas,
            "ips_analizadas": len(X),
            "sospechosas": sospechosas}