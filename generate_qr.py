"""
Detecta o IP do PC na rede local e gera um QR Code com a URL do app.
Rode este script DEPOIS de iniciar o servidor (uvicorn).

Como usar:
    python generate_qr.py
"""
import socket
import os

try:
    import qrcode
except ImportError:
    print("Instale qrcode: pip install qrcode[pil]")
    raise


def get_local_ip() -> str:
    """
    Descobre o IP do PC na rede WiFi local.
    Abre uma conexão UDP para um servidor externo apenas para descobrir
    qual interface de rede está em uso — nenhum dado é enviado.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_qr(port: int = 8000) -> str:
    """Gera qrcode.png com a URL do app e retorna a URL gerada."""
    ip = get_local_ip()
    url = f"http://{ip}:{port}"

    print("\n" + "=" * 50)
    print(f"  URL do App: {url}")
    print(f"  Compartilhe esse link no WhatsApp!")
    print("=" * 50 + "\n")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    output_path = "qrcode.png"
    img.save(output_path)

    print(f"QR Code salvo em: {os.path.abspath(output_path)}")
    print("Imprima ou mostre na tela para os membros escanearem.\n")

    return url


if __name__ == "__main__":
    generate_qr()
