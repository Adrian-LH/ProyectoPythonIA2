Resultados de los experimentos

A través de la batería de pruebas, hemos comprobado que el desempeño real del modelo es muy dependiente del diseño del dataset sintético y de la proporción de clases.

En primer lugar, observamos mediante repeticiones de la partición de datos (E4) que el F1 fluctúa ligeramente (entre 0.980 y 1.000) debido al azar; sin embargo, al evaluarlo sobre un log completamente nuevo generado con otra semilla (E5), el clasificador mantiene un F1 sobresaliente de 0.990 y 0 falsos negativos, demostrando que generaliza bien dentro de las mismas reglas de simulación.

Por otro lado, en escenarios desbalanceados con escasos ataques reales (E6), la precisión del sistema decae fuertemente debido al peso de los falsos positivos. Finalmente, al prescindir de las etiquetas mediante algoritmos no supervisados como IsolationForest (E7), constatamos que el modelo pierde efectividad y su éxito queda condicionado a adivinar previamente el porcentaje de contaminación: asumiendo un 5% de anomalías, el recall cae críticamente al 0.200 (dejando escapar el 80% de los ataques).
