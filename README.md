# Kit del Proyecto DAM — Auditar e integrar un detector de intrusiones

Contenido:

- `generar_logs.py` — genera tu log (`auth.log`) y sus etiquetas (`etiquetas.csv`). No lo modifiques.
- `logtools.py` — lee el log y construye las características por IP. Está hecho: léelo y entiéndelo.
- `entrenar.py` — entrena el modelo y lo guarda en `modelo.joblib`.
- `analisis.ipynb` — cuaderno guiado con preguntas (❓) y experimentos (🧪).
- `requirements.txt` — librerías necesarias.

## Puesta en marcha

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt

python generar_logs.py --seed <TU_NUMERO_DE_LISTA> --salida auth.log --etiquetas etiquetas.csv
python entrenar.py --log auth.log --etiquetas etiquetas.csv --salida modelo.joblib
jupyter notebook analisis.ipynb
```

La fase de integración (API + interfaz) la programas tú; los apuntes y el enunciado explican qué debe hacer.
