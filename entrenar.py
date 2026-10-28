"""Entrena el detector y guarda el modelo (kit del Proyecto DAM).

Uso:
    python entrenar.py --log auth.log --etiquetas etiquetas.csv --salida modelo.joblib

Hace tres cosas: construye las caracteristicas por IP, entrena un bosque
aleatorio con parte de los datos y lo evalua con el resto.
"""
import argparse

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from logtools import cargar_etiquetas, cargar_log, construir_features


def main():
    ap = argparse.ArgumentParser(description="Entrena el detector de IPs atacantes")
    ap.add_argument("--log", default="auth.log")
    ap.add_argument("--etiquetas", default="etiquetas.csv")
    ap.add_argument("--salida", default="modelo.joblib")
    args = ap.parse_args()

    df = cargar_log(args.log)
    X = construir_features(df)
    y = cargar_etiquetas(args.etiquetas, X.index)
    print(f"{len(X)} IPs; {int(y.sum())} atacantes ({y.mean():.0%})")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42)

    modelo = RandomForestClassifier(
        n_estimators=200, class_weight="balanced", random_state=42)
    modelo.fit(X_train, y_train)

    pred = modelo.predict(X_test)
    print(confusion_matrix(y_test, pred))
    print(classification_report(y_test, pred, digits=3))

    joblib.dump(modelo, args.salida)
    print(f"Modelo guardado en {args.salida}")


if __name__ == "__main__":
    main()
