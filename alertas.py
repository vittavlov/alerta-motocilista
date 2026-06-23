from dataclasses import dataclass
from enum import Enum

class NivelRisco(Enum):
    SEGURO  = "✅ SEGURO"
    ATENCAO = "⚠️  ATENÇÃO"
    PERIGO  = "🔴 PERIGO"
    CRITICO = "🚨 CRÍTICO"

@dataclass
class Alerta:
    nivel: NivelRisco
    tipo: str
    mensagem: str

def analisar_risco(dados: dict) -> list:
    alertas = []

    clima       = dados["weather"][0]
    condicao    = clima["main"]
    descricao   = clima["description"]
    vento_kmh   = dados["wind"]["speed"] * 3.6
    visibilidade = dados.get("visibility", 10000)
    chuva_1h    = dados.get("rain", {}).get("1h", 0)

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
                "Chuva fraca — atenção ao óleo aflorado no asfalto."
            ))

    # --- Tempestade ---
    if condicao == "Thunderstorm":
        alertas.append(Alerta(
            NivelRisco.CRITICO,
            "TEMPESTADE",
            "Raios, rajadas fortes e chuva intensa. Evite sair — busque abrigo."
        ))

    # --- Céu Nublado ---
    if condicao == "Clouds":
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

    # --- Risco de deslizamento ---
    if chuva_1h >= 30:
        alertas.append(Alerta(
            NivelRisco.CRITICO,
            "RISCO DE DESLIZAMENTO",
            "Chuva muito intensa — evite estradas de encosta, morros e áreas de risco."
        ))

    # --- Sem risco ---
    if not alertas:
        alertas.append(Alerta(
            NivelRisco.SEGURO,
            "BOM TEMPO",
            f"Condições favoráveis para andar de moto. {descricao.capitalize()}."
        ))

    return alertas
