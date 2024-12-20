import requests
import os
import certifi
import pandas as pd
import urllib3
import openai
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

urllib3.disable_warnings()

# Configura tu clave API
openai.api_key = "" #clave de openiaKEY

#ingresar los datos del usuario

cuil = 20960087888
edad = 35
salario_actual = 3000000
credito_pedido = 100000
email = "" #email del destinatario / usuario de la consulta

email_respuesta = "" #colocar el email que sera el remitente del usuario para dar respuesta sobre el credito
clave_respuesta = "" #colocar la clave del email remitente 

#Con el cuil, se obtiene la informacion del BCRA para obtener el historial crediticio del usuario

api_url = f"https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/Historicas/{cuil}"


response = requests.get(api_url, verify=False)


data = response.json()

results = data.get("results", {})

# Procesar los períodos y entidades
periods = []
for period in results.get("periodos", []):
    periodo = period.get("periodo")
    for entidad in period.get("entidades", []):
        entidad_info = {
            "Periodo": periodo,
            "Entidad": entidad.get("entidad"),
            "Situación": entidad.get("situacion"),
            "Monto": entidad.get("monto"),
            "En Revisión": entidad.get("enRevision"),
            "Proceso Judicial": entidad.get("procesoJud"),
        }
        periods.append(entidad_info)

# Crear un DataFrame
df = pd.DataFrame(periods)
df['monto_'] = df["Monto"] * 1000

df = df[['Periodo', 'Entidad','Situación','monto_','En Revisión','Proceso Judicial']]

df = df.rename(columns={'monto_': 'Monto'})


# Función para calcular el score crediticio
def calcular_score_crediticio(df):
    # Criterios del score
    total_puntaje = 100
    historial_pagos_peso = 35
    utilizacion_credito_peso = 30
    duracion_historial_peso = 15
    diversidad_crediticia_peso = 10
    consultas_recientes_peso = 10

    # 1. Historial de pagos (35%)
    pagos_puntuales = df["Situación"].sum()
    total_pagos = len(df)
    historial_pagos_score = (pagos_puntuales / total_pagos) * historial_pagos_peso

    # 2. Utilización de crédito (30%)
    monto_total = df["Monto"].sum()
    utilizacion_credito_score = 0
    if monto_total > 0:  # Si hay actividad crediticia
        utilizacion_credito_score = (0.8) * utilizacion_credito_peso  # Asumimos uso moderado (~80%)

    # 3. Duración del historial (15%)
    meses_historial = len(df["Periodo"].unique())
    duracion_historial_score = (meses_historial / 12) * duracion_historial_peso  # Normalizamos a 12 meses

    # 4. Diversidad crediticia (10%)
    entidades_unicas = len(df["Entidad"].unique())
    diversidad_crediticia_score = (entidades_unicas / 5) * diversidad_crediticia_peso  # Asumimos máximo 5 entidades

    # 5. Consultas recientes (10%)
    consultas_recientes_score = consultas_recientes_peso  # Asumimos sin consultas recientes

    # Calcular puntaje total
    score_total = (
        historial_pagos_score +
        utilizacion_credito_score +
        duracion_historial_score +
        diversidad_crediticia_score +
        consultas_recientes_score
    )

    return round(score_total, 2)

# Calcular el score
score = calcular_score_crediticio(df)
score_total = f"El score crediticio del cliente es: {score}"

def calcular_deuda_actual(df):
    # Filtrar los registros más recientes (Periodo máximo)
    periodo_actual = df["Periodo"].max()
    deuda_actual = df[df["Periodo"] == periodo_actual]["Monto"].sum()
    return deuda_actual

# Calcular la deuda actual
deuda = calcular_deuda_actual(df)
deuda_total = f"La deuda actual del cliente es: ${deuda}"

def calcular_retrasos(df):
    # Obtener el periodo más reciente
    periodo_actual = df["Periodo"].max()
    
    # Calcular los últimos 6 periodos
    ultimos_seis_periodos = sorted(df["Periodo"].unique(), reverse=True)[:8]
    
    # Filtrar los datos para los últimos 6 periodos
    df_seis_meses = df[df["Periodo"].isin(ultimos_seis_periodos)]
    
    # Contar los retrasos (donde Situación no es igual a 1)
    retrasos = df_seis_meses[df_seis_meses["Situación"] != 1]
    
    # Retornar el número total de retrasos y los detalles
    return {
        "total_retrasos": len(retrasos)
    }

# Calcular los retrasos
resultado = calcular_retrasos(df)
retrasos_total = f"Total de retrasos en los últimos 8 meses: {resultado['total_retrasos']}"


def calcular_riesgo_crediticio(datos_usuario):

    # Prompt inicial para configurar al asistente como experto
    prompt = f"""Actúa como un experto en análisis de riesgo crediticio. Evalúa la información proporcionada y determina si el usuario es apto para un crédito de ${credito_pedido}. Considera el nivel de riesgo (bajo, medio, alto) y aplica la regla: si no tiene score crediticio, no se le puede otorgar el crédito.

Información del usuario: {datos_usuario}

Responde de forma profesional, precisa y concisa en máximo 60 palabras, indicando claramente si es apto o no para el crédito.


    
    """
    try:
        # Solicitud a la API con el modelo adecuado para chat
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,  
            temperature=0.1
        )
        
        # Extraer el texto de la respuesta
        return respuesta.choices[0].message['content'].strip()
    except Exception as e:
        return f"Error al conectar con la API: {e}"


def respuesta_cliente(respuesta):

    # Prompt inicial para configurar al asistente como experto
    prompt = f"""De acuerdo a esta informacion: {respuesta}. haz un promp donde indique al cliente si es o no acto para el credito solicitado, Responde de forma profesional, precisa y concisa en máximo 60 palabra.
    """
    try:
        # Solicitud a la API con el modelo adecuado para chat
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,  
            temperature=0.1
        )
        
        # Extraer el texto de la respuesta
        return respuesta.choices[0].message['content'].strip()
    except Exception as e:
        return f"Error al conectar con la API: {e}"

#Funciòn de envio de email


def envio_email(email_remitente, email_password, email_destinatario, asunto, cuerpo_mail):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    mensaje = MIMEMultipart()
    mensaje['From'] = email_remitente
    mensaje['To'] = email_destinatario
    mensaje['Subject'] = asunto
    cuerpo_mensaje = cuerpo_mail
    mensaje.attach(MIMEText(cuerpo_mensaje, 'plain'))

    try:
        servidor = smtplib.SMTP(smtp_server, smtp_port)
        servidor.starttls()  
        servidor.login(email_remitente, email_password)  
        texto_mensaje = mensaje.as_string()  
        servidor.sendmail(email_remitente, email_destinatario, texto_mensaje)  
        servidor.quit()  
        print("Correo enviado correctamente.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")



def respuesta_color(color):

    # Prompt inicial para configurar al asistente como experto
    prompt = f"""Determinar si la frase es positiva o negativa: {color}. si es positiva indicar la palabra "SI" en caso contario decir "NO".
    """
    try:
        # Solicitud a la API con el modelo adecuado para chat
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,  
            temperature=0.1
        )
        
        # Extraer el texto de la respuesta
        return respuesta.choices[0].message['content'].strip()
    except Exception as e:
        return f"Error al conectar con la API: {e}"
    
def generar_imagen(prompt):

    try:
        respuesta = openai.Image.create(
            prompt=prompt,
            n=1,  
            size="1024x1024" 
        )
        # Extraer la URL de la imagen generada
        url_imagen = respuesta['data'][0]['url']
        return url_imagen
    except Exception as e:
        print(f"Error al generar la imagen: {e}")
        return None


    # Información del usuario para evaluar
datos = f"""
    Edad: {edad} años,
    Ingresos mensuales: ${salario_actual},
    {deuda_total},
    {retrasos_total},
    {score_total}
    """

resultado = calcular_riesgo_crediticio(datos)
respuesta = respuesta_cliente(resultado)
color = respuesta_color(respuesta)

#funcion para enviar el mail con la respuesta de la IA


if color == 'NO':
    prompt = "Genera una imagen de color rojo."
    url = generar_imagen(prompt)
    envio_email(email_respuesta,clave_respuesta,email,f"Solicitud de prestamo",f"{respuesta}, {url}")
elif color == 'SI':
    prompt = "Genera una imagen de color verde."
    url = generar_imagen(prompt)
    envio_email(email_respuesta,clave_respuesta,email,f"Solicitud de prestamo",f"{respuesta}, {url}")
