import telebot
import os
from dotenv import load_dotenv

# Carrega as variáveis do seu arquivo de configuração
load_dotenv("api.env")
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Inicializa o bot com o token correto
bot = telebot.TeleBot(TOKEN)

def salvar_novo_usuario(chat_id, nome):
    """Cria o arquivo usuarios.txt e salva o ID de quem interagir com o bot."""
    arquivo_usuarios = "usuarios.txt"
    
    # Evita salvar o mesmo ID mais de uma vez
    if os.path.exists(arquivo_usuarios):
        with open(arquivo_usuarios, "r", encoding="utf-8") as f:
            if str(chat_id) in f.read():
                return
                
    # Adiciona o novo usuário no final do arquivo
    with open(arquivo_usuarios, "a", encoding="utf-8") as f:
        f.write(f"{chat_id},{nome}\n")
    print(f"💾 Usuário cadastrado automaticamente: {nome} ({chat_id})")

# Monitora quando alguém envia o comando /start
@bot.message_handler(commands=['start'])
def boas_vindas(mensagem):
    chat_id_do_usuario = mensagem.chat.id if 'mensaje' in locals() else mensagem.chat.id
    nome_usuario = mensagem.from_user.first_name
    
    # Agora a função existe e o erro vai sumir!
    salvar_novo_usuario(chat_id_do_usuario, nome_usuario)
    
    bot.reply_to(mensagem, f"Olá, {nome_usuario}! Seu Alerta Motociclista foi ativado com sucesso!")

# Deixa o bot rodando e escutando o Telegram
print("🛰️ Servidor do Telegram ativo no arquivo bottelegram.py...")
bot.infinity_polling()