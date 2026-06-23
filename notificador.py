from datetime import datetime
from alertas import NivelRisco, Alerta

CORES = {
    NivelRisco.SEGURO:   "\033[92m",
    NivelRisco.ATENCAO:  "\033[93m",
    NivelRisco.PERIGO:   "\033[91m",
    NivelRisco.CRITICO:  "\033[95m",
}
RESET = "\033[0m"

def exibir_alertas(cidade: str, dados: dict, alertas: list):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    temp  = dados["main"]["temp"]
    umid  = dados["main"]["humidity"]

    print(f"\n{'='*55}")
    print(f"  🏍️  ALERTA MOTOCICLISTA — {cidade.upper()}")
    print(f"  🕐 {agora}  |  🌡️  {temp:.1f}°C  |  💧 {umid}% umidade")
    print(f"{'='*55}")

    for alerta in alertas:
        cor = CORES[alerta.nivel]
        print(f"\n{cor}[{alerta.nivel.value}] {alerta.tipo}{RESET}")
        print(f"  → {alerta.mensagem}")

    print(f"\n{'='*55}\n")
