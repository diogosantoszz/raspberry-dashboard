from flask import Flask, render_template, jsonify, request
import subprocess
import platform
import socket
import requests
import time
import json
import os
from datetime import datetime

app = Flask(__name__)

# Configuração dos Raspberry Pis
RASPBERRIES = [
    {"id": 1, "nome": "Estúdio Pelé", "ip": "192.168.1.179", "descricao": "Flypack N.30", "porta": 5000},
    {"id": 2, "nome": "Estúdio Maradona", "ip": "192.168.1.184", "descricao": "Flypack N.33", "porta": 5000},
    {"id": 3, "nome": "Estúdio Ronaldo", "ip": "192.168.1.155", "descricao": "Flypack N.63", "porta": 5000}
]

# Diretório para armazenar os resultados dos testes
RESULTS_DIR = "resultados"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

def verificar_ping(host):
    """Verifica se o host está acessível via ping"""
    parametro = '-n' if platform.system().lower() == 'windows' else '-c'
    comando = ['ping', parametro, '3', host]
    
    try:
        inicio = time.time()
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        duracao = time.time() - inicio
        
        # Verificar se o comando foi bem-sucedido
        if resultado.returncode == 0:
            # Extrair estatísticas do ping (isso pode variar dependendo do sistema operacional)
            try:
                output = resultado.stdout
                if platform.system().lower() == 'windows':
                    latencia = output.split('Média = ')[1].split('ms')[0].strip()
                else:  # Linux/Mac
                    latencia = output.split('min/avg/max/mdev = ')[1].split('/')[1].strip()
                
                return {
                    "online": True,
                    "latencia": float(latencia),
                    "raw_output": output,
                    "duracao": duracao
                }
            except (IndexError, ValueError):
                return {
                    "online": True,
                    "latencia": None,
                    "raw_output": output,
                    "duracao": duracao
                }
        else:
            return {
                "online": False,
                "latencia": None,
                "raw_output": resultado.stdout,
                "duracao": duracao
            }
    except Exception as e:
        return {
            "online": False,
            "latencia": None,
            "raw_output": str(e),
            "duracao": 0
        }

def verificar_porta(host, porta):
    """Verifica se uma porta específica está aberta"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        inicio = time.time()
        resultado = sock.connect_ex((host, porta))
        duracao = time.time() - inicio
        sock.close()
        return {
            "aberta": resultado == 0,
            "duracao": duracao
        }
    except Exception as e:
        return {
            "aberta": False,
            "duracao": 0,
            "erro": str(e)
        }

def fazer_curl(url):
    """Executa um teste curl para a URL"""
    try:
        inicio = time.time()
        resposta = requests.get(url, timeout=5)
        duracao = time.time() - inicio
        
        return {
            "sucesso": resposta.status_code == 200,
            "status_code": resposta.status_code,
            "tempo_resposta": duracao,
            "tamanho_resposta": len(resposta.content),
            "headers": dict(resposta.headers)
        }
    except Exception as e:
        return {
            "sucesso": False,
            "erro": str(e),
            "tempo_resposta": 0
        }

def executar_speedtest():
    """Executa o teste de velocidade da internet"""
    try:
        resultado = subprocess.run(["speedtest-cli"], capture_output=True, text=True, timeout=60)
        
        if resultado.returncode == 0:
            return jsonify({"resultado": resultado.stdout})
        else:
            return jsonify({"erro": resultado.stderr}), 500
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

def executar_speedtest_remoto(ip, porta):
    """Executa o speedtest em um Raspberry Pi remoto"""
    try:
        url = f"http://{ip}:{porta}/speedtest"
        resposta = requests.get(url, timeout=60)
        
        if resposta.status_code == 200:
            return {
                "sucesso": True,
                "resultado": resposta.json()["resultado"]
            }
        else:
            return {
                "sucesso": False,
                "erro": f"Status code: {resposta.status_code}"
            }
    except Exception as e:
        return {
            "sucesso": False,
            "erro": str(e)
        }

def salvar_resultado(tipo, raspberry_id, dados):
    """Salva o resultado de um teste no arquivo"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = os.path.join(RESULTS_DIR, f"{tipo}_historico.json")
    
    # Carregar dados existentes ou criar lista vazia
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try:
                resultados = json.load(f)
            except json.JSONDecodeError:
                resultados = []
    else:
        resultados = []
    
    # Adicionar novo resultado
    dados["timestamp"] = timestamp
    dados["raspberry_id"] = raspberry_id
    resultados.append(dados)
    
    # Limitar a 100 entradas para evitar que o arquivo fique muito grande
    if len(resultados) > 100:
        resultados = resultados[-100:]
    
    # Salvar de volta no arquivo
    with open(filename, 'w') as f:
        json.dump(resultados, f, indent=2)

def ler_historico(tipo):
    """Lê o histórico de resultados de um tipo de teste"""
    filename = os.path.join(RESULTS_DIR, f"{tipo}_historico.json")
    
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    else:
        return []

@app.route('/')
def index():
    """Página principal do dashboard"""
    return render_template('index.html', raspberries=RASPBERRIES)

@app.route('/api/raspberry/<int:raspberry_id>')
def get_raspberry(raspberry_id):
    """Retorna os detalhes de um Raspberry Pi"""
    for raspberry in RASPBERRIES:
        if raspberry["id"] == raspberry_id:
            return jsonify(raspberry)
    return jsonify({"erro": "Raspberry Pi não encontrado"}), 404

@app.route('/api/ping/<int:raspberry_id>')
def api_ping(raspberry_id):
    """Executa ping em um Raspberry Pi específico"""
    for raspberry in RASPBERRIES:
        if raspberry["id"] == raspberry_id:
            resultado = verificar_ping(raspberry["ip"])
            salvar_resultado("ping", raspberry_id, resultado)
            return jsonify(resultado)
    return jsonify({"erro": "Raspberry Pi não encontrado"}), 404

@app.route('/api/port/<int:raspberry_id>')
def api_port(raspberry_id):
    """Verifica se a porta está aberta em um Raspberry Pi específico"""
    for raspberry in RASPBERRIES:
        if raspberry["id"] == raspberry_id:
            resultado = verificar_porta(raspberry["ip"], raspberry["porta"])
            salvar_resultado("porta", raspberry_id, resultado)
            return jsonify(resultado)
    return jsonify({"erro": "Raspberry Pi não encontrado"}), 404

@app.route('/api/curl/<int:raspberry_id>')
def api_curl(raspberry_id):
    """Executa curl em um Raspberry Pi específico"""
    for raspberry in RASPBERRIES:
        if raspberry["id"] == raspberry_id:
            url = f"http://{raspberry['ip']}:{raspberry['porta']}"
            resultado = fazer_curl(url)
            salvar_resultado("curl", raspberry_id, resultado)
            return jsonify(resultado)
    return jsonify({"erro": "Raspberry Pi não encontrado"}), 404

@app.route('/api/speedtest/local')
def api_speedtest_local():
    """Executa speedtest no servidor local"""
    resultado = executar_speedtest()
    salvar_resultado("speedtest", 0, resultado)  # 0 representa o servidor
    return jsonify(resultado)

@app.route('/api/speedtest/<int:raspberry_id>')
def api_speedtest_remote(raspberry_id):
    """Executa speedtest em um Raspberry Pi remoto"""
    for raspberry in RASPBERRIES:
        if raspberry["id"] == raspberry_id:
            resultado = executar_speedtest_remoto(raspberry["ip"], raspberry["porta"])
            salvar_resultado("speedtest", raspberry_id, resultado)
            return jsonify(resultado)
    return jsonify({"erro": "Raspberry Pi não encontrado"}), 404

@app.route('/api/status')
def api_status():
    """Verifica o status de todos os Raspberry Pis"""
    resultados = []
    
    for raspberry in RASPBERRIES:
        ping_result = verificar_ping(raspberry["ip"])
        port_result = verificar_porta(raspberry["ip"], raspberry["porta"])
        
        resultado = {
            "id": raspberry["id"],
            "nome": raspberry["nome"],
            "ip": raspberry["ip"],
            "descricao": raspberry["descricao"],
            "online": ping_result["online"],
            "porta_aberta": port_result["aberta"],
            "latencia": ping_result.get("latencia")
        }
        
        resultados.append(resultado)
    
    return jsonify(resultados)

@app.route('/api/historico/<tipo>')
def api_historico(tipo):
    """Retorna o histórico de um tipo de teste"""
    tipos_validos = ["ping", "porta", "curl", "speedtest"]
    
    if tipo not in tipos_validos:
        return jsonify({"erro": "Tipo de teste inválido"}), 400
    
    resultados = ler_historico(tipo)
    return jsonify(resultados)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
