# 💡 Proposals & Future Improvements

Ideas and enhancements logged for future development.
This file tracks good ideas that are not yet implemented.

---

## 🎨 M1 — Proof of Work Monitor

### Interactivity
- **Selector de N bloques** — slider para elegir cuántos bloques analizar (20 / 50 / 100). A más bloques, mejor el histograma estadístico.
- **Click en el hash** — al hacer clic en el hash del bloque, navegar automáticamente a M2 con ese bloque precargado.
- **Hover rico en gráficas** — al pasar el ratón sobre una barra del histograma, mostrar los bloques concretos que caen en ese rango de tiempo.

### Visualizaciones
- **Heatmap de actividad por hora** — bloques de las últimas 24h distribuidos por hora del día. ¿Hay horas con más actividad de minado?
- **Scatter plot nonce vs block time** — correlación entre el nonce encontrado y el tiempo que tardó el bloque. ¿Los bloques rápidos tienden a tener nonces bajos?

---

## 🧱 M2 — Block Header Analyzer

- **Comparación entre dos bloques** — mostrar dos headers en paralelo para ver diferencias campo a campo.
- **Historial de bloques analizados** — guardar en localStorage los últimos hashes buscados.
- **Exportar header como JSON** — botón para descargar los 6 campos parseados.

---

## 📈 M3 — Difficulty History

- **Zoom interactivo** — seleccionar un rango de fechas arrastrando sobre la gráfica.
- **Overlay de precio BTC** — superponer el precio histórico de Bitcoin sobre la curva de dificultad para ver correlaciones.
- **Predicción visual de M7** — mostrar la predicción del próximo ajuste directamente en la gráfica de M3.

---

## 🤖 M4 — AI Anomaly Detector

- **Modo en tiempo real** — detectar anomalías conforme llegan bloques nuevos, sin necesidad de pulsar botón.
- **Filtro por tipo** — mostrar solo fast anomalies o solo slow anomalies.
- **Exportar anomalías** — descargar la tabla de bloques anómalos como CSV.

---

## 📊 M7 — AI Difficulty Predictor

- **Comparativa de modelos** — implementar Prophet o LSTM y comparar métricas con la regresión lineal actual.
- **Predicción a múltiples períodos** — predecir los próximos 3-5 ajustes, no solo el siguiente.
- **Intervalo de confianza dinámico** — ajustar el nivel de confianza con un slider (80%, 90%, 95%).

---

## 🌳 M5 — Merkle Proof Verifier

- **Verificación de firma ECDSA** — verificar la firma de curva elíptica de una transacción. Requiere implementar secp256k1 en JS.
- **Modo educativo** — animación paso a paso que muestra visualmente cómo se construye el árbol.
- **Buscar transacción por TXID** — en lugar de usar el índice, buscar por hash de transacción directamente.

---

## 🔒 M6 — Security Score

- **Precio de alquiler actualizable** — input para ajustar el precio de NiceHash en tiempo real.
- **Comparativa con Ethereum** — añadir ETH al análisis de coste de ataque (PoS vs PoW).
- **Simulador de confirmaciones** — dado un importe en USD y un porcentaje de hashrate del atacante, calcular el riesgo exacto.

---

## 🌐 General — Dashboard

- **Modo claro** — toggle light/dark theme.
- **Persistencia de configuración** — guardar preferencias del usuario en localStorage (N bloques, moneda, etc.).
- **Exportar dashboard como PDF** — snapshot del estado actual para documentación.
- **WebSocket en tiempo real** — conectar a mempool.space WebSocket para recibir bloques nuevos sin polling.
- **Internacionalización** — versión en español del dashboard.
- **Notificaciones del sistema** — alerta del navegador cuando se mina un bloque nuevo o se detecta una anomalía.

---

*Last updated: 2026-05-06*