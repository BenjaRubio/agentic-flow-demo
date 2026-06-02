# Operations AI Copilot

Copilot interno para un equipo de operaciones logísticas. Responde preguntas
sobre documentación interna, clasifica solicitudes entrantes de clientes, decide
la siguiente acción, usa herramientas cuando corresponde, y **se abstiene o
escala** cuando la confianza es insuficiente.

> El código y los comentarios están en inglés; esta documentación está en
> español (idioma del brief / de los evaluadores).

---

## 1. Resumen de la solución

El sistema está construido sobre el **framework WAT** (Workflows, Agents, Tools),
descrito en [CLAUDE.md](CLAUDE.md):

- **Workflows** (`workflows/*.md`): SOPs en lenguaje natural que un agente de IA
  lee para saber qué hacer.
- **Agente** (Claude Code u otro): aporta el **razonamiento** — resolver
  conflictos entre políticas activas, redactar prosa, aplicar criterio cuando la
  clasificación tiene baja confianza. **No hay LLM embebido en el código.**
- **Tools** (`tools/*.py`): Python **determinístico** — recuperación (RAG),
  clasificación (k-NN + tabla de decisión), formateo de respuestas, escalamiento.

La idea central: la IA probabilística decide; el código determinístico ejecuta.
Esto mantiene el sistema barato, rápido, testeable y auditable.

Cubre los tres pilares del brief, no como módulos aislados sino integrados en los
workflows:

| Pilar del brief | Dónde vive |
|---|---|
| **A. Knowledge Reasoning** | `workflows/answer_docs_question.md` + `search_docs`, `get_active_policy` |
| **B. ML Decision Layer** | `workflows/classify_request.md` + `classify_ticket` (k-NN + tabla de decisión) |
| **C. Agentic Workflow** | ambos workflows: cada uno encadena tools y razonamiento del agente |

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
(parse de vigencia), `embeddings` (backend local + cosine), `decision_table`
(reglas), `observability` (structlog + tracing de latencia/costo).

---

## 3. Decisiones técnicas

- **Corpus diminuto → embeddings locales, sin vector store.** Los 7 docs suman
  <1.000 tokens. Un Pinecone/Chroma sería sobre-ingeniería. Uso
  `sentence-transformers` (`all-MiniLM-L6-v2`) en memoria, con **fallback
  automático a TF-IDF** si `torch` no está disponible (CI/entornos livianos).
- **La resolución de vigencia es el verdadero problema, no el retrieval.**
  `policy_v1` y `policy_v2` son casi idénticos semánticamente (mismo texto,
  umbral 0.60 vs 0.80) → el retriever devuelve ambos. El valor está en filtrar
  por metadatos: `search_docs` **descarta `Deprecated`/`Outdated`** y
  `get_active_policy` rankea por `(status, effective_date)` y reporta los docs
  superseded para transparencia.
- **Clasificación = híbrido.** Ver sección 4.
- **Tools ejecutables por CLI** (`python -m tools.x ...`) para que el agente las
  invoque y para los tests.

---

## 4. Enfoque de ML

El dataset de entrenamiento tiene **10 ejemplos** y el de test **6 (sin labels)**.
Con tan pocos datos, *entrenar* un modelo paramétrico (árbol, regresión) sobreajusta
y no es validable. El enfoque honesto es híbrido:

- **`type` (lo único genuinamente aprendido): k-NN (nearest-neighbour, k=1).**
  Instance-based learning degrada con gracia con datos diminutos y no entrena
  parámetros. Con ~1.6 ejemplos por clase, k=1 supera a k≥3 (verificado por
  LOOCV: k=1→0.6, k=3→0.5, k=5→0.1). La confianza se mide con la **similitud
  absoluta** del vecino más cercano y el **margen** al vecino de otra clase.
- **`priority` / `human_escalation` / `next_action`: tabla de decisión
  determinística** (`config/rules.yaml`), derivada a mano de `sla_matrix.md` +
  `escalation_policy.md` + `policy_v2` + `pricing_notes_current`. **Reproduce el
  100% de las labels de priority/escalation del train.** No usa LLM. Sobre la
  base por tipo se aplican *triggers* por palabra clave (customs, temperature,
  legal, delay, service-continuity) que pueden **subir prioridad o forzar
  escalamiento**, nunca bajarla.
- **`next_action`** no tiene labels en el train → por diseño es salida de la
  tabla: `auto_respond` (bajo riesgo) o `route:<team>` (deriva al equipo del
  routing de `escalation_policy.md`).
- **Baja confianza → criterio del agente.** Cuando `low_confidence` es true, el
  workflow pide al agente revisar el tipo con las definiciones de los docs.

**Resultado clave (robustez del híbrido):** en el caso de test *"cargo is delayed
and they may lose a supermarket slot tomorrow"*, el k-NN equivoca el tipo
(`tracking_request` en vez de `shipment_exception`), **pero los triggers `delay` +
`service_continuity` igual fuerzan `high` / escalamiento / `route:operations_lead`**.
La política determinística corrige el error del modelo aprendido.

---

## 5. Enfoque agentic (qué es y qué no es agentic)

- **Agentic (razonamiento del agente):** reformular preguntas mal hechas;
  resolver empates entre políticas **activas** por fecha/versión; redactar prosa;
  aplicar criterio cuando la clasificación tiene baja confianza.
- **NO agentic (código determinístico):** retrieval, filtrado de vigencia,
  clasificación de tipo, tabla de prioridad/escalamiento, registro de
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
| Type — accuracy LOOCV (k=1) | **0.6** (6/10) |
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

`tools/common/observability.py` configura **structlog** (JSON a stderr, stdout
queda limpio para la salida de las tools) y el decorador **`@traced`** que envuelve
cada tool y emite por llamada:

```json
{"tool":"classify_ticket","status":"ok","duration_ms":9.58,
 "in_tokens":20,"out_tokens":289,"est_cost_usd":0.004395, ...}
```

Los escalamientos quedan registrados en `.tmp/escalations.log`.

---

## 10. Riesgos y limitaciones

- **El clasificador de tipo es la parte más frágil:** 10 ejemplos, 0.6 LOOCV. Se
  mitiga con triggers determinísticos y deferral al agente, pero el tipo puede
  errar en texto novedoso.
- **Triggers por keyword:** simples y auditables, pero frágiles ante sinónimos o
  negaciones ("no delay"). Conscientemente erramos hacia escalar (safety-first),
  lo que puede sobre-escalar delays benignos.
- **Sin labels en el test set:** la evaluación end-to-end es manual.
- **El fallback TF-IDF degrada la calidad** del retrieval y la clasificación;
  el backend semántico es el recomendado en producción.

---

## 11. Qué mejoraría con una semana más

- Ampliar y balancear el dataset de tickets; medir con cross-validation k-fold
  estratificado y reportar matriz de confusión por tipo.
- Reemplazar triggers por keyword con un extractor de features semántico
  (similitud a frases canónicas) manteniéndolo determinístico.
- Persistir los vectores del corpus en disco para arranque en frío más rápido.
- Un *router* ligero que detecte si la entrada es pregunta documental o ticket.
- Tests de integración que ejerciten el workflow completo con un agente simulado.

---

## 12. Instrucciones de ejecución

```bash
cd src
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # incluye sentence-transformers (pesado)
                                        # si falla, el sistema usa TF-IDF igual

# Tests (>=6, sin llamadas a API)
python -m pytest tests/ -q

# Evaluación cuantitativa (LOOCV + fidelidad de la tabla)
python -m eval.evaluate_classifier

# Clasificación del test set para revisión manual
python -m eval.classify_test_set

# Tools individuales (como las invoca el agente)
python -m tools.search_docs "pricing dispute commercial team"
python -m tools.get_active_policy "pricing dispute routing"
python -m tools.classify_ticket "Customer reports a temperature alert in reefer cargo."
python -m tools.escalate_case operations_lead "temperature exception"
```

**Uso agentic:** dar al agente una instrucción (p.ej. *"¿pueden las disputas de
precio de envíos activos manejarse por el equipo comercial?"*). El agente lee
`workflows/answer_docs_question.md`, ejecuta `search_docs`/`get_active_policy`, y
redacta la respuesta con la cita correcta (**pricing operations**, citando
`policy_v2` y `pricing_notes_current`, descartando v1/old).

---

## 13. Estructura del proyecto

```
src/
  CLAUDE.md                 # framework WAT (instrucciones del agente)
  README.md                 # este archivo
  requirements.txt
  workflows/                # SOPs en markdown (lo que el agente sigue)
  tools/                    # tools determinísticas + tools/common/ (helpers)
  config/                   # rules.yaml (tabla de decisión), pricing.yaml
  eval/                     # evaluate_classifier.py, classify_test_set.py
  tests/                    # pytest (6 archivos, 36 tests)
  dataset/                  # docs, tickets, tool_specs, examples (provistos)
```
