# Secrets Manager: vuelve a la versión que funcionaba

Publica una versión incompatible y recupera la que funciona moviendo la etiqueta AWSCURRENT.

El código no cambió, pero la siguiente lectura del secreto falla en el consumidor. Reproduce el problema con datos de ejemplo en AWS Emulator y elige qué versión recuperar.

## Prepara tu entorno

### 1. Clona el repositorio

Si ya tienes el repositorio, ejecuta git pull desde su raíz y entra en el directorio de este lab.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/secrets-version-rollback
```

### Linux

#### 2. Arranca el emulador

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

En otra terminal, entra en la carpeta del lab y activa el entorno de Python. Ajusta la ruta si clonaste el repo en otra ubicación.

**Terminal B · práctica**

```bash
cd devops-in-practice-labs/secrets-version-rollback
source .venv/bin/activate
```

Cuando el emulador esté listo, continúa en la terminal B.

### Docker

#### 2. Entra al entorno del lab

Inicia el contenedor desde la carpeta del lab. Incluye AWS Emulator 1.0.322, Python y nano. Los logs se guardan en .lab en tu equipo.

**Tu terminal → shell del contenedor**

```bash
bash docker-lab.sh
```

- Usa Bash y Docker con contenedores Linux; en Windows, ejecuta estos comandos en WSL.

El shell se abre cuando el emulador está listo. Continúa ahí.

## 1. Crea el secreto y prueba su lectura

Crea un secreto de ejemplo y ejecuta el validador del consumidor.

```bash
python lab.py prepare
python lab.py inspect
```

- Busca consumer_read con result ACCEPTED y guarda el version_id.
- Abre read_version en lab.py: el consumidor espera schema igual a 1 y un api_key no vacío. El log guarda el resultado de la validación sin incluir el valor del secreto.

¿Qué devuelve GetSecretValue si no indicas una versión?

GetSecretValue devuelve la versión con la etiqueta AWSCURRENT. El ID identifica la versión; la etiqueta puede moverse.

## 2. Publica una versión incompatible

Publica un documento con schema 2 y token en lugar de api_key.

```bash
python lab.py publish-bad
python lab.py inspect
```

- Busca consumer_read con REJECTED y valid false.
- Compara las etiquetas: la nueva versión tiene AWSCURRENT y la anterior, AWSPREVIOUS.

¿Por qué Secrets Manager acepta un valor que la aplicación rechaza?

El servicio almacena el valor; no conoce el formato que exige tu consumidor. En este lab, el fallo lo produce la validación de Python al leer el nuevo documento.

### Traza de referencia

```text
{"event": "consumer_read", "result": "ACCEPTED", "stages": ["AWSCURRENT"], "time": "2026-11-14T09:46:29.480843+00:00", "valid": true, "version_id": "ac0e556f-6f04-45e7-ad26-1d3e1a09dd70"}
{"event": "consumer_read", "reason": "consumer_requires_schema_1_and_api_key", "result": "REJECTED", "stages": ["AWSCURRENT"], "time": "2026-11-14T09:46:29.882311+00:00", "valid": false, "version_id": "795b2924-b170-484f-adf0-261c67676152"}
```

## 3. Encuentra una versión válida

Lee cada versión por su ID y compara el resultado del validador.

```bash
python lab.py diagnose
```

- Encuentra version_checked con valid true y copia su version_id.
- Comprueba que la versión actual sigue siendo la rechazada.

¿Basta con elegir la versión etiquetada AWSPREVIOUS?

AWSPREVIOUS identifica la versión que antes era actual. Comprueba que pase la validación: la etiqueta por sí sola no garantiza que funcione con la aplicación.

## 4. Mueve AWSCURRENT a la versión elegida

En recovery.json, cambia el valor de version_id por el ID que pasó la validación. Guarda con Ctrl+O, Enter y sal con Ctrl+X. Ejecuta repair para mover la etiqueta.

```bash
nano recovery.json
python lab.py repair
python lab.py inspect
```

- Comprueba from_version y to_version en label_moved.
- La versión válida debe tener AWSCURRENT; la rechazada queda con AWSPREVIOUS.

¿El rollback creó otra versión del secreto?

No. UpdateSecretVersionStage mueve las etiquetas entre versiones existentes. AWSPREVIOUS pasa automáticamente a la versión que perdió AWSCURRENT.

## 5. Vuelve a leer el secreto

Lee el secreto sin fijar versión y vuelve a ejecutar el validador.

```bash
python lab.py verify
```

- Busca verification con result PASS, current.valid true y el ID recuperado.

¿Qué pasaría si la aplicación conservara el valor anterior en caché?

Este consumidor hace una lectura nueva. Mover AWSCURRENT no actualiza una copia que la aplicación ya tiene en memoria; su estrategia de caché decide cuándo vuelve a leer.

### Traza de referencia

```text
{"consumer": "fresh_read_without_version_selector", "current": {"stages": ["AWSCURRENT"], "valid": true, "version_id": "ac0e556f-6f04-45e7-ad26-1d3e1a09dd70"}, "event": "verification", "previous": {"stages": ["AWSPREVIOUS"], "valid": false, "version_id": "795b2924-b170-484f-adf0-261c67676152"}, "result": "PASS", "time": "2026-11-14T09:46:30.684885+00:00"}
```

## 6. Limpia y conserva la secuencia

Elimina el secreto de ejemplo. Las trazas quedan en .lab/events.jsonl en tu equipo.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Busca cleanup_completed y sigue los cambios de etiquetas de principio a fin.
- Linux: detén la terminal A con Ctrl+C. Docker: sal del shell; el archivo .lab/events.jsonl sigue disponible en el directorio del lab.
- Si reiniciaste el emulador a mitad del lab, ejecuta python lab.py reset y vuelve a prepare. Los logs anteriores se conservan.

¿Qué evidencia explica la recuperación?

Una lectura rechazada, la validación de la versión elegida, el movimiento de AWSCURRENT y una lectura nueva aceptada. Los IDs permiten seguir la misma versión sin registrar su contenido.

## Recuperación comprobada

Moviste AWSCURRENT a una versión válida y comprobaste que una nueva lectura del consumidor la acepta.

## Referencias

- [AWS Emulator](https://docs.aws.amazon.com/emulator/latest/userguide/what-is-service.html)
- [Secrets Manager · UpdateSecretVersionStage](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_UpdateSecretVersionStage.html)
- [Código y trazas de referencia](https://github.com/leodc/devops-in-practice-labs/tree/main/secrets-version-rollback)
