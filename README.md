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

## 5. Autenticación desde GitHub Actions (completada)

El usuario ejecutó el workflow 01 y obtuvo `AUTH OK`. La automatización ya está también en `dev`. No es necesario repetir esta prueba ahora; el siguiente paso está en la sección 6.

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

### Cómo repetir la comprobación de autenticación si fuera necesario

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

Este workflow no publica aunque la autenticación sea exitosa. La comprobación de acceso a DataHub-Test se explica a continuación.

## 6. Paso actual: comprobar acceso de lectura a TEST

Autenticarse responde «¿quién es esta aplicación?». Ahora comprobaremos «¿puede esta aplicación ver DataHub-Test?». Todavía no comprobaremos si puede publicar.

El nuevo workflow **02 - Comprobar acceso a TEST** ejecuta `scripts/check_test_workspace.py`. Reutiliza el secreto `AZURE_CREDENTIALS` y realiza únicamente consultas GET a Fabric: obtener los datos del workspace y listar sus artefactos, incluyendo páginas adicionales si existen. Ambos endpoints admiten Service Principals y acceso de lectura. [Consultar workspace](https://learn.microsoft.com/en-us/rest/api/fabric/core/workspaces/get-workspace), [listar artefactos](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/list-items).

### A. Configurar el destino en GitHub

En el repositorio, abrir **Settings → Secrets and variables → Actions → Variables → New repository variable** y crear:

| Nombre | Valor |
| --- | --- |
| `FABRIC_TEST_WORKSPACE_ID` | El GUID completo del workspace DataHub-Test, copiado de su URL. |

Es una **Variable**, no un Secret: identifica el destino y no contiene una contraseña. Mantener `AZURE_CREDENTIALS` como Secret, sin modificarlo. No copiar la URL completa ni usar el ID de DEV, de un reporte o de un modelo. No transcribimos el GUID de la captura para evitar errores en su borde derecho.

Esta variable tampoco es el archivo `parameter.yml`: aquí solo elegimos el workspace que vamos a consultar. No estamos configurando el binding entre reportes y modelos.

### B. Incorporar y ejecutar los archivos manualmente

1. Revisar estos cambios locales: `.github/workflows/check-fabric-test.yml`, `scripts/check_test_workspace.py` y este README.
2. Incorporarlos a `dev` mediante el procedimiento Git habitual y luego llevar estos cambios de automatización a `main` mediante un PR revisado. No es necesario cambiar archivos de `DataHub`. Revisar que el PR no arrastre cambios de reportes pendientes de release.
3. Mantener `main` como rama predeterminada de GitHub y `dev` como rama sincronizada con DataHub-Dev. El workflow debe estar en la rama predeterminada para aparecer en la ejecución manual.
4. En **Actions**, abrir **02 - Comprobar acceso a TEST**, pulsar **Run workflow**, elegir **main** y confirmar la ejecución.
5. Abrir el job **Leer DataHub-Test**, paso **Comprobar acceso de lectura a TEST**, y compartir su salida sin credenciales.

El workflow solo tiene disparador manual: subir estos archivos no lo ejecuta. No hay que ejecutar un script de PowerShell ni cargar secretos en la computadora local. El asistente no realiza las operaciones Git ni las corridas reales.

### C. Interpretar el resultado

Si TEST continúa vacío, esperamos:

```text
Workspace name: "DataHub-Test"
Workspace ID: <el ID configurado>
Capacity ID (informational): <ID o valor no devuelto>
Items found: 0
READ ACCESS OK: TEST metadata and inventory retrieved. Deployment permissions are NOT checked.
No deployment, deletion or data refresh was requested.
```

El script verifica que el nombre sea exactamente `DataHub-Test`. Si encuentra otro nombre, se detiene. Si encuentra artefactos, los lista y permite revisar el estado real antes del despliegue; no los modifica ni los elimina.

| Resultado | Qué revisar |
| --- | --- |
| `Configure the Actions variable...` | Nombre de la variable y formato del GUID completo. |
| `Expected DataHub-Test` | El GUID apunta a otro workspace o el nombre del workspace cambió. |
| `HTTP 401` | Autenticación y aceptación del token por Fabric. |
| `HTTP 403` | Acceso del Service Principal al workspace y configuración del tenant para usar las APIs de Fabric. |
| `HTTP 404` | ID y tenant correctos; un recurso no accesible también puede no estar visible. |
| `HTTP 429` | Límite temporal de solicitudes: esperar y repetir manualmente. |

`READ ACCESS OK` demuestra lectura del workspace y su inventario. No demuestra permisos de escritura, disponibilidad de capacidad, aceptación de los modelos, binding ni refresh. El ID de capacidad se muestra solo como dato informativo. Con este resultado revisaremos los requisitos de publicación y prepararemos la primera ejecución selectiva de Interest Rates en TEST.

## 7. Cómo sabremos que la prueba de publicación funcionó

Antes del despliegue registraremos el inventario de TEST y, si Stocks Index ya existe, su estado inicial. Después comprobaremos:

1. Interest Rates aparece como reporte y como modelo semántico.
2. El reporte utiliza el modelo de TEST.
3. Stocks Index no aparece si antes no existía; si existía, sus definiciones no se modificaron por esta publicación.
4. Las conexiones de datos están configuradas y el refresh de Interest Rates termina correctamente.
5. El gráfico muestra datos.

Si TEST estaba vacío, esta prueba demuestra exclusión de Stocks Index, pero no demuestra todavía que un ítem existente queda intacto. Para ello estableceremos una base con ambos conjuntos y repetiremos una actualización selectiva de Interest Rates.

## 8. Después de comprobar la publicación

| Etapa | Resultado esperado |
| --- | --- |
| Selección local | Entender exactamente qué dos ítems se publicarían. |
| Publicación en TEST | Comprobar selección, binding y refresh reales. |
| Base con ambos conjuntos | Cambiar Interest Rates y verificar que Stocks Index permanece intacto. |
| Ramas `dev` y `main` (ya configuradas) | DEV sincroniza `dev`; `main` prepara candidatos de release. |
| Tag y SHA | Identificar una versión concreta de los archivos. |
| GitHub Actions (autenticación comprobada) | Comprobar acceso a TEST con el workflow 02 y luego incorporar el despliegue manual. |
| Aprobación y PROD de laboratorio | Publicar el mismo candidato probado, con autorización. |

Un commit registra una versión; su SHA la identifica. Una rama puede avanzar a nuevos commits. Un tag asigna un nombre a un commit. En la opción 2, `dev` integra trabajo y `main` prepara releases; una versión seleccionada se despliega primero a TEST y después a PROD. [Opción 2 de Microsoft](https://learn.microsoft.com/en-us/fabric/cicd/manage-deployment#option-2---definition-based-deployments-from-a-shared-release-commit).

El usuario creó `dev` desde `main` y conectó `DataHub-Dev` a `dev` en `/DataHub`. Antes de la primera publicación, el usuario comprobará la rama y versión locales elegidas para la prueba. El script local publica los archivos presentes en disco: todavía no garantiza una versión inmutable ni sustituye el futuro manifiesto de release.
