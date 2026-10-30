"""Pruebas automaticas de la API con pytest y el TestClient de FastAPI.

Necesitan modelo.joblib y auth.log (semilla 123). Ejecutar:  pytest -v
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import MAX_LINEAS, app

cliente = TestClient(app)
RUTA_LOG = Path(__file__).parent / "auth.log"
LINEA_OK = ("Oct  7 03:00:01 srv-web01 sshd[1234]: Failed password for invalid user admin "
            "from 203.0.113.5 port 40000 ssh2")


@pytest.fixture(scope="module")
def lineas():
    if not RUTA_LOG.exists():
        pytest.skip("Falta auth.log: ejecuta generar_logs.py --seed 123")
    return RUTA_LOG.read_text(encoding="utf-8").splitlines()


def analizar(**cuerpo):
    return cliente.post("/analizar", json=cuerpo)


def test_salud():
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert "n_fallos" in r.json()["caracteristicas"]


def test_peticion_correcta(lineas):
    r = analizar(lineas=lineas, umbral=0.7, lista_blanca=[])
    assert r.status_code == 200
    datos = r.json()
    assert datos["lineas_ignoradas"] == 0
    assert datos["ips_analizadas"] > 0
    assert datos["sospechosas"]
    for s in datos["sospechosas"]:
        assert set(s) == {"ip", "probabilidad", "motivo"}
        assert s["probabilidad"] >= 0.7
        assert s["motivo"]


def test_lista_blanca(lineas):
    primera = analizar(lineas=lineas).json()["sospechosas"][0]["ip"]
    r = analizar(lineas=lineas, lista_blanca=[primera])
    assert r.status_code == 200
    assert primera not in [s["ip"] for s in r.json()["sospechosas"]]


def test_umbral_cero_marca_todas_menos_lista_blanca(lineas):
    datos = analizar(lineas=lineas, umbral=0).json()
    assert len(datos["sospechosas"]) == datos["ips_analizadas"]


@pytest.mark.parametrize("umbral", [1.5, -0.1, "alto"])
def test_umbral_fuera_de_rango(umbral):
    r = analizar(lineas=[LINEA_OK], umbral=umbral)
    assert r.status_code == 422
    assert r.json()["detalles"][0].startswith("umbral")


def test_lineas_basura():
    r = analizar(lineas=["hola que tal", "esto no es un log", "12345"])
    assert r.status_code == 422
    assert r.json()["error"] == "No hay nada que analizar"


def test_mezcla_basura_y_lineas_validas():
    r = analizar(lineas=["basura", LINEA_OK, "mas basura"])
    assert r.status_code == 200
    assert r.json()["lineas_ignoradas"] == 2
    assert r.json()["ips_analizadas"] == 1


def test_cuerpo_mal_formado():
    r = cliente.post("/analizar", content="{esto no es json",
                     headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_falta_lineas():
    r = cliente.post("/analizar", json={"umbral": 0.5})
    assert r.status_code == 422
    assert r.json()["detalles"][0].startswith("lineas")


def test_lista_de_lineas_vacia():
    assert analizar(lineas=[]).status_code == 422


def test_ip_no_valida_en_lista_blanca():
    r = analizar(lineas=[LINEA_OK], lista_blanca=["no-es-una-ip"])
    assert r.status_code == 422
    assert "no es una IP valida" in r.json()["detalles"][0]


def test_demasiadas_lineas():
    assert analizar(lineas=[LINEA_OK] * (MAX_LINEAS + 1)).status_code == 422