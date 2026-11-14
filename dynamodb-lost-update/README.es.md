# DynamoDB: dos escrituras, una actualización perdida

Reproduce un incremento perdido, rechaza una escritura obsoleta y reintenta con datos actuales.

Dos procesos leen el mismo contador y sus escrituras tienen éxito, pero el valor solo aumenta una vez. Reproduce la secuencia con AWS Emulator y usa una condición de versión para detectar el conflicto.

## Prepara tu entorno

### 1. Clona el repositorio

Si ya tienes el repositorio, ejecuta git pull desde su raíz y entra en el directorio de este lab.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/dynamodb-lost-update
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

#### 3. Abre tu terminal de trabajo

En otra terminal, entra en el directorio del lab y activa el entorno de Python. Ajusta la ruta si clonaste el repositorio en otra ubicación.

**Terminal B · práctica**

```bash
cd devops-in-practice-labs/dynamodb-lost-update
source .venv/bin/activate
```

Continúa en la terminal B cuando el emulador esté listo.

### Docker

#### 2. Entra al ambiente del lab

El contenedor incluye AWS Emulator 1.0.322, Python y nano. Los logs quedan en .lab en tu equipo.

**Tu terminal → shell del contenedor**

```bash
bash docker-lab.sh
```

- En Windows, ejecuta los comandos en WSL con Docker usando contenedores Linux.

Continúa en el shell que se abre.

## 1. Crea el contador

Crea una tabla con un contador en value 0 y version 0.

```bash
python lab.py prepare
python lab.py inspect
```

- Busca status ACTIVE y applied_writer.check_version en false.
- Abre lab.py y busca write: calcula el siguiente valor a partir de una lectura guardada.

¿Una escritura exitosa demuestra que no se perdió otra actualización?

UpdateItem acepta el valor de reemplazo si ninguna condición lo rechaza. El éxito no dice nada sobre la lectura usada para calcular ese valor.

## 2. Haz que ambos procesos lean el mismo valor

Lee el contador desde A y B antes de ejecutar sus escrituras. Ambos calculan 0 + 1.

```bash
python lab.py collide
python lab.py inspect
```

- Busca snapshots_read con dos lecturas de value 0 y después dos eventos write_accepted con value 1.

¿Por qué dos incrementos aceptados dejaron el valor en 1?

B sobrescribió el resultado de A con el mismo valor. El script controla el orden para reproducir lo que puede ocurrir entre dos procesos concurrentes.

Ambas lecturas son fuertemente consistentes: reflejan el valor guardado en ese momento, pero no impiden que otro proceso lo cambie antes de la siguiente escritura.

## 3. Encuentra el incremento perdido

Compara las escrituras aceptadas con el valor guardado.

```bash
python lab.py diagnose
```

- Busca lost_update: accepted_writes es 2, pero observed.value es 1.

¿Basta con volver a leer antes de escribir?

Otro proceso puede cambiar el valor entre tu lectura y tu escritura. La escritura debe comprobar que la versión leída siga vigente.

### Traza de referencia

```text
{"accepted_writes": 2, "cause": "Both writers calculated 0 + 1 before either write.", "event": "lost_update", "expected_value": 2, "observed": {"value": 1, "version": 1}, "time": "2026-11-14T09:47:11.502727+00:00"}
```

## 4. Comprueba la versión al escribir

Cambia check_version a true en writer.json. Guarda con Ctrl+O, Enter y sal con Ctrl+X. Aplica la configuración.

```bash
nano writer.json
python lab.py repair
python lab.py inspect
```

- Comprueba que file_writer y applied_writer muestren check_version true.

¿Dónde se evalúa la condición?

El helper agrega ConditionExpression a UpdateItem. DynamoDB comprueba la versión y escribe el cambio en una sola operación atómica. check_version configura cómo escribe el helper.

## 5. Rechaza la escritura obsoleta

Reinicia el contador a 0 y repite la secuencia con la condición activada. Esta nueva ejecución permite comparar los resultados; el incremento perdido en la anterior no se recupera.

```bash
python lab.py replay
python lab.py inspect
```

- A tiene éxito. B recibe ConditionalCheckFailedException porque su versión 0 ya no coincide con la versión 1.

¿La condición completó ambos incrementos?

Evitó una sobrescritura. El incremento de B sigue pendiente. Repetir la solicitud anterior de B volvería a fallar la misma condición.

### Traza de referencia

```text
{"check_version": true, "code": "ConditionalCheckFailedException", "event": "write_rejected", "observed": {"value": 1, "version": 1}, "snapshot": {"value": 0, "version": 0}, "time": "2026-11-14T09:47:12.253195+00:00", "writer": "B"}
```

## 6. Vuelve a leer y calcula de nuevo

Actualiza la lectura de B y calcula su incremento a partir del valor actual.

```bash
python lab.py retry
python lab.py inspect
```

- Sigue snapshot_refreshed de la versión 0 a la 1 y después write_accepted con value 2 y version 2.

¿Qué cambió entre la solicitud rechazada y este reintento?

B leyó el elemento actual y recalculó tanto el nuevo valor como la versión esperada. El helper hace un reintento explícito; una aplicación necesitaría una política de conflictos con límites.

## 7. Comprueba ambos incrementos

Lee el contador final y comprueba la configuración del helper.

```bash
python lab.py verify
```

- Busca verification con result PASS, value 2 y version 2.

¿El bloqueo optimista es la única forma de incrementar un contador?

Para un contador simple, un incremento atómico con UpdateItem evita este patrón de leer, calcular y escribir. Las condiciones de versión son útiles cuando una decisión depende de valores leídos antes.

### Traza de referencia

```text
{"event": "verification", "increments": 2, "observed": {"value": 2, "version": 2}, "result": "PASS", "time": "2026-11-14T09:47:12.928307+00:00"}
```

## 8. Conserva la evidencia y elimina la tabla

Elimina la tabla. La secuencia queda en .lab/events.jsonl en tu equipo.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Busca cleanup_completed. Detén la terminal del emulador en Linux o sal del shell de Docker.
- Si el emulador se reinició durante el lab, ejecuta python lab.py reset. Vuelve a poner check_version en false antes de preparar otra ejecución. Los logs se conservan.

¿Qué eventos distinguen una actualización perdida de una escritura rechazada?

Compara los dos eventos write_accepted sin protección con write_rejected, snapshot_refreshed y la verificación final. Son trazas del helper con respuestas reales de las APIs.

Comparte events.jsonl; el log de arranque del emulador puede contener credenciales locales generadas.

## El reintento conserva ambos cambios

Usa tus logs para explicar por qué una lectura consistente no evitó la actualización perdida, qué rechazó la condición y por qué el siguiente intento tuvo éxito.

## Referencias

- [AWS Emulator · instalación](https://docs.aws.amazon.com/emulator/latest/userguide/setting-up.html)
- [DynamoDB · bloqueo optimista](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBMapper.OptimisticLocking.html)
- [DynamoDB · expresiones de actualización](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html)
