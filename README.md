# Laboratorio Fabric CI/CD: DataHub

Este repositorio contiene el laboratorio de la opción 2: preparar una versión en Git, probarla en TEST y publicar esa misma versión en PROD después de una aprobación.

La primera etapa es más pequeña: publicar **Interest Rates y su modelo en TEST**, manteniendo Stocks Index fuera del despliegue. Después automatizaremos esa operación. El primer workflow comprueba autenticación de forma manual; todavía no implementa releases, aprobación ni despliegue a producción.

## 1. Qué tenemos

La carpeta `DataHub` representa el contenido de un workspace. No hace falta duplicarla para DEV, TEST y PROD: cambia el workspace de destino.

| Solución | Modelo: datos y cálculos | Reporte: presentación |
| --- | --- | --- |
| Interest Rates | `Interest Rates.SemanticModel` | `Interest Rates.Report` |
| Stocks Index | `Stocks Index.SemanticModel` | `Stocks Index.Report` |

Por tanto, hay cuatro artefactos publicables, aunque en Power BI Desktop veamos dos proyectos.

Los archivos `.pbip` permiten abrir los proyectos en Desktop. Cada `.platform` identifica un artefacto. Los archivos `definition.pbir` enlazan cada reporte con su modelo mediante una ruta relativa (`byPath`). Conservaremos esos archivos e identificadores.

La librería convierte la referencia `byPath` en la conexión al modelo del destino durante la publicación. Para este ejercicio seleccionamos siempre el reporte junto con su modelo, presentes en la misma carpeta de workspace. [Binding de reportes en fabric-cicd](https://microsoft.github.io/fabric-cicd/1.4.0/how_to/parameterization/#reports).

Los modelos tienen particiones Import y consultan CSV de FRED mediante `Web.Contents`. Publicar la definición y cargar los datos son operaciones distintas. Tendremos que comprobar las conexiones del origen y ejecutar un refresh antes de dar por válida la visualización en TEST.

## 2. Primer paso: ver la selección, sin publicar

Desde PowerShell:

```powershell
Set-Location 'C:\Fabric_CICD\fabric-cicd'
python scripts/deploy_test.py --solution interest-rates
```

La salida debe mostrar únicamente:

```text
Selected items:
  - Interest Rates.SemanticModel
  - Interest Rates.Report
Deletion: disabled. Data refresh: not included.
PREVIEW ONLY: local pair checked; no authentication or Fabric calls.
```

Este comando lee archivos locales y comprueba la identidad de los dos artefactos y la referencia reporte → modelo. No instala paquetes ni se conecta a Fabric. No valida permisos, capacidad, credenciales del origen ni la aceptación de las definiciones por el servicio.

Para revisar el otro conjunto:

```powershell
python scripts/deploy_test.py --solution stocks-index
```

`--solution` es obligatorio: una selección omitida o incorrecta no se convierte en un despliegue completo.

## 3. Cómo funciona el script

El archivo `scripts/deploy_test.py` hace cuatro cosas:

1. Traduce `interest-rates` a una lista explícita de dos artefactos.
2. Comprueba los archivos locales mínimos y muestra la selección.
3. Solo si se agrega `--deploy`, usa un Service Principal y llama a `fabric-cicd`. Con `--check-auth` únicamente solicita un token a Microsoft Entra.
4. Pasa la lista a `publish_all_items(..., items_to_include=items)`.

Aunque la función se llama `publish_all_items`, el argumento `items_to_include` limita los ítems publicados. Esta función selectiva requiere las banderas experimentales `enable_experimental_features` y `enable_items_to_include`; la documentación advierte sobre las dependencias. Probaremos precisamente ese comportamiento. [Selección de ítems](https://microsoft.github.io/fabric-cicd/1.4.0/how_to/optional_feature/#item-level-filtering).

No usamos la función de eliminación de huérfanos. Un ítem ajeno a la selección no debe borrarse por quedar fuera de esta prueba.

El script siempre selecciona un par reporte/modelo; todavía no demuestra el caso de actualizar solo el reporte sin republicar su modelo.

## 4. Datos necesarios antes de la primera publicación

Estado confirmado por el usuario:

- `DataHub-Dev` está conectado a este repositorio, rama `dev`, carpeta `/DataHub`.
- `main` no tiene sincronización con Fabric; se reserva para releases.
- `DataHub-Test` y `DataHub-Prod` están vacíos y no tienen conexión Git.
- Existe un Service Principal con Client ID y Secret, utilizado en el PoC anterior.

Antes de publicar comprobaremos el ID de TEST, su capacidad y los permisos del Service Principal en ese nuevo workspace. Haber usado esa identidad en el PoC anterior no prueba que tenga acceso al nuevo TEST.

El ID del workspace aparece en su URL, por ejemplo `https://app.fabric.microsoft.com/groups/<workspace-id>/list`. Es un identificador, no una contraseña.

El nombre `deploy_test.py` y el valor `environment="TEST"` no verifican qué ambiente representa un GUID: el destino real es el ID indicado. Confirmaremos que corresponde al TEST de laboratorio antes de usarlo.

## 5. Paso actual: autenticación desde GitHub Actions

El usuario confirmó que este repositorio tiene un **Actions Secret** llamado `AZURE_CREDENTIALS`, con las claves `tenantId`, `clientId` y `clientSecret`. Debe contener los valores reales, no los textos de ejemplo.

Conservamos ese formato. No hace falta crear tres secretos separados, instalar Azure CLI ni cargar credenciales en PowerShell. GitHub entregará el JSON al programa durante la ejecución. [Uso de Secrets en Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

La instalación local de `.venv` y `fabric-cicd` 1.4.0 ya fue comprobada. GitHub utiliza otra computadora temporal, llamada **runner**, y por eso instala allí las dependencias de `requirements.txt` en cada ejecución. Las dependencias transitivas todavía no están bloqueadas; incorporaremos ese control antes de las releases reproducibles.

### Archivos preparados

| Archivo | Función |
| --- | --- |
| `.github/workflows/check-fabric-auth.yml` | Instrucciones que GitHub ejecuta cuando el usuario presiona Run workflow. |
| `scripts/deploy_test.py` | Lee el secreto JSON y, con `--check-auth`, solicita un token a Microsoft Entra. |
| `requirements.txt` | Selecciona `fabric-cicd==1.4.0`; su instalación incluye Azure Identity. |
| `.gitignore` | Excluye el entorno virtual y otros archivos locales. |

El workflow se llama **01 - Comprobar autenticacion Fabric**. Solo tiene el evento `workflow_dispatch`: no se inicia por push, pull request ni sincronización de Fabric. Tiene permisos de lectura del repositorio. Los permisos de GitHub y los del Service Principal en Fabric son independientes.

### Qué debe hacer el usuario ahora

1. Revisar y llevar los archivos preparados a GitHub mediante su operación habitual de commit/push o PR. Deben estar el workflow, el script actualizado y `requirements.txt`, junto con los artefactos de `DataHub` ya existentes. Incluir también README y `.gitignore`.
2. Para que aparezca el botón manual, el workflow debe existir en la **rama predeterminada del repositorio**. Para este laboratorio utilizaremos `main`; verificar en GitHub que siga siendo la predeterminada. Si se subió inicialmente a `dev`, incorporar estos archivos de automatización a `main` mediante un PR revisado. No mezclar cambios de reportes ajenos a esta preparación.
3. En GitHub, abrir **Actions** y seleccionar **01 - Comprobar autenticacion Fabric**.
4. Pulsar **Run workflow**, seleccionar **main** y confirmar **Run workflow**.
5. Abrir la ejecución, el job **Comprobar Service Principal** y el paso **Comprobar autenticacion sin desplegar**.

La rama predeterminada de GitHub y la rama sincronizada por Fabric son configuraciones distintas: `main` puede ser la predeterminada mientras DataHub-Dev sincroniza `dev` y `/DataHub`. Publicar el workflow en `main` no conecta esa rama a Fabric. [Ejecución manual de workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

El asistente prepara y revisa archivos locales. Los comandos Git, el push y las ejecuciones reales en GitHub/Fabric los realiza el usuario.

### Qué va a ocurrir

GitHub descargará el commit correspondiente a la ejecución, preparará Python 3.11 e instalará las dependencias. Después ejecutará:

```text
python scripts/deploy_test.py --solution interest-rates --check-auth
```

El programa comprueba el par local de Interest Rates y solicita un token mediante `ClientSecretCredential`. No llama al cliente de workspaces ni a `publish_all_items` en este modo. La autenticación requiere comunicación con Microsoft Entra, pero no accede a TEST, PROD ni DEV. [ClientSecretCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.clientsecretcredential?view=azure-python).

La última línea esperada es:

```text
AUTH OK: Entra issued a token. Workspace access and deployment are NOT checked.
```

`Target workspace ID: (not configured)` es normal: no hace falta un destino para comprobar la identidad.

El programa no muestra el token y registra los campos del JSON para que GitHub los oculte en los logs. Un token válido prueba la autenticación, pero todavía no valida permisos de Fabric, configuración del tenant, capacidad, binding ni refresh.

### Si aparece un error

| Resultado | Qué revisar |
| --- | --- |
| No aparece Run workflow | El archivo debe estar en la rama predeterminada y usar `workflow_dispatch`; la cuenta necesita permiso para ejecutarlo. |
| `AZURE_CREDENTIALS must contain valid JSON` | Existencia del secreto en este repositorio y formato del JSON. |
| `Missing or invalid credential field` | Que existan las tres claves con texto no vacío. |
| `must be a real, nonzero UUID` | Que Tenant ID y Client ID sean los IDs reales, no los ejemplos. |
| `Authentication failed` | Tenant, aplicación y **Value** del secreto vigente; no usar Secret ID. |
| `Cannot reach Microsoft Entra` | Conectividad del runner con Entra. |

Compartir la salida de estado o el error, sin valores de credenciales. Una vez confirmado `AUTH OK`, prepararemos la comprobación de acceso a DataHub-Test y después su despliegue manual desde Actions. Este workflow no publica aunque la autenticación sea exitosa.

## 6. Cómo sabremos que la prueba funcionó

Antes del despliegue registraremos el inventario de TEST y, si Stocks Index ya existe, su estado inicial. Después comprobaremos:

1. Interest Rates aparece como reporte y como modelo semántico.
2. El reporte utiliza el modelo de TEST.
3. Stocks Index no aparece si antes no existía; si existía, sus definiciones no se modificaron por esta publicación.
4. Las conexiones de datos están configuradas y el refresh de Interest Rates termina correctamente.
5. El gráfico muestra datos.

Si TEST estaba vacío, esta prueba demuestra exclusión de Stocks Index, pero no demuestra todavía que un ítem existente queda intacto. Para ello estableceremos una base con ambos conjuntos y repetiremos una actualización selectiva de Interest Rates.

## 7. Después de comprobar la publicación

| Etapa | Resultado esperado |
| --- | --- |
| Selección local | Entender exactamente qué dos ítems se publicarían. |
| Publicación en TEST | Comprobar selección, binding y refresh reales. |
| Base con ambos conjuntos | Cambiar Interest Rates y verificar que Stocks Index permanece intacto. |
| Ramas `dev` y `main` (ya configuradas) | DEV sincroniza `dev`; `main` prepara candidatos de release. |
| Tag y SHA | Identificar una versión concreta de los archivos. |
| GitHub Actions (autenticación preparada) | Comprobar la identidad y luego incorporar el despliegue manual. |
| Aprobación y PROD de laboratorio | Publicar el mismo candidato probado, con autorización. |

Un commit registra una versión; su SHA la identifica. Una rama puede avanzar a nuevos commits. Un tag asigna un nombre a un commit. En la opción 2, `dev` integra trabajo y `main` prepara releases; una versión seleccionada se despliega primero a TEST y después a PROD. [Opción 2 de Microsoft](https://learn.microsoft.com/en-us/fabric/cicd/manage-deployment#option-2---definition-based-deployments-from-a-shared-release-commit).

El usuario creó `dev` desde `main` y conectó `DataHub-Dev` a `dev` en `/DataHub`. Antes de la primera publicación, el usuario comprobará la rama y versión locales elegidas para la prueba. El script local publica los archivos presentes en disco: todavía no garantiza una versión inmutable ni sustituye el futuro manifiesto de release.
