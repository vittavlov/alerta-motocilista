import os
import time
import threading
import sqlite3
import urllib.request
import urllib.parse
import telebot
from dotenv import load_dotenv
import schedule

# Adicione os novos imports do Flask aqui no topo!
from flask import Flask, request

# ... resto das suas configurações (load_dotenv, token, etc.) ...
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# Instancia o Flask já aqui no escopo global
app = Flask(__name__)

# Importa as suas lógicas dos outros arquivos
from clima import buscar_clima, buscar_alertas_inmet_brasil

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
    
    # Cria a tabela garantindo o nome correto da coluna 'cidade'
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

# --- SERVIDOR WEB FALSO (Para evitar o Port Scan Timeout do Render) ---

def rodar_servidor_falso():
    """Apenas abre uma porta HTTP para o Render parar de dar Timeout"""
    porta = int(os.getenv("PORT", 8080))
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot Online")
            
    TCPServer.allow_reuse_address = True
    with TCPServer(("", porta), Handler) as server:
        print(f"🌍 Servidor falso rodando na porta {porta} para o Render.")
        server.serve_forever()

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

# --- MOTOR DE MONITORAMENTO DE CLIMA INMET ---

def verificar_seguranca_geral():
    global ALERTAS_NOTIFICADOS_INMET
    usuarios = listar_usuarios()  # O seu banco deve retornar uma estrutura onde o u[1] é a cidade
    if not usuarios:
        return

    print(f"\n🛰️ [RODADA DE MONITORAMENTO BRASIL] Checando clima...")

    # 1. ALERTAS INMET
    try:
        # Chamamos a nova função do clima.py que busca o Brasil inteiro
        avisos_inmet = buscar_alertas_inmet_brasil() 
        
        if avisos_inmet and isinstance(avisos_inmet, list):
            for aviso in avisos_inmet:
                # Removemos o filtro rígido de severidade para aceitar todos os níveis (incluindo o amarelo)
                texto_completo = (aviso['titulo'] + " " + aviso.get('descricao', '')).lower()
                termos_perigo = ['chuva', 'tempestade', 'vento', 'vendaval', 'granizo', 'acumulado', 'nublado']
                afeta_moto = any(termo in texto_completo for termo in termos_perigo)

                if afeta_moto:
                    # Pegamos a lista de cidades afetadas por este alerta específico
                    cidades_afetadas = aviso.get('cidades', [])
                    id_alerta = aviso.get('id', aviso['titulo'])

                    # Varremos a lista de usuários cadastrados no sistema
                    for u in usuarios:
                        chat_id = u[0]
                        cidade_usuario = u[1].lower().strip()  # Ex: "recife", "são paulo", "jaboatão dos guararapes"

                        # Verificamos se a cidade escolhida por este usuário está dentro do alerta do INMET
                        if cidade_usuario in cidades_afetadas:
                            # Criamos um identificador único por usuário para controlar o envio individual
                            chave_notificacao = f"{id_alerta}_{chat_id}"
                            
                            if chave_notificacao not in ALERTAS_NOTIFICADOS_INMET:
                                msg_inmet = (
                                    f"🚨 [ALERTA INMET - {u[1].upper()}]\n"
                                    f"📌 {aviso['titulo']}\n"
                                    f"⚠️ Grau: {aviso['severidade']}\n"
                                    f"📝 {aviso.get('descricao', 'Atenção redobrada nas pistas.')}\n"
                                    f"📅 Período: {aviso['inicio']} até {aviso['fim']}"
                                )
                                
                                enviar_mensagem_direta(chat_id, msg_inmet)
                                ALERTAS_NOTIFICADOS_INMET.add(chave_notificacao)
                                
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

# --- ADICIONE ESTA FUNÇÃO AUXILIAR LOGO ACIMA DO SEU BlOCO MAIN ---
def inicializar_e_rodar_clima():
    """Roda o agendador de clima de forma totalmente isolada para não travar o bot"""
    try:
        print("🗄️ Inicializando conexão com o banco de dados para o Clima...")
        conectar_banco()
        print("📅 Iniciando agendador de monitoramento de clima...")
        rodar_agendador()
    except Exception as e:
        print(f"💥 Erro crítico ao rodar o agendador de clima/banco: {e}")

from flask import Flask, request
import os
import telebot
import threading

# Instancia o Flask (Ele vai substituir aquele servidor falso antigo)
app = Flask(__name__)

# O Render vai enviar os webhooks para este endereço final
@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def receber_updates():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Incorreto', 403

# Rota simples na raiz para o Render saber que o app está vivo (Health Check)
@app.route('/', methods=['GET'])
def index():
    return "Bot de Clima Operando via Webhook!", 200

def inicializar_e_rodar_clima():
    """Roda o agendador de clima de forma totalmente isolada em background"""
    try:
        print("🗄️ Conectando ao banco de dados...")
        conectar_banco()
        print("📅 Iniciando agendador de monitoramento de clima...")
        rodar_agendador()
    except Exception as e:
        print(f"💥 Erro no agendador de clima: {e}")

if __name__ == "__main__":
    # 1. Dispara a thread do Clima em segundo plano
    thread_clima = threading.Thread(target=inicializar_e_rodar_clima, daemon=True)
    thread_clima.start()

    # 2. Configura o Webhook no Telegram apontando para o seu link do Render
    # O Render gera automaticamente a URL do seu app na variável RENDER_EXTERNAL_URL
    RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
    
    if RENDER_URL:
        # Garante que a URL termine sem barra antes de juntar com o Token
        RENDER_URL = RENDER_URL.rstrip('/')
        WEBHOOK_URL = f"{RENDER_URL}/{TELEGRAM_TOKEN}"
        
        print(f"🧹 Removendo webhooks antigos e configurando novo: {WEBHOOK_URL}")
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
    else:
        print("⚠️ RENDER_EXTERNAL_URL não encontrada. Certifique-se de que está rodando no Render.")

    # 3. Liga o servidor Flask na porta que o Render exige
    PORTA = int(os.getenv("PORT", 8080))
    print(f"🚀 Servidor Webhook ativo de forma nativa na porta {PORTA}!")
    
    # Roda o servidor Flask de forma limpa (substitui o infinity_polling e o servidor falso antigo)
    app.run(host="0.0.0.0", port=PORTA)
