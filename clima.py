import requests
import os
from dotenv import load_dotenv

load_dotenv("api.env")

API_KEY = os.getenv("OWM_API_KEY")
BASE_URL_ATUAL    = "https://api.openweathermap.org/data/2.5/weather"
BASE_URL_PREVISAO = "https://api.openweathermap.org/data/2.5/forecast"

def buscar_clima(cidade: str, pais: str = "BR") -> dict:
    """Retorna clima atual."""
    params = {
        "q": f"{cidade},{pais}",
        "appid": API_KEY,
        "units": "metric",
        "lang": "pt_br"
    }
    resposta = requests.get(BASE_URL_ATUAL, params=params)
    resposta.raise_for_status()
    return resposta.json()

def buscar_previsao(cidade: str, pais: str = "BR") -> list:
    """Retorna previsão das próximas 12 horas."""
    params = {
        "q": f"{cidade},{pais}",
        "appid": API_KEY,
        "units": "metric",
        "lang": "pt_br",
        "cnt": 4
    }
    resposta = requests.get(BASE_URL_PREVISAO, params=params)
    resposta.raise_for_status()
    return resposta.json()["list"]

def buscar_alertas_inmet_brasil() -> list:
    """Busca TODOS os alertas oficiais do INMET ativos no Brasil inteiro."""
    try:
        url = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()

        todos_alertas = []
        for aviso in dados:
            # Captura a lista de cidades do campo 'municipios'
            lista_municipios = aviso.get("municipios", [])
            
            if isinstance(lista_municipios, str):
                cidades_limpas = [c.strip().lower() for c in lista_municipios.split(",")]
            else:
                cidades_limpas = [str(c).strip().lower() for c in lista_municipios]

            todos_alertas.append({
                "titulo":     aviso.get("titulo", ""),
                "severidade": aviso.get("severidade", ""),
                "inicio":     aviso.get("inicio", ""),
                "fim":        aviso.get("fim", ""),
                "descricao":  aviso.get("descricao", ""),
                "cidades":    cidades_limpas
            })
        return todos_alertas

    except Exception as e:
        print(f"⚠️  INMET indisponível: {e}")
        return []
