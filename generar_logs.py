#!/usr/bin/env python3
"""Genera un auth.log sintetico de un servidor SSH con ataques inyectados.

Uso:
    python generar_logs.py --seed 7 --salida auth.log --etiquetas etiquetas.csv

Cada alumno puede usar una semilla (--seed) distinta: obtendra un dataset
diferente pero con las mismas caracteristicas.
"""
import argparse
import csv
import random
from datetime import datetime, timedelta

HOST = "srv-web01"
MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
USUARIOS_LEGITIMOS = ["ana", "luis", "marta", "javi", "admin_sistemas", "backup"]
USUARIOS_ATAQUE = ["root", "admin", "test", "ubuntu", "oracle", "postgres",
                   "user", "pi", "guest", "ftpuser", "mysql", "git"]


def linea(ts, mensaje):
    """Formatea una linea con el estilo de /var/log/auth.log (syslog)."""
    pid = random.randint(1000, 60000)
    return (f"{MESES[ts.month - 1]} {ts.day:2d} {ts.strftime('%H:%M:%S')} "
            f"{HOST} sshd[{pid}]: {mensaje}")


def puerto():
    return random.randint(32768, 60999)


def ip_publica(usadas):
    """IP de los rangos de documentacion (RFC 5737): no pertenecen a nadie."""
    while True:
        red = random.choice(["198.51.100", "203.0.113"])
        ip = f"{red}.{random.randint(1, 254)}"
        if ip not in usadas:
            usadas.add(ip)
            return ip


def instante(inicio, minutos_max):
    return inicio + timedelta(seconds=random.randint(0, minutos_max * 60))


def eventos_fallo(ts, usuario, ip, valido):
    """Devuelve las lineas que genera OpenSSH ante un intento fallido."""
    p = puerto()
    if valido:
        return [(ts, f"Failed password for {usuario} from {ip} port {p} ssh2")]
    return [
        (ts, f"Invalid user {usuario} from {ip} port {p}"),
        (ts, f"Failed password for invalid user {usuario} from {ip} port {p} ssh2"),
    ]


def generar(seed, n_legit, n_ataque, dia):
    random.seed(seed)
    inicio = datetime.strptime(dia, "%Y-%m-%d")
    eventos = []   # (datetime, texto)
    etiquetas = {}  # ip -> 0/1
    usadas = set()

    # --- Trafico legitimo interno: personas del centro (192.168.1.x) ---
    for i in range(n_legit):
        ip = f"192.168.1.{10 + i % 200}" if i < 200 else f"10.0.{i // 200}.{i % 200 + 1}"
        etiquetas[ip] = 0
        usuario = random.choice(USUARIOS_LEGITIMOS[:5])
        for _ in range(random.randint(1, 4)):
            t = instante(inicio + timedelta(hours=7), 10 * 60)  # horario lectivo
            fallos = random.choices([0, 1, 2, 6], weights=[80, 12, 6, 2])[0]
            se_rinde = random.random() < 0.06   # se cansa y no llega a entrar
            if se_rinde:
                fallos = random.randint(2, 5)
            for _ in range(fallos):
                t += timedelta(seconds=random.randint(3, 20))
                eventos += eventos_fallo(t, usuario, ip, True)
            if not se_rinde:
                t += timedelta(seconds=random.randint(3, 20))
                eventos.append((t, f"Accepted password for {usuario} from {ip} port {puerto()} ssh2"))

    # --- Tarea de backup: muchos eventos, todos correctos (caso dificil) ---
    ip_backup = "10.0.0.5"
    etiquetas[ip_backup] = 0
    for h in range(24):
        t = inicio + timedelta(hours=h, minutes=random.randint(0, 3))
        eventos.append((t, f"Accepted password for backup from {ip_backup} port {puerto()} ssh2"))

    # --- Usuarios legitimos desde fuera (teletrabajo) ---
    for _ in range(max(3, n_legit // 8)):
        ip = ip_publica(usadas)
        etiquetas[ip] = 0
        usuario = random.choice(USUARIOS_LEGITIMOS[:5])
        t = instante(inicio + timedelta(hours=8), 12 * 60)
        se_rinde = random.random() < 0.3
        for _ in range(random.randint(2, 6) if se_rinde else random.choice([0, 1, 2, 3, 5])):
            t += timedelta(seconds=random.randint(5, 40))
            eventos += eventos_fallo(t, usuario, ip, True)
        if not se_rinde:
            t += timedelta(seconds=random.randint(5, 40))
            eventos.append((t, f"Accepted password for {usuario} from {ip} port {puerto()} ssh2"))

    # --- Atacantes ---
    for k in range(n_ataque):
        if random.random() < 0.15:   # equipo interno comprometido
            ip = f"192.168.2.{random.randint(1, 254)}"
            while ip in usadas:
                ip = f"192.168.2.{random.randint(1, 254)}"
            usadas.add(ip)
        else:
            ip = ip_publica(usadas)
        etiquetas[ip] = 1
        tipo = random.choices(["rapida", "lenta", "dirigida"], weights=[40, 35, 25])[0]
        if tipo == "rapida":      # diccionario de usuarios en pocos minutos
            n = random.randint(40, 250)
            t = instante(inicio, 23 * 60)
            for _ in range(n):
                t += timedelta(seconds=random.randint(0, 3))
                eventos += eventos_fallo(t, random.choice(USUARIOS_ATAQUE), ip, False)
                if random.random() < 0.2:
                    eventos.append((t, f"Connection closed by invalid user root {ip} port {puerto()} [preauth]"))
        elif tipo == "lenta":     # pocos intentos repartidos todo el dia
            for _ in range(random.randint(4, 18)):
                t = instante(inicio, 24 * 60 - 1)
                usuario = random.choice(USUARIOS_ATAQUE)
                valido = usuario == "root"
                eventos += eventos_fallo(t, usuario, ip, valido)
        else:                     # contra un usuario real, desde fuera
            objetivo = random.choice(["admin_sistemas", "ana", "root"])
            t = instante(inicio, 22 * 60)
            for _ in range(random.randint(3, 40)):
                t += timedelta(seconds=random.randint(20, 900))
                eventos += eventos_fallo(t, objetivo, ip, True)
        if random.random() < 0.25:  # alguno consigue entrar
            t += timedelta(seconds=random.randint(5, 60))
            eventos.append((t, f"Accepted password for root from {ip} port {puerto()} ssh2"))

    # --- Un usuario legitimo con mal dia (muchos fallos seguidos, red interna) ---
    ip = "192.168.1.250"
    etiquetas[ip] = 0
    t = inicio + timedelta(hours=9, minutes=random.randint(0, 59))
    for _ in range(random.randint(7, 12)):
        t += timedelta(seconds=random.randint(4, 15))
        eventos += eventos_fallo(t, "admin_sistemas", ip, True)
    t += timedelta(seconds=10)
    eventos.append((t, f"Accepted password for admin_sistemas from {ip} port {puerto()} ssh2"))

    # --- Script de monitorizacion mal configurado (legitimo, pero parece ataque) ---
    ip = "192.168.1.249"
    etiquetas[ip] = 0
    t = inicio + timedelta(hours=2)
    for _ in range(random.randint(30, 60)):
        t += timedelta(seconds=random.randint(60, 400))
        eventos += eventos_fallo(t, "backup", ip, True)

    eventos.sort(key=lambda e: e[0])
    return eventos, etiquetas


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--salida", default="auth.log")
    ap.add_argument("--etiquetas", default="etiquetas.csv")
    ap.add_argument("--legitimos", type=int, default=250)
    ap.add_argument("--atacantes", type=int, default=100)
    ap.add_argument("--dia", default="2026-10-07")
    args = ap.parse_args()

    eventos, etiquetas = generar(args.seed, args.legitimos, args.atacantes, args.dia)
    with open(args.salida, "w", encoding="utf-8") as f:
        for ts, texto in eventos:
            f.write(linea(ts, texto) + "\n")
    with open(args.etiquetas, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ip", "etiqueta"])
        for ip, e in sorted(etiquetas.items()):
            w.writerow([ip, e])
    print(f"{len(eventos)} lineas en {args.salida}; {len(etiquetas)} IPs "
          f"({sum(etiquetas.values())} atacantes) en {args.etiquetas}")


if __name__ == "__main__":
    main()
