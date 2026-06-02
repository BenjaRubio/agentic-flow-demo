# Prueba Técnica – AI Engineer / Machine Learning / Agentic Systems

## Objetivo
Diseñar e implementar una solución funcional de IA aplicada a un problema operativo realista, combinando:
- fundamentos de Machine Learning
- uso razonado de LLMs
- diseño de flujos agentic
- evaluación técnica seria
- criterio de ingeniería y producto

Puedes usar herramientas de IA durante el desarrollo. La evaluación no busca medir si usaste IA o no, sino si entiendes, validas y puedes defender lo que construiste.

## Contexto del desafío
Una empresa quiere construir un **Operations AI Copilot** para uso interno.

Este sistema debe ayudar a un equipo a:
- responder preguntas sobre documentación interna
- clasificar solicitudes entrantes
- decidir qué acción sugerir
- usar herramientas cuando corresponda
- abstenerse o escalar cuando la confianza sea insuficiente

La empresa está abierta a una arquitectura agentic, pero no quiere agentes “por moda”. Espera una solución donde la autonomía esté justificada y controlada.

## Lo que debes construir
Tu solución debe combinar estas tres capacidades:

### A. Knowledge Reasoning
Un componente que responda preguntas usando los documentos entregados, mostrando evidencia y manejando incertidumbre.

### B. ML-based Decision Layer
Un componente de Machine Learning o lógica híbrida que clasifique, priorice o enrute solicitudes.

Ejemplos válidos:
- clasificación por tipo de caso
- prioridad alta/media/baja
- requiere escalamiento humano sí/no
- scoring de riesgo
- recomendación de siguiente acción

No es obligatorio entrenar un modelo complejo, pero sí debes demostrar pensamiento de ML.

### C. Agentic Workflow
Un flujo agentic o semiautónomo que utilice una o más tools para resolver el caso.

Ejemplos:
- consulta documental
- detección de vigencia de política
- clasificación del caso
- sugerencia de acción
- generación de borrador de respuesta
- escalamiento a humano

Debes justificar:
- por qué esa parte sí debe ser agentic
- qué parte no debe ser agentic
- qué guardrails implementaste

## Requerimientos funcionales mínimos
Tu sistema debe permitir:
1. procesar el set de documentos entregado
2. responder preguntas con sustento en evidencia
3. citar o mostrar fragmentos relevantes
4. clasificar solicitudes entrantes
5. sugerir una acción
6. abstenerse cuando no exista sustento suficiente
7. escalar cuando la confianza sea insuficiente
8. manejar ambigüedad, contradicciones y documentos desactualizados

## Requerimientos técnicos mínimos
Tu entrega debe incluir:
- repositorio funcional
- instrucciones claras de ejecución
- README técnico
- al menos 5 tests
- logs básicos o trazas simples
- explicación de arquitectura
- explicación de evaluación
- reflexión sobre riesgos y limitaciones
- estimación de costos
- demo breve de máximo 5 minutos

## Restricciones del desafío
Debes asumir que:
1. El presupuesto es limitado.
2. La latencia importa.
3. Hay documentos contradictorios.
4. Hay documentos antiguos y vigentes.
5. Los usuarios preguntan mal.
6. La autonomía tiene riesgo.

Debes explicar cómo tu sistema lidia con cada una.

## Entregables
### 1. Código fuente
Repositorio ejecutable localmente.

### 2. README técnico
Debe incluir:
- resumen de la solución
- arquitectura general
- decisiones técnicas
- enfoque de ML
- enfoque agentic
- métricas de evaluación
- riesgos y limitaciones
- costos estimados
- observabilidad
- qué mejorarías con una semana más

### 3. Demo
Video de máximo 5 minutos mostrando:
- un caso exitoso
- un caso ambiguo
- un caso que escala
- un caso con conflicto documental o vigencia

### 4. Reflexión técnica breve
Máximo 1 página respondiendo:
- cuál es la parte más frágil de tu solución
- qué no lanzarías aún a producción
- qué construiste con ayuda de IA y cómo lo validaste

## Tiempo esperado
Entre 8 y 12 horas efectivas.

## Entrevista posterior
Luego de la entrega habrá una entrevista técnica donde revisaremos:
- arquitectura
- enfoque de ML
- decisiones agentic
- control de errores
- evaluación
- posibles cambios sobre la solución
