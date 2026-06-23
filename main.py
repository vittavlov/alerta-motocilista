import os
import time
import threading
import sqlite3
import urllib.request
import urllib.parse
import telebot
from dotenv import load_dotenv
import schedule

# Carrega as chaves do api.env
load_dotenv("api.env")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Inicializa o bot do Telegram
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Importa as suas lógicas dos outros arquivos
from clima   import buscar_clima, buscar_alertas_inmet
from alertas import analisar_risco, NivelRisco

INTERVALO_MINUTOS = 30
ALERTAS_NOTIFICADOS_INMET = set()

# Dicionário temporário para saber quem está na fase de digitação de cidades
ESTADOS_USUARIOS = {}

# --- BANCO DE DADOS (PostgreSQL / Supabase) ---
import psycopg2

def conectar_banco():
    """Conecta ao banco de dados PostgreSQL no Supabase usando a URL de conexão."""
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    # Cria a tabela na nuvem se ela ainda não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            chat_id BIGINT,
            nome TEXT,
            cidade TEXT,
            PRIMARY KEY (chat_id, city)
        )
    """)
    # Fallback caso dê erro de sintaxe por conta do nome da coluna
    try:
        conn.commit()
    except:
        conn.rollback()
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
        try:
            cursor.execute("""
                INSERT INTO usuarios (chat_id, nome, city) 
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, city) DO NOTHING
            """, (chat_id, nome, cidade.lower()))
        except:
            conn.rollback()
            cursor.execute("""
                INSERT INTO usuarios (chat_id, nome, cidade) 
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, cidade) DO NOTHING
            """, (chat_id, nome, cidade.lower()))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def listar_usuarios():
    conn, cursor = conectar_banco()
    try:
        cursor.execute("SELECT chat_id, nome, city FROM usuarios")
    except:
        cursor.execute("SELECT chat_id, nome, cidade FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()
    conn.close()
    return usuarios

# --- ROTINA DE NOTIFICAÇÃO ---
def enviar_mensagem_direta(chat_id, texto):
    try:
        texto_codificado = urllib.parse.quote(texto)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={chat_id}&text={texto_codificado}"
        with urllib.request.urlopen(url) as response:
            return response.read()
    except Exception as e:
        print(f"Erro ao enviar para {chat_id}: {e}")

# --- FLUXO DO BOT DO TELEGRAM ---

@bot.message_handler(commands=['start'])
def comando_start(mensagem):
    chat_id = mensagem.chat.id
    nome = mensagem.from_user.first_name
    
    ESTADOS_USUARIOS[chat_id] = "aguardando_cidade"
    
    resposta = (
        f"🏍️ Olá, {nome}! Bem-vindo ao Alerta Motociclista.\n\n"
        f"Por favor, digite o nome da **primeira cidade** que você deseja monitorar:"
    )
    bot.send_message(chat_id, resposta, parse_mode="Markdown")

@bot.message_handler(commands=['sair'])
def comando_sair(mensagem):
    chat_id = mensagem.chat.id
    nome = message_id = mensagem.from_user.first_name
    
    conn, cursor = conectar_banco()
    try:
        cursor.execute("DELETE FROM usuarios WHERE chat_id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()
        
    ESTADOS_USUARIOS.pop(chat_id, None)
    
    resposta = (
        f"👋 Até logo, {nome}!\n"
        f"Seu cadastro e cidades foram removidos com sucesso. Você não receberá mais alertas.\n\n"
        f"Quando quiser retornar, basta enviar um novo **/start**!"
    )
    bot.send_message(chat_id, resposta, parse_mode="Markdown")
    print(f"❌ Usuário removido do sistema: {nome} ({chat_id})")

@bot.message_handler(func=lambda msg: ESTADOS_USUARIOS.get(msg.chat.id) == "aguardando_cidade")
def capturar_cidades_sequenciais(mensagem):
    chat_id = mensagem.chat.id
    nome = mensagem.from_user.first_name
    texto_digitado = mensagem.text.strip()
    
    # Ignora se o cara sem querer digitou o comando /sair na hora de escolher a cidade
    if texto_digitado.startswith('/'):
        return

    if texto_digitado.lower() == "ok":
        ESTADOS_USUARIOS.pop(chat_id, None)
        resposta = (
            f"✅ Tudo pronto, {nome}!\n"
            f"O cadastro das suas cidades foi finalizado com sucesso. ALERTA ATIVADO!\n\n"
            f"Caso queira cancelar o serviço a qualquer momento, basta digitar **/sair** aqui no chat.\n\n"
            f"Boa pilotagem! 🏍️💨"
        )
        bot.send_message(chat_id, resposta, parse_mode="Markdown")
        return

    try:
        buscar_clima(texto_digitado, "BR")
        salvar_cidade_usuario(chat_id, nome, texto_digitado)
        
        resposta = (
            f"📍 Cidade **{texto_digitado.title()}** adicionada!\n\n"
            f"• Quer monitorar mais alguma? Digite o nome da próxima.\n"
            f"• Se já terminou, basta digitar **`ok`**."
        )
        bot.send_message(chat_id, resposta, parse_mode="Markdown")
        print(f"💾 Cidade vinculada: {nome} -> {texto_digitado}")
        
    except Exception:
        bot.send_message(chat_id, "⚠️ Não encontrei essa cidade. Verifique se digitou o nome correto e tente novamente:")

# --- MOTOR DE MONITORAMENTO DE CLIMA ---

def verificar_seguranca_geral():
    global ALERTAS_NOTIFICADOS_INMET
    usuarios = listar_usuarios()
    if not usuarios:
        return

    print(f"\n🛰️ [RODADA DE MONITORAMENTO] Checando clima...")

    # 1. ALERTAS INMET
    try:
        avisos_inmet = buscar_alertas_inmet("PE")
        if avisos_inmet and isinstance(avisos_inmet, list):
            for aviso in avisos_inmet:
                severidade = aviso['severidade'].lower()
                texto_completo = (aviso['titulo'] + " " + aviso.get('descricao', '')).lower()
                termos_perigo = ['chuva', 'tempestade', 'vento', 'vendaval', 'granizo', 'acumulado', 'nublado']
                afeta_moto = any(termo in texto_completo for termo in termos_perigo)
                
                if severidade in ['perigo', 'grande perigo'] and afeta_moto:
                    id_alerta = aviso.get('id', aviso['titulo'])
                    if id_alerta not in ALERTAS_NOTIFICADOS_INMET:
                        msg_inmet = (
                            f"🚨 [ALERTA URGENTE INMET]\n"
                            f"📌 {aviso['titulo']}\n"
                            f"⚠️ Severidade: {aviso['severidade']}\n"
                            f"📅 Período: {aviso['inicio']} até {aviso['fim']}"
                        )
                        enviados = set()
                        for u in usuarios:
                            if u[0] not in enviados:
                                enviar_mensagem_direta(u[0], msg_inmet)
                                enviados.add(u[0])
                        ALERTAS_NOTIFICADOS_INMET.add(id_alerta)
    except Exception as e:
        print(f"Erro no INMET: {e}")

    # 2. ALERTAS INDIVIDUAIS POR CIDADE
    for chat_id, nome, cidade in usuarios:
        try:
            dados = buscar_clima(cidade, "BR")
            alertas = analisar_risco(dados)
            
            alertas_importantes = [a for a in alertas if a.nivel != NivelRisco.SEGURO]
            
            for alerta in alertas_importantes:
                msg_clima = (
                    f"{alerta.nivel.value} - {alerta.tipo} em {cidade.title()}\n"
                    f"📋 {alerta.mensagem}"
                )
                enviar_mensagem_direta(chat_id, msg_clima)
        except Exception as e:
            print(f"Erro ao checar cidade {cidade} do usuário {nome}: {e}")

def rodar_agendador():
    verificar_seguranca_geral()
    schedule.every(INTERVALO_MINUTOS).minutes.do(verificar_seguranca_geral)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    conectar_banco()
    
    thread_clima = threading.Thread(target=rodar_agendador, daemon=True)
    thread_clima.start()
    
    print("🛰️ SISTEMA ATIVO!")
    print("🤖 Bot completo com comandos /start e /sair online...")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\nDesligando o sistema...")