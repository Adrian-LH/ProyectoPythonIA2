"""Utilidades para analizar un auth.log de OpenSSH (kit del Proyecto DAM).

Este modulo ya esta escrito: en el proyecto NO hace falta modificarlo.
Lo importante es entender que hace cada funcion (ver los comentarios).

    from logtools import cargar_log, construir_features
    df = cargar_log("auth.log")          # una fila por evento del log
    X = construir_features(df)           # una fila por IP, con caracteristicas
"""
import ipaddress
import re
from datetime import datetime

import pandas as pd

# El log de syslog no incluye el anio: lo fijamos nosotros.
ANIO = 2026

# Los nombres de mes dependen del idioma del sistema; usamos un diccionario propio.
MESES = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# Estructura comun de toda linea:  "Oct  7 10:15:32 srv-web01 sshd[1234]: <mensaje>"
PATRON_LINEA = re.compile(
    r"^(?P<mes>\w{3})\s+(?P<dia>\d{1,2}) (?P<hora>\d{2}:\d{2}:\d{2}) "
    r"(?P<host>\S+) sshd\[(?P<pid>\d+)\]: (?P<msg>.*)$")

# Tipos de mensaje que sabemos interpretar (el primero que encaje, gana).
PATRONES_MSG = [
    ("fallo_password", re.compile(
        r"Failed password for (?P<invalido>invalid user )?(?P<usuario>\S+) "
        r"from (?P<ip>[\d.]+) port (?P<puerto>\d+)")),
    ("acceso_ok", re.compile(
        r"Accepted password for (?P<usuario>\S+) from (?P<ip>[\d.]+) port (?P<puerto>\d+)")),
    ("usuario_invalido", re.compile(
        r"Invalid user (?P<usuario>\S+) from (?P<ip>[\d.]+) port (?P<puerto>\d+)")),
    ("conexion_cerrada", re.compile(
        r"Connection closed by (?:authenticating |invalid )?user (?P<usuario>\S+) "
        r"(?P<ip>[\d.]+) port (?P<puerto>\d+)")),
]

# Que consideramos "red interna" (la de la organizacion).
RED_INTERNA = [ipaddress.ip_network("192.168.0.0/16"),
               ipaddress.ip_network("10.0.0.0/8")]


def parsear_linea(linea, anio=ANIO):
    """Convierte una linea de log en un diccionario, o None si no la entiende."""
    m = PATRON_LINEA.match(linea)
    if not m:
        return None
    h, mi, s = map(int, m["hora"].split(":"))
    ts = datetime(anio, MESES[m["mes"]], int(m["dia"]), h, mi, s)
    for tipo, patron in PATRONES_MSG:
        r = patron.search(m["msg"])
        if r:
            d = r.groupdict()
            return {
                "timestamp": ts,
                "tipo": tipo,
                "usuario": d["usuario"],
                "ip": d["ip"],
                "puerto": int(d["puerto"]),
                "usuario_invalido": bool(d.get("invalido")) or tipo == "usuario_invalido",
            }
    return None


def cargar_lineas(lineas):
    """Parsea una lista de lineas. Devuelve (DataFrame, numero_de_lineas_ignoradas)."""
    filas, ignoradas = [], 0
    for linea in lineas:
        r = parsear_linea(linea.rstrip("\n"))
        if r is None:
            ignoradas += 1
        else:
            filas.append(r)
    columnas = ["timestamp", "tipo", "usuario", "ip", "puerto", "usuario_invalido"]
    return pd.DataFrame(filas, columns=columnas), ignoradas


def cargar_log(ruta, verbose=True):
    """Lee un fichero de log y devuelve un DataFrame con un evento por fila."""
    with open(ruta, encoding="utf-8") as f:
        df, ignoradas = cargar_lineas(f)
    if verbose:
        print(f"{len(df)} eventos cargados; {ignoradas} lineas ignoradas")
    return df


def es_interna(ip):
    """True si la IP pertenece a la red interna definida arriba."""
    direccion = ipaddress.ip_address(ip)
    return any(direccion in red for red in RED_INTERNA)


def max_fallos_5min(eventos_de_una_ip):
    """Maximo numero de fallos de contrasena en cualquier ventana de 5 minutos."""
    fallos = eventos_de_una_ip.loc[
        eventos_de_una_ip["tipo"] == "fallo_password", "timestamp"]
    if fallos.empty:
        return 0
    serie = pd.Series(1, index=fallos.sort_values())
    return int(serie.rolling("5min").sum().max())


def construir_features(df):
    """Resume el log en una tabla con UNA FILA POR IP y varias caracteristicas."""
    g = df.groupby("ip")
    feats = g.agg(
        n_eventos=("tipo", "size"),
        n_fallos=("tipo", lambda s: (s == "fallo_password").sum()),
        n_ok=("tipo", lambda s: (s == "acceso_ok").sum()),
        n_usuarios=("usuario", "nunique"),
        n_inv=("usuario_invalido", "sum"),
        primero=("timestamp", "min"),
        ultimo=("timestamp", "max"),
    )
    feats["duracion_min"] = (feats["ultimo"] - feats["primero"]).dt.total_seconds() / 60
    feats["ratio_fallos"] = feats["n_fallos"] / feats["n_eventos"]
    feats["fallos_por_min"] = feats["n_fallos"] / feats["duracion_min"].clip(lower=1)
    feats["es_interna"] = [int(es_interna(ip)) for ip in feats.index]
    feats["max_fallos_5min"] = pd.Series(
        {ip: max_fallos_5min(grupo) for ip, grupo in df.groupby("ip")})
    feats["hora_media"] = g["timestamp"].apply(lambda s: s.dt.hour.mean())
    feats = feats.drop(columns=["primero", "ultimo"])
    feats["n_inv"] = feats["n_inv"].astype(int)
    return feats


def cargar_etiquetas(ruta, indice):
    """Lee etiquetas.csv y las alinea con las filas de la tabla de caracteristicas."""
    etiquetas = pd.read_csv(ruta).set_index("ip")["etiqueta"]
    return etiquetas.reindex(indice)
