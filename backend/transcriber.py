from typing import Optional
import os
import whisper

# Variável global que guarda o modelo carregado
# (carregamos só uma vez para não gastar tempo toda vez)
_model: Optional[object] = None


def load_model(model_name: str = "small"):
    """
    Carrega o modelo Whisper na memória.
    Chame isso UMA VEZ quando o servidor iniciar.

    model_name: "tiny" (rápido, menos preciso) ou "small" (recomendado)
    """
    global _model
    print(f"Carregando modelo Whisper '{model_name}'... (pode demorar 1-2 minutos na primeira vez)")
    _model = whisper.load_model(model_name)
    print(f"Modelo '{model_name}' carregado com sucesso!")


def transcribe_and_translate(wav_path: str) -> str:
    """
    Recebe o caminho de um arquivo .wav em português.
    Retorna o texto traduzido para inglês.
    Deleta o .wav após processar.

    Exemplo:
        texto = transcribe_and_translate("temp/audio123.wav")
        # texto = "Good morning, brothers and sisters"
    """
    if _model is None:
        raise RuntimeError(
            "Modelo Whisper não carregado. Chame load_model() antes de transcrever."
        )

    # task="translate" faz o Whisper transcrever E traduzir para inglês diretamente
    result = _model.transcribe(wav_path, task="translate")
    text = result["text"].strip()
    if not text:
        return ""

    # Deleta o .wav temporário para não encher o disco
    if os.path.exists(wav_path):
        os.remove(wav_path)

    return text
