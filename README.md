# Descargador de archivos de TTS desde la URL del Workshop 

Este script en Python permite descargan los archivos de un mod del Workshop de Tabletop Simulator dada la URL del Workshop un directorio dado por el nombre del mod o desde un archivo JSON de Tabletop Simulator

**Creditos** Telegram @hinakawa y @alemarfar

## Caracteristicas
- Lee el ID desde el Workshop de TTS especificado por el usuario
- Realiza la conversion a archivo obteniendo los campo de datos terminados en URL y su url
- Realiza reemplazo de las url con las URLs validas para descargar
- Verifica que sean URLs unicas
- Detecta extensiones de los archivos segun su cabecera descargada y le asiga el MIME Type correspondiente
  a los correspondientes a TTS
- Descarga las URLs indicando nombre del campo de datos utilizando el metodo HTTP GET a un directorio con el nombre del mod o a uno especificado por el usuario si ya existe
- Identifica la extension del archivo identificando la cabecera leyendo los primeros 4096 bytes del archivo y comparandolos con archivos conocidos de TTS
- Simula un navegador para los sitios de hosting de imagenes y reintenta la descarga de archivos si esta falla
- Guarda automaticamente las URLs reemplazadas en un archivo TXT
- Entrega la opcion de descragar desde el archivo JSON si se posee 
- Verifica que la libreria request este instalada al ejecutar el script


## Requisitos
- **Python**: Versión 3.6 o superior.
- **Librería `requests`**:
```bash
 pip install requests
```
   


