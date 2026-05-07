# 💡 Proposals & Future Improvements

Ideas and enhancements logged for future development.
✅ = already implemented · 🔲 = pending

---

## 🎨 M1 — Proof of Work Monitor

### Interactivity
- ✅ **Selector de N bloques** — slider para elegir cuántos bloques analizar (20–150).
- ✅ **Click en el hash** — al hacer clic en el hash del bloque, navegar automáticamente a M2 con ese bloque precargado.
- ✅ **Hover rico en gráficas** — al pasar el ratón sobre una barra del histograma, mostrar los bloques concretos que caen en ese rango de tiempo.

### Visualizaciones
- ✅ **Heatmap de actividad por hora** — bloques de las últimas 24h distribuidos por hora del día.
- ✅ **Scatter plot nonce vs block time** — correlación entre el nonce encontrado y el tiempo del bloque.

---

## 🧱 M2 — Block Header Analyzer

- ✅ **Comparación entre dos bloques** — headers en paralelo con diferencias campo a campo.
- ✅ **Exportar header como JSON** — botón para descargar los 6 campos parseados.
- 🔲 **Historial de bloques analizados** — guardar en localStorage los últimos hashes buscados.

---

## 📈 M3 — Difficulty History

- ✅ **Zoom interactivo** — scroll para hacer zoom, drag para moverse. Plugin chartjs-plugin-zoom.
- ✅ **Botones de rango rápido** — 1M / 3M / 6M / 1Y / ALL.
- 🔲 **Overlay de precio BTC** — superponer el precio histórico de Bitcoin sobre la curva de dificultad.
- 🔲 **Predicción visual de M7** — mostrar la predicción del próximo ajuste directamente en la gráfica de M3.

---

## 🤖 M4 — AI Anomaly Detector

- ✅ **Slider de sensibilidad en tiempo real** — umbral p1–p20 recalcula anomalías sin recargar datos.
- ✅ **Click en anomalía → M2** — navegar al block header desde la tabla de anomalías.
- ✅ **KS test** — validación estadística del ajuste exponencial implementada en JavaScript puro.
- 🔲 **Modo en tiempo real** — detectar anomalías conforme llegan bloques nuevos vía WebSocket.
- 🔲 **Filtro por tipo** — mostrar solo fast anomalies o solo slow anomalies.
- 🔲 **Exportar anomalías** — descargar la tabla de bloques anómalos como CSV.

---

## 📊 M7 — AI Difficulty Predictor

- ✅ **OLS implementado en JavaScript puro** — sin librerías externas, regresión lineal completa.
- ✅ **Intervalo de confianza dinámico** — slider 80%–99%, recalcula en tiempo real.
- ✅ **Gráfica de residuos** — validación visual del modelo.
- ✅ **Feature importance** — coeficientes estandarizados en gráfica de barras horizontal.
- 🔲 **Comparativa de modelos** — implementar Prophet o LSTM y comparar métricas con OLS.
- 🔲 **Predicción a múltiples períodos** — predecir los próximos 3–5 ajustes, no solo el siguiente.
- 🔲 **Feature importance mejorada** — revisar escala y visualización del gráfico de barras.

---

## 🌳 M5 — Merkle Proof Verifier

- ✅ **Animación paso a paso** — nodos aparecen secuencialmente con SVG animado.
- ✅ **Buscar transacción por TXID** — input de búsqueda por hash de transacción.
- ✅ **Conectado con M2** — root calculado comparado con el Merkle Root del header.
- 🔲 **Verificación de firma ECDSA** — verificar la firma de curva elíptica (secp256k1 en JS). Alta complejidad técnica.

---

## 🔒 M6 — Security Score

- ✅ **Precio de alquiler actualizable** — input para ajustar precio NiceHash en tiempo real.
- ✅ **Simulador de confirmaciones** — dado un importe en USD y hashrate del atacante, calcula el riesgo exacto.
- ✅ **"Economic Rationality"** — compara coste del ataque vs recompensas de bloque.
- ✅ **Slider de hashrate del atacante** — curva de Nakamoto se redibuja en tiempo real.
- 🔲 **Comparativa con Ethereum PoS** — añadir ETH al análisis (diferente modelo de seguridad).

---

## 🌐 General — Dashboard

- ✅ **Modo claro/oscuro** — toggle light/dark theme persistente en localStorage.
- ✅ **Persistencia de configuración** — sliders, rangos y último hash buscado se restauran al recargar.
- ✅ **WebSocket en tiempo real** — conectado a mempool.space WebSocket. M1 se actualiza al llegar un bloque nuevo sin polling.
- ✅ **Flash de nuevo bloque** — la barra superior parpadea en verde al detectar un bloque nuevo.
- 🔲 **Exportar dashboard como PDF** — snapshot del estado actual.
- 🔲 **Internacionalización** — versión en español del dashboard.
- 🔲 **Notificaciones del sistema** — alerta del navegador cuando se mina un bloque nuevo o se detecta una anomalía.
- 🔲 **Vercel/GitHub Pages deploy** — desplegar el dashboard HTML como URL pública accesible sin servidor local.

---

*Last updated: 2026-05-07*