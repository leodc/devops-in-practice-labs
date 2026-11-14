# S3: recupera el archivo que sobrescribiste y borraste

Recupera una versión anterior de un objeto de S3 y comprueba su contenido.

Sobrescribiste una configuración válida y después la borraste. Inspecciona las versiones que conserva S3 y recupera el contenido correcto con AWS Emulator.

## Prepara tu entorno

### 1. Clona el repositorio

Si ya tienes el repositorio, ejecuta git pull desde su raíz y entra en el directorio de este lab.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/s3-version-recovery
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
cd devops-in-practice-labs/s3-version-recovery
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

## 1. Sube una configuración válida

Crea un bucket con versionado y sube config.json con timeout_seconds en 30.

```bash
python lab.py prepare
python lab.py inspect
```

- Busca versioning: Enabled y el version_id actual.
- Guarda el SHA-256 original para comparar el contenido después de recuperarlo.

¿Qué identifica el ID de versión?

Una versión concreta del objeto. Las siguientes escrituras sobre la misma clave reciben sus propios IDs.

## 2. Sobrescribe el archivo y bórralo

Cambia el timeout a 0 y después borra config.json sin indicar una versión.

```bash
python lab.py break
python lab.py inspect
```

- La lectura actual devuelve NoSuchKey.
- El historial conserva dos versiones del objeto y un marcador de borrado con latest en true.

¿El borrado eliminó las dos versiones guardadas?

Al borrar sin VersionId con el versionado activo, S3 añade un marcador de borrado. Un GET normal ya no devuelve el objeto, pero todavía puedes leer las versiones anteriores por su ID.

## 3. Encuentra la versión válida

Lee las versiones guardadas y compara su contenido.

```bash
python lab.py diagnose
```

- Busca timeout_seconds: 30 y copia su version_id.
- Compáralo con la versión que contiene timeout_seconds: 0.

¿Bastaría con quitar el marcador de borrado?

Volvería a aparecer la versión más reciente, que tiene el timeout incorrecto. Necesitas recuperar la anterior.

## 4. Restaura la versión elegida

En recovery.json, cambia el valor de version_id por el ID de la versión válida que encontraste en diagnose. Guarda en nano con Ctrl+O, Enter y sal con Ctrl+X.

```bash
nano recovery.json
python lab.py repair
```

- Busca source_version y new_version en version_restored.
- Comprueba que source_version sea el ID que elegiste.

¿Por qué el objeto restaurado tiene otro ID de versión?

CopyObject lee la versión de origen elegida y escribe una nueva versión en la misma clave. Las versiones anteriores y el marcador de borrado siguen en el historial.

## 5. Comprueba el archivo recuperado

Lee el objeto actual y compáralo con el contenido original.

```bash
python lab.py verify
python lab.py inspect
cat .lab/recovered-config.json
```

- Busca matches_original: true y el SHA-256 original.
- El historial tiene cuatro entradas: las dos versiones anteriores, el marcador de borrado y la versión restaurada.

¿Por qué comparar el contenido además de los IDs?

El nuevo ID indica que hubo una escritura. El hash comprueba que el objeto actual contiene exactamente los mismos bytes que el original.

### Traza de referencia

```text
{"error_code": "NoSuchKey", "event": "current_object_missing", "http_status": 404, "time": "2026-11-14T09:46:08.854733+00:00"}
{"event": "version_restored", "new_version": "ba240be8196984c3ebbbbdece4ce530b", "source_version": "014eff17fab3d44869c86a6beec09942", "time": "2026-11-14T09:46:09.255350+00:00"}
{"event": "recovery_verified", "file": ".lab/recovered-config.json", "history_entries": 4, "matches_original": true, "sha256": "bb05bf2c57c1f5aa3c5fb93c7e05b71e5e43848f584896c8047c16df3c2563a9", "time": "2026-11-14T09:46:09.434978+00:00", "version_id": "ba240be8196984c3ebbbbdece4ce530b"}
```

## 6. Elimina el bucket y conserva la evidencia

Borra todas las versiones y los marcadores de borrado; después elimina el bucket.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Sigue los IDs de versión en events.jsonl, desde la primera subida hasta la recuperación.
- Conserva .lab/recovered-config.json para leerlo incluso después de detener el emulador.
- Linux: detén la terminal A con Ctrl+C. Docker: sal del shell; los archivos de .lab siguen en tu equipo.
- Si reiniciaste el emulador durante el lab, ejecuta python lab.py reset y vuelve a prepare. Los logs anteriores se conservan.

¿Por qué cleanup borra las versiones explícitamente?

Borrar solo la clave actual añadiría otro marcador de borrado. Para eliminar un bucket con versionado, primero hay que quitar sus versiones y marcadores.

## La configuración válida vuelve a estar disponible

Recuperaste la versión elegida, comprobaste su contenido y conservaste un registro local de la secuencia.

## Referencias

- [Código del lab en GitHub ↗](https://github.com/leodc/devops-in-practice-labs/tree/main/s3-version-recovery)
- [Versionado de S3 ↗](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [Restaurar versiones de objetos ↗](https://docs.aws.amazon.com/AmazonS3/latest/userguide/RestoringPreviousVersions.html)
