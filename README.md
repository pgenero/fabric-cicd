# Laboratorio Fabric CI/CD: DataHub

Este repositorio contiene el laboratorio de la opción 2: preparar una versión en Git, probarla en TEST y publicar esa misma versión en PROD después de una aprobación.

La primera prueba de **Interest Rates y su modelo en TEST** quedó validada por el usuario: inventario de dos ítems, binding a TEST, refresh y reporte correctos. El refresh requirió tomar ownership y asignar manualmente una conexión existente; automatizar esa configuración queda para una fase posterior. El paso actual es preparar una base con ambos conjuntos en TEST (sección 9). Todavía no implementamos releases, aprobación ni despliegue a producción.

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
- `DataHub-Test` y `DataHub-Prod` no tienen conexión Git. TEST comenzó vacío y ahora contiene el reporte y modelo de Interest Rates; PROD continúa vacío según el último estado informado.
- El Service Principal `PBI_ServicePrincipal` tiene rol Admin en los tres workspaces, confirmado por el usuario el 2026-10-28.
- `main` y `dev` tienen los mismos workflows y código base de tareas, según confirmó el usuario.

El workflow 02 confirmó DataHub-Test con ID `9b918b42-1d3d-4ae3-97fb-89d061ad1f40`, inventario vacío y capacidad asignada con ID `2db82b68-be75-4ed0-bbdf-57d719aa53e6`. El primer intento devolvió 403 porque faltaba agregar el Service Principal al workspace; el usuario lo agregó y la segunda ejecución fue exitosa. Esto prueba lectura, no escritura ni disponibilidad de la capacidad para desplegar.

El ID del workspace aparece en su URL, por ejemplo `https://app.fabric.microsoft.com/groups/<workspace-id>/list`. Es un identificador, no una contraseña.

El destino real es el ID indicado. Ahora `deploy_test.py --deploy` solo acepta el GUID de TEST confirmado arriba; un ID diferente o ausente detiene el programa antes de autenticarse. Es una restricción de este laboratorio, que revisaremos al preparar el despliegue a PROD.

## 5. Autenticación desde GitHub Actions (completada)

El usuario ejecutó el workflow 01 y obtuvo `AUTH OK`. La automatización ya está también en `dev`. No es necesario repetir esta prueba ahora; el paso actual está en la sección 9.

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

## 6. Acceso de lectura a TEST (completado)

El usuario ejecutó el workflow 02 y obtuvo `READ ACCESS OK` e `Items found: 0`. Las instrucciones siguientes quedan como referencia para repetir el diagnóstico.

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

## 7. Primera publicación en TEST (ejecutada; binding confirmado)

El 2026-10-28 el usuario informó que el workflow 03 terminó correctamente. La captura de linaje muestra `Interest Rates.SemanticModel` en DataHub-Test conectado a `Interest Rates.Report` en DataHub-Test. El usuario confirmó después el inventario, el refresh y el gráfico; la intervención sobre ownership y conexión queda registrada en la sección 8.

La primera ejecución se realizó con el nombre **03 - Publicar Interest Rates en TEST** y selección fija de Interest Rates. Ahora el mismo archivo de workflow se muestra como **03 - Publicar seleccion en TEST** y permite elegir uno de los dos pares. Publica desde los archivos del repositorio; no copia el contenido vivo de DEV. Esta sección describe la primera prueba, con `solution=interest-rates`.

Es una operación automatizada con inicio manual: vos presionás Run workflow y GitHub ejecuta los pasos. Más adelante incorporaremos selección de release, aprobación y promoción del mismo candidato a PROD.

### Antes de ejecutarlo

1. En **DataHub-Test → Manage access**, comprobar que el Service Principal tenga rol **Contributor**, **Member** o **Admin**. Viewer alcanza para el workflow 02, pero no para crear reportes y modelos. No hace falta elevar Contributor a Admin para esta prueba.
2. Conservar el Secret `AZURE_CREDENTIALS` y la Variable `FABRIC_TEST_WORKSPACE_ID`. Ya funcionaron en el workflow 02.
3. Revisar e incorporar a `dev` el nuevo archivo `.github/workflows/deploy-interest-rates-test.yml`, el cambio en `scripts/deploy_test.py` y este README. Luego llevarlos a `main` mediante un PR revisado. Los dos conjuntos de artefactos ya existentes deben seguir disponibles en `DataHub`; no hace falta modificarlos para esta prueba.
4. Para repetir esa primera prueba con el workflow actual, abrir **Actions → 03 - Publicar seleccion en TEST → Run workflow**, elegir **main** y `solution=interest-rates`. Esto creará o actualizará el par en TEST. Para el paso actual, seguir la sección 9 y seleccionar `stocks-index`.

No hay que ejecutar PowerShell. La conexión DEV–`dev` y la ausencia de conexión Git en TEST/PROD se mantienen.

### Qué hace el workflow

1. Exige `main` como rama de ejecución y registra su commit SHA, el identificador de esa versión. Descarga ese SHA concreto aunque la rama avance durante la corrida.
2. Comprueba los archivos locales y muestra el par seleccionado.
3. Consulta DataHub-Test y registra el inventario previo. Si falla esta consulta, no continúa a publicar.
4. Llama a `fabric-cicd==1.4.0` con `items_to_include` limitado a `Interest Rates.SemanticModel` e `Interest Rates.Report`. Esta selección usa la funcionalidad experimental documentada en la sección 3.
5. Consulta el inventario posterior. Esperamos dos ítems: el modelo y el reporte de Interest Rates. Este paso lista el resultado; la comprobación funcional se hace abajo.

El workflow evita dos publicaciones simultáneas de este workflow en TEST y no cancela una publicación en curso cuando se solicita otra. No ejecuta eliminación de huérfanos ni refresh.

Para este par no necesitamos `parameter.yml`: el reporte referencia su modelo mediante `byPath`, y la librería resuelve el vínculo durante el despliegue. La conexión del modelo con FRED y sus credenciales son otro asunto; se comprueban al cargar datos.

### Qué revisar y compartir después

- El resultado del paso de publicación, ahora llamado **Publicar exclusivamente el par seleccionado**.
- La salida de **Consultar inventario despues de publicar**. Si TEST seguía vacío, esperamos `Items found: 2` y ningún Stocks Index.
- En Fabric, abrir **DataHub-Test → Lineage / Linaje** y verificar que Interest Rates utiliza el modelo del mismo workspace. Registrar los IDs de ambos ítems de TEST; no deben confundirse con los de DEV.

Después revisaremos las conexiones del modelo y su refresh. Un workflow verde demuestra que finalizaron sus operaciones; todavía no demuestra que el gráfico tenga datos. Si falla durante la publicación, puede haber quedado creado el modelo aunque no el reporte: no existe rollback automático. Compartir el paso y el error antes de repetir o borrar contenido.

El SHA queda registrado para trazabilidad de esta corrida. Todavía falta formalizar el candidato de release (SHA, selección y configuración), fijar dependencias y promover ese mismo candidato a PROD. No presentaremos esta primera publicación como la implementación completa de Option 2.

## 8. Datos y visualización en TEST (validados con configuración manual)

El usuario confirmó el inventario de únicamente Interest Rates (reporte y modelo), el refresh exitoso y el reporte correcto. El modelo recién publicado tenía ownership de `PBI_ServicePrincipal` y mostraba una Personal Cloud Connection. Según la comprobación del usuario, esa configuración impedía el refresh. El usuario tomó control del modelo y lo asignó a una conexión ya existente para el origen; después el refresh y el reporte funcionaron.

Por tanto, no registramos el refresh como validado bajo ownership del Service Principal ni la configuración de conexiones como automatizada. Se difiere expresamente a una fase posterior: permisos de la conexión, asignación automática al modelo y operación con la identidad de despliegue. No necesitamos resolverlo para continuar la prueba de selección de artefactos.

Las instrucciones siguientes quedan como referencia de la validación realizada.

El modelo usa Import y consulta un CSV de FRED mediante `Web.Contents`. El workflow publica definiciones y no solicita refresh. Para cargar los datos se necesita una actualización del modelo semántico; actualizar la página del navegador no realiza esa operación. [Actualización de datos en Power BI](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data).

### Comprobación manual del usuario

1. En el inventario completo de **DataHub-Test**, comprobar que aparecen únicamente el modelo y el reporte de Interest Rates, sin Stocks Index.
2. En la fila de **Interest Rates de tipo Semantic model**, abrir `…` y elegir **Refresh now / Actualizar ahora**. Si ya ejecutaste un refresh, alcanza con revisar su resultado en el historial.
3. Consultar **Refresh history / Historial de actualizaciones** y esperar a que termine. Registrar si finaliza correctamente o copiar el mensaje del error.
4. Si termina correctamente, abrir el **reporte** Interest Rates y comprobar que el gráfico muestra datos sin errores. El modelo local limita la consulta a fechas concretas (incluye `coed=2026-10-22`); no exigimos que aparezca una observación con la fecha de hoy.

Si aparece un problema de conexión o credenciales, abrir **Semantic model → Settings → Gateway and cloud connections** y revisar también **Data source credentials**, si está disponible. Compartir el mensaje y el estado de la conexión antes de cambiar la configuración. Si la interfaz exige **Take over / Tomar control**, informar ese detalle antes de usarlo: cambiaría el propietario y debemos decidir cómo mantener la operación con el Service Principal. [Conexiones cloud de modelos semánticos](https://learn.microsoft.com/en-us/power-bi/connect-data/service-connect-cloud-data-sources).

El secreto `AZURE_CREDENTIALS` autentica la aplicación que publica en Fabric; no es una credencial para el sitio FRED. Si falta una conexión del modelo al origen, la trataremos como configuración del entorno y documentaremos cómo automatizar su asociación. La verificación manual actual no sustituye ese objetivo de automatización.

No hace falta volver a ejecutar el workflow 03 ni hacer cambios de reportes para esta comprobación. El único cambio local de esta etapa es este README, que el usuario puede versionar con su operación habitual.

### Criterios de cierre de la primera prueba

1. Interest Rates aparece como reporte y como modelo semántico (confirmado).
2. El reporte utiliza el modelo de TEST (confirmado por linaje).
3. Stocks Index no aparece en TEST (confirmado; antes no existía).
4. El refresh de Interest Rates termina correctamente después de configurar la conexión y cambiar ownership manualmente (confirmado).
5. El gráfico muestra datos (confirmado).

Si TEST estaba vacío, esta prueba demuestra exclusión de Stocks Index, pero no demuestra todavía que un ítem existente queda intacto. Para ello estableceremos una base con ambos conjuntos y repetiremos una actualización selectiva de Interest Rates.

## 9. Paso actual: preparar la base con ambos conjuntos

Ya demostramos que se puede publicar un par y excluir el otro en un workspace vacío. Ahora necesitamos que ambos existan en TEST para probar una actualización selectiva sobre contenido existente.

El workflow 03 agrega un selector `solution` con dos opciones. El script de Python ya soportaba ambas; no se modifica en esta etapa.

| Valor de `solution` | Artefactos seleccionados |
| --- | --- |
| `interest-rates` | Interest Rates.SemanticModel y Interest Rates.Report |
| `stocks-index` | Stocks Index.SemanticModel y Stocks Index.Report |

Solo se puede seleccionar un par por ejecución. La selección se registra junto al SHA. No hay opción de publicar todos los ítems ni se ejecuta eliminación de huérfanos. El archivo mantiene el nombre `deploy-interest-rates-test.yml` para conservar el workflow existente; su nombre visible en Actions pasa a ser **03 - Publicar seleccion en TEST**.

### Qué debe hacer el usuario ahora

1. Incorporar a `dev` y después a `main`, mediante el procedimiento Git habitual, los cambios de `.github/workflows/deploy-interest-rates-test.yml` y este README. No hay cambios nuevos en el script ni en `DataHub` para esta etapa.
2. Abrir **Actions → 03 - Publicar seleccion en TEST → Run workflow**. Elegir rama **main** y cambiar explícitamente `solution` a **stocks-index**; el valor predeterminado sigue siendo `interest-rates`.
3. Ejecutar y comprobar que **Revisar seleccion local** muestra solo `Stocks Index.SemanticModel` y `Stocks Index.Report`.
4. Revisar el inventario posterior: esperamos **cuatro artefactos**, dos de Interest Rates y dos de Stocks Index. Guardar la salida con los nombres e IDs y el SHA de esta corrida.
5. Revisar el linaje de Stocks Index: su reporte debe apuntar al modelo de TEST. Comprobar también que Interest Rates sigue abriendo y mostrando sus datos.

Esta publicación no selecciona Interest Rates. No hace falta configurar todavía el refresh de Stocks Index para establecer una base de sus definiciones; si luego queremos comparar su gráfico, primero cargaremos sus datos. La automatización de conexiones sigue pendiente como acordamos.

### Prueba posterior, cuando la base esté confirmada

Registraremos una referencia de las definiciones de Stocks Index en TEST antes de modificar Interest Rates. Prepararemos un cambio visible en Interest Rates, lo llevaremos por `dev` y `main`, y publicaremos solo `interest-rates`. Compararemos las definiciones de Stocks Index antes y después; contar cuatro ítems o conservar los mismos IDs no basta para demostrar que no hubo cambios. También revisaremos el comportamiento de ownership y conexiones de Interest Rates al actualizarlo, sin asumir que se conserva o se restablece automáticamente.

La comprobación de esta base todavía no demuestra por sí sola la actualización selectiva ni la promoción de una release a PROD. Es el requisito para realizar esa prueba con evidencia.

## 10. Próximas etapas

| Etapa | Resultado esperado |
| --- | --- |
| Selección local | Entender exactamente qué dos ítems se publicarían. |
| Publicación en TEST (validada) | Inventario, binding y reporte correctos; refresh validado después de configurar conexión y ownership manualmente. |
| Base con ambos conjuntos | Cambiar Interest Rates y verificar que Stocks Index permanece intacto. |
| Ramas `dev` y `main` (ya configuradas) | DEV sincroniza `dev`; `main` prepara candidatos de release. |
| Tag y SHA | Identificar una versión concreta de los archivos. |
| Conexiones y ownership (diferido) | Automatizar la asignación de conexión y validar refresh con la identidad prevista para operar el modelo. |
| GitHub Actions (primera publicación ejecutada) | Mantener ejecuciones manuales del usuario mientras construimos la automatización. |
| Aprobación y PROD de laboratorio | Publicar el mismo candidato probado, con autorización. |

Un commit registra una versión; su SHA la identifica. Una rama puede avanzar a nuevos commits. Un tag asigna un nombre a un commit. En la opción 2, `dev` integra trabajo y `main` prepara releases; una versión seleccionada se despliega primero a TEST y después a PROD. [Opción 2 de Microsoft](https://learn.microsoft.com/en-us/fabric/cicd/manage-deployment#option-2---definition-based-deployments-from-a-shared-release-commit).

El usuario creó `dev` desde `main` y conectó `DataHub-Dev` a `dev` en `/DataHub`. El workflow 03 descarga y registra el SHA de su ejecución. Invocar el script local directamente publica los archivos presentes en disco. Todavía falta formalizar y promover un mismo candidato con su selección y configuración mediante un manifiesto de release.
