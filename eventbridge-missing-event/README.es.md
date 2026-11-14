# EventBridge: aceptado no significa entregado

Publica un evento, encuentra el patrón que lo excluye y sigue la entrega hasta SQS.

PutEvents responde sin errores, pero el evento no llega a la cola. Reproduce el problema, compara el evento con la regla y corrige el patrón antes de volver a publicar.

## Prepara tu entorno

### 1. Clona el repositorio

Si ya tienes el repositorio, ejecuta git pull desde su raíz y entra en el directorio de este lab.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/eventbridge-missing-event
```

### Linux

#### 2. Inicia el emulador

Instala AWS Emulator 1.0.322, Python con pip y venv, y nano. Después prepara el entorno e inicia el emulador.

[Instalar AWS Emulator 1.0.322](https://docs.aws.amazon.com/emulator/latest/userguide/versioning.html)

**Terminal A · emulador**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
aws-emulator --version
bash start-emulator.sh
```

- Deja esta terminal abierta.

#### 3. Abre la terminal de trabajo

En otra terminal, entra en el directorio del lab y activa el entorno de Python. Ajusta la ruta si clonaste el repositorio en otra ubicación.

**Terminal B · práctica**

```bash
cd devops-in-practice-labs/eventbridge-missing-event
source .venv/bin/activate
```

Continúa en la terminal B cuando el emulador esté listo.

### Docker

#### 2. Abre el entorno del lab

El contenedor incluye AWS Emulator 1.0.322, Python y nano. Los logs quedan en .lab en tu equipo.

**Tu terminal → shell del contenedor**

```bash
bash docker-lab.sh
```

- Usa Bash y contenedores Linux; en Windows, ejecuta los comandos desde WSL.

Continúa en el shell que se abre.

## 1. Inspecciona la regla antes de publicar

Crea un bus de eventos, una regla y su destino SQS.

```bash
python lab.py prepare
python lab.py inspect
```

- Busca detail-type en el patrón desplegado. Abre pattern.json y lab.py para compararlo con el evento que construye event().

¿Coincide el patrón con el evento que vas a enviar?

La regla espera order.created, pero el código envía OrderCreated. EventBridge compara estos valores de forma exacta.

## 2. Publica el evento

Envía OrderCreated e inspecciona la respuesta.

```bash
python lab.py send
python lab.py inspect
```

- Busca failed_entry_count: 0 y el EventId de la respuesta. Guarda el correlation_id para seguir esta publicación.

¿Qué confirma una respuesta exitosa de PutEvents?

EventBridge aceptó el evento. Esa respuesta no confirma que alguna regla coincidiera ni que un destino lo recibiera.

### Traza de referencia

```text
{"correlation_id": "91cc5151f0654b5aa44251e659c99b99", "detail_type": "OrderCreated", "entries": [{"EventId": "18e7e097-cf5c-b28f-0000-000000000001"}], "event": "published", "failed_entry_count": 0, "time": "2026-11-14T09:51:59.155110+00:00"}
{"correlation_id": "a9950d6f3e3d448f915533bd31b80402", "detail_type": "OrderCreated", "entries": [{"EventId": "18e7e097-fc9c-993d-0000-000000000002"}], "event": "published", "failed_entry_count": 0, "time": "2026-11-14T09:51:59.915583+00:00"}
{"correlation_id": "f9f0d88007ef4917a3ed022f17532389", "detail_type": "OrderCancelled", "entries": [{"EventId": "18e7e097-fcda-0462-0000-000000000003"}], "event": "published", "failed_entry_count": 0, "time": "2026-11-14T09:51:59.917511+00:00"}
```

## 3. Prueba el patrón desplegado

Compara el evento original con la regla actual usando TestEventPattern.

```bash
python lab.py diagnose
```

- Busca matched: false. Compara event_detail_type con el patrón del mismo registro.

¿Por qué esta prueba aporta más que una cola vacía?

Una cola vacía también puede significar que la entrega sigue pendiente. TestEventPattern comprueba directamente si el evento coincide con el patrón.

### Traza de referencia

```text
{"correlation_id": "91cc5151f0654b5aa44251e659c99b99", "event": "pattern_diagnosis", "event_detail_type": "OrderCreated", "matched": false, "pattern": {"detail-type": ["order.created"], "source": ["practice.orders"]}, "time": "2026-11-14T09:51:59.316009+00:00"}
```

## 4. Corrige el tipo de evento

En pattern.json, reemplaza order.created por OrderCreated. Guarda con Ctrl+O, Enter y sal con Ctrl+X. Aplica el cambio.

```bash
nano pattern.json
python lab.py repair
python lab.py inspect
```

- Confirma positive_matches: true y negative_matches: false. Revisa que el patrón desplegado contenga OrderCreated.

¿Por qué probar también un evento de cancelación?

Un patrón demasiado amplio también dejaría pasar eventos que no quieres. Antes de actualizar la regla, el helper comprueba que OrderCreated coincida y OrderCancelled quede fuera.

## 5. Publica un evento nuevo y uno de control

Publica otro OrderCreated y un OrderCancelled de control, cada uno con un correlation_id nuevo.

```bash
python lab.py resend
```

- Busca dos publicaciones aceptadas con valores distintos de correlation_id.

¿Corregir la regla recupera el evento original?

Cambiar una regla no vuelve a procesar eventos anteriores. Esta etapa publica uno nuevo, con un ID distinto al de la primera publicación.

## 6. Sigue el evento hasta SQS

Espera el evento de creación y compara su correlation_id con el de la publicación.

```bash
python lab.py verify
```

- Busca queue_delivery para OrderCreated y su correlation_id. Confirma positive_pattern_match: true y negative_pattern_match: false.

¿Qué demuestra que el control queda fuera?

TestEventPattern confirma que la regla desplegada excluye OrderCancelled. La observación de la cola dura un tiempo limitado; no ver el control durante ese intervalo no bastaría para demostrar el filtrado.

El helper espera hasta 30 segundos y elimina los mensajes después de registrarlos. Si la entrega tarda, ejecuta verify de nuevo.

### Traza de referencia

```text
{"correlation_id": "a9950d6f3e3d448f915533bd31b80402", "event": "verification", "negative_delivery_observed": false, "negative_pattern_match": false, "observation": "bounded; negative filtering established by TestEventPattern", "positive_delivered": true, "positive_pattern_match": true, "time": "2026-11-14T09:52:03.113737+00:00"}
```

## 7. Conserva la evidencia y elimina los recursos

Elimina el destino, la regla, el bus y la cola.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Busca cleanup y sigue los correlation_id desde published hasta queue_delivery.
- Linux: detén la terminal A con Ctrl+C. Docker: sal del shell; .lab/events.jsonl sigue en tu equipo.
- Si reiniciaste el emulador durante el lab, espera a que esté listo y ejecuta python lab.py reset. Vuelve a poner order.created en pattern.json antes de ejecutar prepare. Los logs anteriores se conservan.

¿Dónde se detuvo la entrega?

La publicación funcionó, pero el evento no coincidía con la regla. El patrón corregido y una publicación nueva completaron el flujo.

## Publicación y entrega verificadas

Separaste la aceptación del evento, la coincidencia del patrón y la recepción en SQS.

## Referencias

- [EventBridge · patrones de eventos](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-pattern.html)
- [API PutEvents](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutEvents.html)
- [AWS Emulator · fidelidad](https://docs.aws.amazon.com/emulator/latest/userguide/fidelity.html)
