# SQS: ¿por qué volvió el mensaje?

Recibe el mismo mensaje dos veces y comprueba qué cambia cuando lo borras.

Leer un mensaje de SQS no lo borra. Compruébalo con una cola, un mensaje y cuatro pasos.

La práctica toma unos cinco minutos una vez preparado el entorno.

## Prepara tu entorno

### 1. Clona el repositorio

Si ya tienes el repositorio, ejecuta git pull desde su raíz y entra en el directorio de este lab.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-message-returns
```

### Linux

#### 2. Arranca el emulador

Instala AWS Emulator 1.0.322 y Python con pip y venv. Después prepara el entorno e inicia el emulador.

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

En otra terminal, entra en la carpeta del lab y activa el entorno de Python. Ajusta la ruta si clonaste el repo en otra ubicación.

**Terminal B · práctica**

```bash
cd devops-in-practice-labs/sqs-message-returns
source .venv/bin/activate
```

Cuando el emulador esté listo, continúa en la terminal B.

### Docker

#### 2. Entra al entorno del lab

El contenedor incluye AWS Emulator 1.0.322 y Python. Los logs quedan en .lab en tu equipo.

**Tu terminal → shell del contenedor**

```bash
bash docker-lab.sh
```

- Usa Bash y Docker con contenedores Linux; en Windows, ejecuta estos comandos en WSL.

El shell se abre cuando el emulador está listo. Continúa ahí.

## 1. Recibe un mensaje sin borrarlo

Crea la cola, envía hello-again y recíbelo una vez.

```bash
python lab.py prepare
python lab.py receive
```

- Busca received_without_delete con receive_count 1 y guarda su message_id.

¿Ya desapareció el mensaje de la cola?

ReceiveMessage lo oculta temporalmente. El helper no llama a DeleteMessage; en esta práctica, la visibilidad se restablece después de tres segundos.

## 2. Recibe el mismo mensaje otra vez

Vuelve a ejecutar receive. El comando espera si el mensaje todavía está oculto.

```bash
python lab.py receive
```

- Compara message_id: es el mismo. receive_count ahora es 2.

¿Alguien tuvo que enviar otro mensaje?

No. El mensaje original volvió a estar disponible porque no se borró. Eso permite intentar de nuevo un trabajo que quedó pendiente. Si repites el comando, el contador seguirá aumentando.

### Traza de referencia

```text
{"body": "hello-again", "event": "received_without_delete", "message_id": "63b1c706-8395-4a85-aad5-fd0f644083c5", "receive_count": 1, "time": "2026-11-14T10:00:38.879509+00:00", "visibility_seconds": 3}
{"body": "hello-again", "event": "received_without_delete", "message_id": "63b1c706-8395-4a85-aad5-fd0f644083c5", "receive_count": 2, "time": "2026-11-14T10:00:42.174903+00:00", "visibility_seconds": 3}
```

## 3. Bórralo y comprueba el resultado

Ejecuta ack para recibirlo con un receipt handle nuevo y borrarlo inmediatamente. Después verifica la cola.

```bash
python lab.py ack
python lab.py verify
```

- Verás received_for_delete con otra recepción, seguido de deleted.
- Busca verification con PASS, cero mensajes y ningún mensaje en vuelo.

¿Por qué ack vuelve a recibir antes de borrar?

Pudiste detenerte a leer entre pasos. Una nueva recepción obtiene un receipt handle vigente para DeleteMessage. Abre ack en lab.py para ver ambas llamadas.

### Traza de referencia

```text
{"counts": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "event": "verification", "messages_returned": 0, "result": "PASS", "time": "2026-11-14T10:00:46.541568+00:00"}
```

## 4. Conserva la secuencia y termina

Elimina la cola y lee la traza completa.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Sigue el mismo message_id desde sent hasta deleted.
- Linux: detén la terminal A con Ctrl+C. Docker: sal del shell. .lab/events.jsonl queda en tu equipo.

¿Qué faltaba después de recibir el mensaje?

Borrarlo después de completar el trabajo. Recibir y confirmar que terminaste son operaciones distintas. Si reiniciaste el emulador antes de terminar, ejecuta python lab.py reset antes de volver a prepare.

## Recibir no es borrar

Observaste la reentrega del mismo mensaje y comprobaste su eliminación. Esa diferencia también importa cuando una función procesa mensajes por ti.

## Referencias

- [SQS · Tiempo de visibilidad](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)
- [SQS · DeleteMessage](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_DeleteMessage.html)
- [Código y trazas de referencia](https://github.com/leodc/devops-in-practice-labs/tree/main/sqs-message-returns)
