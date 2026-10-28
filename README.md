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

(pendiente)

## Usar la interfaz

(pendiente)

## Ejemplos de peticiones

(pendiente)

## Estructura del repositorio

(pendiente)
