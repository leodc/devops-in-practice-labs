# SQS + Lambda: rompe el flujo, recupera el mensaje

Provoca un fallo en Lambda, sigue los reintentos de SQS y rescata el mensaje de la DLQ. Nuestro primer lab local: código real, logs reales y sin cuenta de AWS.

Un mensaje falla una y otra vez hasta terminar en una dead-letter queue (DLQ). Reproduce ese fallo con AWS Emulator, encuentra la causa en los logs y recupera el mensaje después de corregir el consumidor.

## Prepara tu entorno

### 1. Clona el repositorio

Ejecuta el resto de los comandos desde esta carpeta del lab.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-lambda-retries
```

### Linux

#### 2. Arranca el emulador

Instala AWS Emulator 1.0.322 y Python con pip y venv. Después prepara el entorno de Python y arranca el emulador.

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
cd devops-in-practice-labs/sqs-lambda-retries
source .venv/bin/activate
```

Cuando el emulador esté listo, continúa en la terminal B.

### Docker

#### 2. Entra al entorno del lab

La imagen incluye AWS Emulator 1.0.322, Python y nano. Constrúyela desde la carpeta del lab y abre su shell.

**Tu terminal → shell del contenedor**

```bash
docker build -t sqs-lambda-practice .
docker run --rm -it --name sqs-lambda-practice --network none --memory=2g --memory-swap=2g sqs-lambda-practice
```

- Docker debe estar configurado para usar contenedores Linux.

La shell se abre cuando el emulador está listo. Continúa ahí.

## 1. Crea las colas y la función

Crea la cola origen, la DLQ y la función Lambda. Deja el event source mapping desactivado para inspeccionarlos antes de procesar mensajes.

```bash
python lab.py prepare
python lab.py inspect
```

- Comprueba que el mapping esté en Disabled, fail_poison en true y ambas colas vacías.
- Abre handler.py y encuentra qué hace fallar a order-poison. El lab usa un registro por invocación, timeout de función de 1 segundo, visibility timeout de 6 segundos y maxReceiveCount 3.

¿Qué puedes inspeccionar con el mapping desactivado?

Puedes revisar la función y las colas antes de iniciar el consumo. Aunque envíes mensajes, no se procesarán hasta que actives el mapping.

Estos valores acortan la práctica. AWS recomienda un visibility timeout de al menos seis veces el timeout de la función y maxReceiveCount de al menos cinco; aquí usamos tres para llegar antes a la DLQ.

## 2. Envía dos mensajes

Envía order-ok y order-poison con el consumo aún desactivado.

```bash
python lab.py send
python lab.py inspect
```

- Busca los dos eventos sent y guarda el message_id de order-poison.
- Comprueba que haya dos mensajes visibles en la cola origen y ninguno en la DLQ.

¿Por qué todavía no hay logs del handler?

El event source mapping consulta SQS e invoca Lambda. Mientras esté desactivado, ambos mensajes permanecen en la cola.

## 3. Activa el consumo

Activa el mapping. Lambda procesará los mensajes y los reintentos continuarán en segundo plano.

```bash
python lab.py consume
python lab.py inspect
```

- Busca processed para order-ok y deliberate_failure para order-poison. Repite inspect si aún no aparecen los logs.
- Sigue message_id y receive_count entre intentos.

¿Qué permite que el mensaje fallido vuelva a estar disponible?

El handler lanza un error para order-poison, así que el mensaje permanece en SQS. Cuando vence su visibility timeout, queda disponible para otro intento.

Al procesar un registro por invocación, el mensaje válido no se reintenta junto al fallido.

## 4. Inspecciona los reintentos y la DLQ

Espera a que el mensaje llegue a la DLQ y revisa sus logs y metadatos.

```bash
python lab.py diagnose
python lab.py inspect
```

- Busca tres eventos deliberate_failure del mismo mensaje, con receive_count 1, 2 y 3: un intento inicial y dos reintentos.
- Busca el evento diagnosis de order-poison. Compara su dlq_receive_count con los logs de fallo.

¿Un receive count de 4 demuestra que Lambda falló cuatro veces?

Lambda falló tres veces. La cuarta recepción fue la lectura de diagnóstico de la DLQ. El script restablece la visibilidad del mensaje inmediatamente; repetir diagnose devuelve el resultado guardado sin recibirlo otra vez.

La política de redrive de la cola origen envía el mensaje a esta DLQ. Es distinta de la configuración de DLQ de Lambda para invocaciones asíncronas.

```text
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "1"}
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "2"}
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "3"}
{"body": "order-poison", "dlq_receive_count": "4", "event": "diagnosis", "failed_deliveries": 3, "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "time": "2026-11-12T02:37:23.550458+00:00"}
```

## 5. Corrige el consumidor

En consumer.json, cambia fail_poison a false. Guarda en nano con Ctrl+O, Enter y sal con Ctrl+X. Ejecuta repair para aplicar el cambio a Lambda.

```bash
nano consumer.json
python lab.py repair
python lab.py inspect
```

- Comprueba que la función muestre fail_poison en false.
- Confirma que el mensaje siga en la DLQ.

¿Por qué la función corregida todavía no ha procesado ese mensaje?

El mapping consulta la cola origen, pero el mensaje está en la DLQ. Corregir la función no lo devuelve a la cola origen.

## 6. Devuelve el mensaje a la cola origen

Inicia una tarea de redrive. El mapping sigue activado, así que Lambda podrá procesar el mensaje en cuanto regrese.

```bash
python lab.py redrive
python lab.py inspect
```

- Busca redrive_started y su task handle. Confirma que la tarea comenzó; verify comprobará si la recuperación terminó.

¿Qué pasaría si hicieras redrive antes de corregir el fallo?

El mensaje volvería a fallar. Corrige el consumidor antes de devolver mensajes a una cola que sigue consultando.

## 7. Verifica la recuperación

Comprueba que redrive terminó, Lambda procesó order-poison y ambas colas quedaron vacías.

```bash
python lab.py verify
python lab.py inspect
```

- Busca verification con result PASS y un evento processed de order-poison.
- Revisa redrive_identity_observed. El emulador 1.0.322 conserva el ID y el contador; AWS asigna un ID y una hora de encolado nuevos después de redrive.

¿Por qué no basta con ver la DLQ vacía?

Una DLQ vacía solo indica que el mensaje salió de ella. Para confirmar la recuperación también necesitas una tarea de redrive completada, un log processed y cero mensajes visibles, en vuelo o retrasados en ambas colas.

```text
{"body": "order-poison", "event": "processed", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "5"}
{"dlq": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "event": "verification", "result": "PASS", "source": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "time": "2026-11-12T02:37:29.200757+00:00"}
```

## 8. Guarda los logs y limpia

Elimina los recursos emulados. Tus logs permanecen en .lab/events.jsonl.

```bash
python lab.py cleanup
tail -n 5 .lab/events.jsonl
```

- Comprueba que aparezca cleanup_completed.
- Linux: detén la terminal A con Ctrl+C.
- Docker: antes de salir del contenedor, ejecuta docker cp sqs-lambda-practice:/opt/lab/.lab ./practice-logs desde una terminal del host. Después sal de la shell del contenedor.
- Si reiniciaste el emulador a mitad del lab, ejecuta python lab.py reset y después python lab.py prepare. Los logs anteriores se conservan; usa las fechas para distinguir ejecuciones.

¿Qué entradas del log explican el fallo y la recuperación?

Sigue el ID original a través de los tres fallos, la lectura de la DLQ, la corrección y el redrive. Cierra con el evento processed y el resultado PASS.

Comparte events.jsonl en lugar del log de arranque del emulador, que puede contener credenciales locales generadas.

## Reconstruye el recorrido

Explica con tus logs cuándo volvió a estar disponible el mensaje, por qué llegó a la DLQ y qué confirma que la recuperación funcionó.

## Referencias

- [AWS Emulator · requisitos e instalación](https://docs.aws.amazon.com/emulator/latest/userguide/setting-up.html)
- [AWS Emulator · instalación en Linux](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-linux.html)
- [Lambda · configuración de SQS](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html)
- [Lambda · manejo de errores con SQS](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)
- [SQS · dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [SQS · redrive e identidad del mensaje](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html)
