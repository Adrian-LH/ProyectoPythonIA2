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
