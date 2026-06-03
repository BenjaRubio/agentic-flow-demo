# Operations AI Copilot

Copilot interno para un equipo de operaciones logísticas. Responde preguntas
sobre documentación interna, clasifica solicitudes entrantes de clientes, decide
la siguiente acción, usa herramientas cuando corresponde, y **se abstiene o
escala** cuando la confianza es insuficiente.


---

## 1. Resumen de la solución

El sistema está construido sobre el **framework WAT** (Workflows, Agents, Tools),
descrito en [AGENTS.md](AGENTS.md):

- **Workflows** (`workflows/*.md`): SOPs en lenguaje natural que un agente de IA
  lee para saber qué hacer.
- **Agente** (Claude Code u otro): aporta el **razonamiento** — resolver
  conflictos entre políticas activas, redactar prosa, aplicar criterio cuando la
  clasificación tiene baja confianza. **No hay LLM embebido en el código.**
- **Tools** (`tools/*.py`): Python **determinístico** — recuperación (RAG),
  clasificación (k-NN + tabla de decisión), formateo de respuestas, escalamiento.

La idea central: la IA probabilística decide; el código determinístico ejecuta.
Esto mantiene el sistema barato, rápido, testeable y auditable.

> El archivo AGENTS.md donde se explica la arquitectura fue obtenido en gran parte del sitio web de AI Automation Society (https://www.skool.com/ai-automation-society/classroom/076a1c6e?md=122d76fe19984887af89e30ba0c7d2f8) en base a la investigación realizada, y modificado para el caso de uso particular de la tarea.

---

## 2. Arquitectura

```
Usuario / Agente
      │  (lee el workflow correspondiente)
      ▼
┌─────────────────────────────────────────────────────────────┐
│  workflows/answer_docs_question.md   workflows/classify_request.md │
└─────────────────────────────────────────────────────────────┘
      │ ejecuta tools determinísticas                 │
      ▼                                                ▼
  search_docs ─┐                              classify_ticket ─┐
  get_active_policy                             (k-NN type +   │
      │  (RAG local + resolución de vigencia)    tabla decisión)│
      ▼                                                ▼
  chunks + metadata                          {type, priority, escalation,
  (Active únicamente)                          next_action, confidence}
      │                                                │
      ▼                                          next_action:
  el agente redacta                          ├─ auto_respond → draft_response
  respuesta interna + cita                   └─ route:<team> → escalate_case
```

Capa compartida (`tools/common/`): `ingest` (carga + chunking), `metadata`
(parse de vigencia), `embeddings` (backend local + cosine), `prototypes`
(Nearest Centroid + ConceptMatcher semántico), `decision_table` (reglas),
`observability` (structlog + tracing de latencia/costo).

> **Guía del agente:** `AGENTS.md` es el archivo canónico (estándar cross-vendor,
> lo auto-cargan Codex y otros). `CLAUDE.md` es solo un puntero a él para Claude Code.

---

## 3. Decisiones técnicas

- **Corpus diminuto → embeddings locales, sin vector store.** Los 7 docs suman
  <1.000 tokens. Un Pinecone/Chroma sería sobre-ingeniería. Uso
  `sentence-transformers` (`all-MiniLM-L6-v2`) en memoria, con **fallback
  automático a TF-IDF** si `torch` no está disponible (CI/entornos livianos).
- **La resolución de vigencia es el verdadero problema, no el retrieval.**
  `policy_v1` y `policy_v2` son casi idénticos semánticamente → el retriever devuelve ambos. Se filtra por metadatos: `search_docs` **descarta `Deprecated`/`Outdated`** y
  `get_active_policy` rankea por `(status, effective_date)` y reporta los docs
  superseded para transparencia.
- **Clasificación = híbrido.** Ver sección 4.
- **Tools ejecutables por CLI** (`python -m tools.x ...`) para que el agente las
  invoque y para los tests.

---

## 4. Enfoque de ML

El dataset de entrenamiento tiene **10 ejemplos** y el de test **6 (sin labels)**.
Con tan pocos datos, *entrenar* un modelo paramétrico (árbol, regresión) sobreajusta
y no es validable. Por lo tanto, se usa un enfoque híbrido:

- **`type` (lo único genuinamente aprendido): k-NN (nearest-neighbour, k=1).**
  Instance-based learning degrada con gracia con datos diminutos y no entrena
  parámetros. Con ~1.6 ejemplos por clase, k=1 supera a k≥3 (LOOCV: k=1→0.6,
  k=3→0.5, k=5→0.1). La confianza se mide con la **similitud coseno absoluta** del
  vecino más cercano y el **margen** al vecino de otra clase.
  - *Experimento (Nearest Centroid):* se probó un clasificador por arquetipos
    (promedio de embeddings por clase). Quedó **marginalmente por debajo** (LOOCV 0.5 vs 0.6) → se conservó k-NN. El código queda en `tools/common/prototypes.py` y la comparación la imprime `eval/evaluate_classifier.py`.
- **`priority` / `human_escalation` / `next_action`: simula lo que sería un árbol de decisión** (`config/rules.yaml`), pero derivada a mano de `sla_matrix.md` +
  `escalation_policy.md` + `policy_v2` + `pricing_notes_current`, no entrenado a partir del dataset. **Reproduce el
  100% de las labels de priority/escalation del train.** Sobre la base
  por tipo se aplican *triggers* que pueden **subir prioridad o forzar
  escalamiento**, nunca bajarla. Hay dos clases de trigger:
  - **keyword** (customs, temperature, legal, delay, regulated): términos de
    compliance no ambiguos tomados de los docs; deben **garantizarse**, no quedar
    sujetos a un umbral.
  - **semántico** (service_continuity): detectado por `ConceptMatcher` (coseno vs
    frases-arquetipo en `pricing_notes_current`).
- **`next_action`** no tiene labels en el train → por diseño es salida de la
  tabla: `auto_respond` (bajo riesgo) o `route:<team>`. Se basa en las reglas indicadas en los docs.
- **Baja confianza → criterio del agente.** Cuando `low_confidence` es true, el
  workflow pide al agente revisar el tipo con las definiciones de los docs.

**Resultado clave (robustez del híbrido):** en el caso de test *"cargo is delayed
and they may lose a supermarket slot tomorrow"*, el k-NN equivoca el tipo
(`tracking_request` en vez de `shipment_exception`), **pero los triggers `delay` +
`service_continuity` (este último por semántica) igual fuerzan `high` /
escalamiento / `route:operations_lead`**. La política corrige el error del modelo.

**Nota**: Si bien podría haberse buscado precisión y mayor flexibilidad que keywords al usar un modelo para clasificar las solicitudes del cliente. Este enfoque reduce los costos y la latencia, dejando la tarea al agente sólo en caso de ser necesario.

---

## 5. Enfoque agentic (qué es y qué no es agentic)

- **Agentic (razonamiento del agente):** resolver empates entre políticas **activas** por fecha/versión; redactar borrador de respuesta para cliente;
  aplicar criterio cuando la clasificación tiene baja confianza.
- **NO agentic (código determinístico):** retrieval de documentos, filtrado de vigencia, clasificación de tipo, tabla de prioridad/escalamiento, registro de
  escalamientos, logging de costo. Deben ser confiables y auditables.

**Guardrails implementados:**
- Abstención: si ningún doc activo sustenta la respuesta, el workflow A obliga a
  decirlo y no inventar (`policy_v2`: "must abstain and request clarification").
- Citas obligatorias con el texto literal de la política.
- Vigencia: el contenido `Deprecated`/`Outdated` nunca es base de una respuesta.
- Nunca confirmar ajustes de pricing (`pricing_notes_current`) → se enruta.
- Escalamiento obligatorio para customs, temperature, regulated, legal y delay
  (forzado por la tabla; el agente no puede bajarlo).

---

## 6. Métricas de evaluación

Cuantitativo (`python -m eval.evaluate_classifier`):

| Métrica | Valor (backend semántico) |
|---|---|
| Type — accuracy LOOCV (k-NN, k=1) | **0.6** (6/10) |
| Type — accuracy LOOCV (prototipos, comparación) | 0.5 (5/10) → se descarta |
| Tabla de decisión — priority vs gold | **1.0** |
| Tabla de decisión — escalation vs gold | **1.0** |

> Baseline de clase mayoritaria ≈ 0.2. Con el fallback TF-IDF el type baja a ~0.2
> (las frases comparten vocabulario genérico; la señal es semántica). **Por eso
> el backend preferido es semántico.** Con 10/6 ejemplos las cifras son
> ilustrativas, no estadísticamente robustas.

Cualitativo (`python -m eval.classify_test_set`): clasifica los 6 tickets de test
(sin labels) en un reporte legible para **revisión manual humana**. Inspección:
5/6 con tipo correcto; el delay (caso 1) corregido por triggers.

---

## 7. Cómo el sistema lidia con las 6 restricciones del brief

1. **Presupuesto limitado:** sin LLM embebido ni vector store pago; embeddings
   locales ($0/query); reglas y k-NN corren en milisegundos.
2. **Latencia:** tras cargar el modelo una vez (cacheado process-wide), cada tool
   tarda ~10 ms (ver logs). El test set completo clasifica en <0.1 s.
3. **Documentos contradictorios:** `get_active_policy` reporta los superseded y
   elige el activo; el agente resuelve empates activos por recencia.
4. **Documentos antiguos vs vigentes:** metadatos `Status`/`Effective date`
   parseados; `Deprecated`/`Outdated` pre-filtrados del retrieval.
5. **Usuarios preguntan mal:** el workflow A permite reformular/aclarar antes de
   buscar; si la relevancia es baja, se abstiene en vez de forzar.
6. **La autonomía tiene riesgo:** ejecución crítica en tools determinísticas +
   guardrails que el agente no puede sortear hacia abajo (escalamientos forzados,
   no confirmar pricing, citas obligatorias).

---

## 8. Costos estimados

El sistema no factura tokens por dentro, pero el agente corre sobre un plan con
cuotas → el costo es real. Se estima en dos partes:

1. **Medido por tool** (`@traced`): tokens de input/output de cada tool ×
   tarifa de `config/pricing.yaml`. Es un piso medible del footprint por solicitud
   (~250–550 tokens de I/O por tool en los ejemplos).
2. **Razonamiento del agente** (no visible desde las tools): se estima por
   workflow. Ejemplo con tarifas por defecto (3/15 USD por 1M tok in/out):
   - Workflow B típico: ~1–2k tokens de contexto + ~0.5k de salida ≈ **<US$0.02**.
   - Workflow A típico (con cita): similar orden de magnitud.

Ajustar `pricing.yaml` al modelo/plan real cambia todas las cifras de los logs.

---

## 9. Observabilidad

`tools/common/observability.py` configura **structlog**. Dos niveles de log:

- **Eventos info granulares** dentro de cada tool: logs informativos de las tareas que se van realizando y completando.
- **Resumen por llamada** vía el decorador **`@traced`** (latencia + tokens + costo):

```json
{"tool":"classify_ticket","status":"ok","duration_ms":9.58,
 "in_tokens":20,"out_tokens":289,"est_cost_usd":0.004395, ...}
```

Formato configurable: JSON por defecto, o consola legible con
`COPILOT_LOG_FORMAT=console`. Los escalamientos se registran en `.tmp/escalations.log`.

---

## 10. Riesgos y limitaciones

- **El clasificador de tipo es la parte más frágil:** 10 ejemplos, 0.6 LOOCV. Se
  mitiga con triggers determinísticos y deferral al agente, pero el tipo puede
  errar en texto novedoso.
- **Triggers de compliance por keyword:** simples y auditables, pero frágiles ante
  sinónimos o negaciones ("no delay"). Conscientemente erramos hacia escalar
  (safety-first), lo que puede sobre-escalar delays benignos. El trigger difuso
  (service_continuity) ya es semántico; los duros siguen por keyword a propósito porque siguen reglas de los docs.
- **El umbral semántico (0.40) no está calibrado** con datos de validación (no los
  hay); es un default razonable y podría requerir ajuste en producción.
- **Sin labels en el test set:** la evaluación end-to-end es manual.
- **El fallback TF-IDF degrada la calidad** del retrieval y la clasificación;
  el backend semántico es el recomendado en producción.

---

## 11. Qué mejoraría con una semana más

- Ampliar y balancear el dataset de tickets; medir con cross-validation.
- Reemplazar triggers por keyword con un extractor de features semántico
  (similitud a frases canónicas) manteniéndolo determinístico.
- Persistir los vectores del corpus en disco para arranque en frío más rápido.
- Un *router* ligero que detecte si la entrada es pregunta documental o ticket.
- Tests de integración que ejerciten el workflow completo con un agente simulado.

---

## 12. Instrucciones de ejecución

El repositorio tiene múltiples opciones para ejecutar desde la consola los tests, evaluaciones y las tools. Sin embargo, para probar el flujo agéntico, basta con crear el ambiente virtual, instalar las dependencias y abrir un agente en el root del repositorio, y tras leer ```AGENTS.md``` debería poder responder las consultas.

Ejecutar desde la **raíz del repo**:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # incluye sentence-transformers (pesado)
                                        # si falla, el sistema usa TF-IDF igual

# Tests (sin llamadas a API)
python -m pytest tests/ -q

# Evaluación cuantitativa (LOOCV k-NN vs prototipos + fidelidad de la tabla)
python -m eval.evaluate_classifier

# Clasificación del test set para revisión manual
python -m eval.classify_test_set

# Tools individuales (como las invoca el agente). Logs legibles en consola:
COPILOT_LOG_FORMAT=console python -m tools.search_docs "pricing dispute commercial team"
python -m tools.get_active_policy "pricing dispute routing"
python -m tools.classify_ticket "Customer reports a temperature alert in reefer cargo."
python -m tools.escalate_case operations_lead "temperature exception"
```

---

## 13. Estructura del proyecto

```
<repo root>/
  AGENTS.md                 # guía canónica del agente (WAT) — estándar cross-vendor
  CLAUDE.md                 # puntero a AGENTS.md (para Claude Code)
  README.md                 # este archivo
  requirements.txt
  workflows/                # SOPs en markdown (lo que el agente sigue)
  tools/                    # tools determinísticas + tools/common/ (helpers)
  config/                   # rules.yaml (tabla de decisión), pricing.yaml
  eval/                     # evaluate_classifier.py, classify_test_set.py
  tests/                    # pytest (7 archivos, 41 tests)
  dataset/                  # docs, tickets, tool_specs, examples (provistos)
```

## 14. Reflexión técnica

---

**La parte más frágil de la solución** es el clasificador de la solicitud del cliente, principalmente por el pequeño tamaño del dataset de entrenamiento, y porque el de test no tiene labels, de modo que no permite calcular directamente un accuracy y requiere validación manual.
Si bien la validación manual es lenta, el tamaño del dataset no lo hace difícil, la complejidad radica en que ningún modelo puede ser entrenado con solo 10 datos y poder generalizar bien.
Se busca mitigar un poco esto con la ayuda de ciertas keyword que indican que la solicitud puede referirse a un tópico en específico, sin embargo, al considerar un pool pequeño de estas, y que el usuario pregunta mal o puede ser creativo, no ofrece robustez real.

**No lanzaría el clasificador a producción**, principalmente por lo explicado previamente. Antes de un despliegue a producción buscaría ampliar la base de datos de entrenamiento que permita entrenar un modelo con una mejor precisión, así como el set de testing, que también lo ampliaría y validaría etiquetado.
También, en caso de mandarse a producción, consideraría que existe la posibilidad de que se amplíe la cantidad de docs, de modo que podría necesitarse un workflow que vaya actuanlizando el archivo de ```/config/rules.yml``` cuando esto ocurra. Además, como los vectores de estos docs se guardan en memoria, debería evaluarse el implementar una base de datos vectorial.

**Gran parte de la solución está construida con ayuda de IA**. En primer lugar, investigué sobre flujos agenticos y con apoyo de IA fui iterando para ir entendiendo cómo funciona y cómo podría construir mi solución. Discutí sobré tecnologías que podrían servirme, pros y contras entre ellas; discutí cómo construir un modelo para clasificar con un dataset tan pequeño, mi idea fue la de utilizar un centroide y arquetipos, lo que termino resultando peor en general que la recomendación de la IA de usar kNN.

Describí los workflows y tools necesarias para cada uno a una IA y ella se encargo de construir el código, las especificaciones en los archivos ```.md```, todo basado en mis indicaciones de cómo quería que funcionara, los flujos que deseaba, y algunos de estos que resolvimos en conjunto.

Además, se le indicó a la IA que quería realizar test con ```pytest``` para todas las tools, y fue esta la que decidió finalmente implementar 41, siendo bien exhaustiva. Para validarlo, revisé los archivos de testing (a ver qué se estaba testeando exactamente), y decidí mantenerlo ya que me pareció correcto.

En general, la validación fue de forma cualitativa al discutir y abordar el alcance necesario para la tarea, a excepción del modelo de clasificación que se hizo una validación cuantitativa, midiendo accuracy sobre el train set para los dos enfoques evaluados.