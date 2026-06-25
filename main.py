import os
import time
import threading
import urllib.request
import urllib.parse
import telebot
from dotenv import load_dotenv
import schedule

load_dotenv("api.env")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

from clima import buscar_clima, buscar_alertas_inmet_brasil
from alertas import analisar_risco, NivelRisco
import psycopg2

INTERVALO_MINUTOS = 30
ALERTAS_NOTIFICADOS_INMET = set()
ESTADOS_USUARIOS = {}

# --- BANCO DE DADOS ---

def conectar_banco():
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            chat_id BIGINT,
            nome TEXT,
            cidade TEXT,
            PRIMARY KEY (chat_id, cidade)
        )
    """)
    conn.commit()
    return conn, cursor

def salvar_cidade_usuario(chat_id, nome, cidade):
    conn, cursor = conectar_banco()
    try:
        cursor.execute("""
            INSERT INTO usuarios (chat_id, nome, cidade)
            VALUES (%s, %s, %s)
            ON CONFLICT (chat_id, cidade) DO NOTHING
        """, (chat_id, nome, cidade.lower()))
        conn.commit()
    except Exception as e:
        print(f"Erro ao salvar cidade: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def listar_usuarios():
    conn, cursor = conectar_banco()
    try:
        cursor.execute("SELECT chat_id, nome, cidade FROM usuarios")
        usuarios = cursor.fetchall()
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        usuarios = []
    finally:
        cursor.close()
        conn.close()
    return usuarios

# --- ENVIO DE MENSAGEM ---

def enviar_mensagem_direta(chat_id, texto):
    try:
        texto_codificado = urllib.parse.quote(texto)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={chat_id}&text={texto_codificado}"
        with urllib.request.urlopen(url) as response:
            return response.read()
    except Exception as e:
        print(f"Erro ao enviar para {chat_id}: {e}")

# --- COMANDOS DO BOT ---

@bot.message_handler(commands=['start'])
def comando_start(mensagem):
    chat_id = mensagem.chat.id
    nome = mensagem.from_user.first_name
    ESTADOS_USUARIOS[chat_id] = "aguardando_cidade"
    resposta = (
        f"🏍️ Olá, {nome}! Bem-vindo ao Alerta Motociclista.\n\n"
        f"Digite o nome da primeira cidade que deseja monitorar:"
    )
    bot.send_message(chat_id, resposta)

@bot.message_handler(commands=['sair'])
def comando_sair(mensagem):
    chat_id = mensagem.chat.id
    nome = mensagem.from_user.first_name
    conn, cursor = conectar_banco()
    try:
        cursor.execute("DELETE FROM usuarios WHERE chat_id = %s", (chat_id,))
        conn.commit()
    except Exception as e:
        print(f"Erro ao deletar usuário: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    ESTADOS_USUARIOS.pop(chat_id, None)
    bot.send_message(chat_id, f"👋 Até logo, {nome}! Você foi removido do sistema.\n\nPara voltar, envie /start.")

@bot.message_handler(func=lambda msg: ESTADOS_USUARIOS.get(msg.chat.id) == "aguardando_cidade")
def capturar_cidades(mensagem):
    chat_id = mensagem.chat.id
    nome = mensagem.from_user.first_name
    texto = mensagem.text.strip()

    if texto.startswith('/'):
        return

    if texto.lower() == "ok":
        ESTADOS_USUARIOS.pop(chat_id, None)
        bot.send_message(chat_id, f"✅ Cadastro finalizado! Alerta ativado, {nome}!\n\nBoa pilotagem! 🏍️💨")
        return

    try:
        buscar_clima(texto, "BR")
        salvar_cidade_usuario(chat_id, nome, texto)
        bot.send_message(chat_id,
            f"📍 {texto.title()} adicionada!\n\n"
            f"• Quer monitorar mais alguma? Digite o nome.\n"
            f"• Se terminou, digite ok"
        )
    except Exception:
        bot.send_message(chat_id, "⚠️ Cidade não encontrada. Tente novamente:")

# --- MONITORAMENTO ---

def verificar_seguranca_geral():
    global ALERTAS_NOTIFICADOS_INMET
    usuarios = listar_usuarios()
    if not usuarios:
        return

    print(f"\n🛰️ Checando clima...")

    # Alertas INMET
    try:
        avisos_inmet = buscar_alertas_inmet_brasil()
        if avisos_inmet and isinstance(avisos_inmet, list):
            for aviso in avisos_inmet:
                texto_completo = (aviso['titulo'] + " " + aviso.get('descricao', '')).lower()
                termos_perigo = ['chuva', 'tempestade', 'vento', 'vendaval', 'granizo']
                if any(termo in texto_completo for termo in termos_perigo):
                    cidades_afetadas = aviso.get('cidades', [])
                    id_alerta = aviso.get('id', aviso['titulo'])
                    for u in usuarios:
                        chat_id = u[0]
                        cidade_usuario = u[2].lower().strip()
                        if cidade_usuario in cidades_afetadas:
                            chave = f"{id_alerta}_{chat_id}"
                            if chave not in ALERTAS_NOTIFICADOS_INMET:
                                msg = (
                                    f"🚨 ALERTA INMET - {u[2].upper()}\n"
                                    f"📌 {aviso['titulo']}\n"
                                    f"⚠️ Grau: {aviso['severidade']}\n"
                                    f"📅 {aviso['inicio']} até {aviso['fim']}"
                                )
                                enviar_mensagem_direta(chat_id, msg)
                                ALERTAS_NOTIFICADOS_INMET.add(chave)
    except Exception as e:
        print(f"Erro no INMET: {e}")

    # Alertas por cidade
    for chat_id, nome, cidade in usuarios:
        try:
            dados = buscar_clima(cidade, "BR")
            alertas = analisar_risco(dados)
            alertas_importantes = [a for a in alertas if a.nivel != NivelRisco.SEGURO]
            for alerta in alertas_importantes:
                msg = (
                    f"{alerta.nivel.value} - {alerta.tipo} em {cidade.title()}\n"
                    f"📋 {alerta.mensagem}"
                )
                enviar_mensagem_direta(chat_id, msg)
        except Exception as e:
            print(f"Erro ao checar {cidade}: {e}")

def rodar_agendador():
    verificar_seguranca_geral()
    schedule.every(INTERVALO_MINUTOS).minutes.do(verificar_seguranca_geral)
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- INÍCIO ---

if __name__ == "__main__":
    print("🗄️ Conectando ao banco...")
    conectar_banco()

    print("📅 Iniciando agendador em background...")
    thread_clima = threading.Thread(target=rodar_agendador, daemon=True)
    thread_clima.start()

    print("🤖 Bot iniciado em modo polling...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
