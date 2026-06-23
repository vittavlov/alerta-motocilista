from dataclasses import dataclass, field
from enum import Enum

class NivelRisco(Enum):
    SEGURO    = "✅ SEGURO"
    ATENCAO   = "⚠️  ATENÇÃO"
    PERIGO    = "🔴 PERIGO"
    CRITICO   = "🚨 CRÍTICO"

@dataclass
class Alerta:
    nivel: NivelRisco
    tipo: str
    mensagem: str

def analisar_risco(dados: dict) -> list[Alerta]:
    """
    Recebe o JSON da API e retorna lista de alertas
    específicos para quem anda de moto.
    """
    alertas = []

    clima     = dados["weather"][0]
    condicao  = clima["main"]          # "Rain", "Thunderstorm", "Clear", "Clouds"...
    descricao = clima["description"]   # "chuva moderada", "trovoada", "nublado"...

    vento_kmh   = dados["wind"]["speed"] * 3.6   # API entrega m/s → converte
    visibilidade = dados.get("visibility", 10000) # em metros
    chuva_1h    = dados.get("rain", {}).get("1h", 0)  # mm na última hora

    # --- Chuva ---
    if condicao == "Rain":
        if chuva_1h >= 20:
            alertas.append(Alerta(
                NivelRisco.CRITICO,
                "CHUVA INTENSA",
                f"Chuva de {chuva_1h:.1f}mm/h — risco alto de aquaplanagem e alagamentos."
            ))
        elif chuva_1h >= 5:
            alertas.append(Alerta(
                NivelRisco.PERIGO,
                "CHUVA MODERADA",
                f"Chuva de {chuva_1h:.1f}mm/h — pista escorregadia, reduza a velocidade."
            ))
        else:
            alertas.append(Alerta(
                NivelRisco.ATENCAO,
                "GAROA",
                "Chuva fraca — atenção ao óleo aflorado no asfalto (mais perigoso no início)."
            ))

    # --- Tempestade ---
    if condicao == "Thunderstorm":
        alertas.append(Alerta(
            NivelRisco.CRITICO,
            "TEMPESTADE",
            "Raios, rajadas fortes e chuva intensa. Evite sair — busque abrigo imediatamente."
        ))

    # --- Céu Nublado / Encoberto ---
    # Captura quando o tempo está fechado mas ainda não começou a chover
    if condicao == "Clouds":
        termos_nublado = ['nublado', 'encoberto', 'nuvens quebradas']
        if any(termo in descricao.lower() for termo in termos_nublado):
            alertas.append(Alerta(
                NivelRisco.ATENCAO,
                "CÉU NUBLADO",
                f"Tempo fechado ({descricao.capitalize()}) — possibilidade de chuva a qualquer momento."
            ))

    # --- Vento forte ---
    if vento_kmh >= 60:
        alertas.append(Alerta(
            NivelRisco.CRITICO,
            "VENTO MUITO FORTE",
            f"Vento de {vento_kmh:.0f} km/h — risco de perda de controle da moto."
        ))
    elif vento_kmh >= 40:
        alertas.append(Alerta(
            NivelRisco.PERIGO,
            "VENTO FORTE",
            f"Vento de {vento_kmh:.0f} km/h — atenção em viadutos e avenidas largas."
        ))

    # --- Visibilidade ---
    if visibilidade < 200:
        alertas.append(Alerta(
            NivelRisco.CRITICO,
            "NEBLINA DENSA",
            f"Visibilidade de {visibilidade}m — risco extremo. Acenda o farol."
        ))
    elif visibilidade < 1000:
        alertas.append(Alerta(
            NivelRisco.PERIGO,
            "VISIBILIDADE REDUZIDA",
            f"Visibilidade de {visibilidade}m — reduza a velocidade."
        ))

    # --- Risco de deslizamento (heurística simples) ---
    if chuva_1h >= 30:
        alertas.append(Alerta(
            NivelRisco.CRITICO,
            "RISCO DE DESLIZAMENTO",
            "Chuva muito intensa — evite estradas de encosta, morros e áreas de risco."
        ))

    # Se nenhum risco ou aviso preventivo foi detectado
    if not alertas:
        alertas.append(Alerta(
            NivelRisco.SEGURO,
            "BOM TEMPO",
            f"Condições favoráveis para andar de moto. {descricao.capitalize()}."
        ))

    return alertas