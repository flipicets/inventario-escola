import os
import psycopg2
import csv
import io
from datetime import datetime, date
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, Response, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_nuvem_escola")

SENHA_SISTEMA = "#cmilitarJP"
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("A variável de ambiente DATABASE_URL não foi configurada!")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Criação das tabelas base
        cur.execute('''CREATE TABLE IF NOT EXISTS computadores (
                        id SERIAL PRIMARY KEY,
                        setor TEXT, 
                        cpu TEXT, 
                        ram TEXT, 
                        armazenamento TEXT, 
                        infos_extras TEXT,
                        ultima_preventiva DATE)''')
                        
        cur.execute('''CREATE TABLE IF NOT EXISTS chamados (
                        id SERIAL PRIMARY KEY, 
                        pc_id INTEGER, 
                        descricao TEXT,
                        data_chamado TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                        status TEXT DEFAULT 'Aberto',
                        categoria TEXT DEFAULT 'Geral',
                        FOREIGN KEY(pc_id) REFERENCES computadores(id))''')

        # Verifica e adiciona a coluna de numero_registro caso ela não exista
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='computadores' AND column_name='numero_registro'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE computadores ADD COLUMN numero_registro TEXT")

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao inicializar o banco: {e}")

if DATABASE_URL:
    init_db()

# =====================================================================
# TEMPLATE VISUAL ÚNICO (Com Rodapé e Notificações Injetadas)
# =====================================================================
BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inventário TI - Sistema Escolar</title>
    <!-- Favicon dinâmico para notificação -->
    <link id="favicon" rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%230071e3' rx='20'/></svg>">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f5f5f7; color: #1d1d1f; margin: 0; padding: 0; display: flex; flex-direction: column; min-height: 100vh;}
        .navbar { background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(20px); position: sticky; top: 0; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d2d2d7; z-index: 100; }
        .navbar a { text-decoration: none; color: #1d1d1f; font-weight: 600; font-size: 18px; }
        .nav-links a { font-size: 14px; color: #0071e3; margin-left: 20px; font-weight: 400; display: inline-flex; align-items: center; }
        .container { max-width: 900px; margin: 40px auto; padding: 0 20px; flex: 1; width: 100%; box-sizing: border-box; }
        .card { background: #ffffff; border-radius: 18px; padding: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); margin-bottom: 25px; }
        h1, h2, h3 { font-weight: 600; letter-spacing: -0.5px; margin-top: 0; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 6px; font-size: 14px; font-weight: 500; }
        input, textarea, select { width: 100%; padding: 12px; border: 1px solid #d2d2d7; border-radius: 10px; box-sizing: border-box; font-family: inherit; background: #fff; font-size: 15px; }
        input:focus, textarea:focus, select:focus { border-color: #0071e3; outline: none; }
        button { background: #0071e3; color: white; border: none; padding: 12px 20px; border-radius: 10px; font-size: 15px; font-weight: 500; cursor: pointer; transition: 0.2s; }
        button:hover { background: #0077ed; }
        button.danger { background: #ff3b30; }
        button.danger:hover { background: #ff453a; }
        button.warning { background: #ffcc00; color: #1d1d1f; }
        button.success { background: #34c759; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #e8e8ed; font-size: 14px; }
        th { background: #f5f5f7; font-weight: 600; }
        .badge { background: #e8e8ed; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 600; }
        .badge.open { background: #ffe5e5; color: #ff3b30; }
        .badge.maintenance { background: #fff5cc; color: #b08d00; }
        .badge.resolved { background: #e6f4ea; color: #137333; }
        .badge.risk { background: #fff0d4; color: #b06000; }
        .alert { padding: 12px; border-radius: 10px; margin-bottom: 20px; font-weight: 500; text-align: center; font-size: 14px; }
        .alert-success { background: #e3f2fd; color: #0071e3; }
        .alert-error { background: #ffebee; color: #d32f2f; }
        .alert-warning { background: #fff5cc; color: #b08d00; }
        .tab-menu { display: flex; border-bottom: 1px solid #d2d2d7; margin-bottom: 25px; overflow-x: auto; white-space: nowrap; }
        .tab-menu a { padding: 10px 20px; text-decoration: none; color: #86868b; font-weight: 500; border-bottom: 2px solid transparent; }
        .tab-menu a.active { color: #0071e3; border-bottom-color: #0071e3; }

        details { border: 1px solid #d2d2d7; border-radius: 12px; margin-bottom: 15px; background: #fff; overflow: hidden; transition: all 0.3s ease; }
        summary { padding: 15px 20px; font-weight: 600; font-size: 16px; cursor: pointer; background: #f5f5f7; display: flex; justify-content: space-between; align-items: center; list-style: none; user-select: none; }
        summary::-webkit-details-marker { display: none; }
        summary:hover { background: #e8e8ed; }
        .details-content { padding: 0 20px 20px 20px; overflow-x: auto; }
        details[open] summary { border-bottom: 1px solid #d2d2d7; margin-bottom: 10px; }

        .search-bar { width: 100%; padding: 15px; font-size: 16px; border: 2px solid #d2d2d7; border-radius: 12px; margin-bottom: 20px; background: #f5f5f7 url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="%2386868b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>') no-repeat 15px center; padding-left: 45px; }
        .search-bar:focus { background-color: #fff; border-color: #0071e3; }
        
        .footer { display: flex; justify-content: space-between; align-items: center; padding: 25px 30px; background: #fff; border-top: 1px solid #d2d2d7; font-size: 13px; color: #86868b; margin-top: auto; }
        .notification-dot { display: none; background:#ff9500; color:#fff; border-radius:50%; padding:2px 6px; font-size:11px; margin-left:6px; font-weight:bold; }
    </style>
    <script>
        function buscarInventario() {
            let input = document.getElementById('buscaPcs').value.toLowerCase();
            let setores = document.querySelectorAll('details');

            setores.forEach(setor => {
                let showSetor = false;
                let linhas = setor.querySelectorAll('.linha-pc');

                linhas.forEach(linha => {
                    let texto = linha.innerText.toLowerCase();
                    if(texto.includes(input)) {
                        linha.style.display = '';
                        showSetor = true;
                    } else {
                        linha.style.display = 'none';
                    }
                });

                if(input !== '') {
                    setor.style.display = showSetor ? '' : 'none';
                    if(showSetor) setor.open = true;
                } else {
                    setor.style.display = '';
                    setor.open = false;
                }
            });
        }

        // Sistema de notificação em tempo real
        function checkNotifications() {
            fetch('/api/chamados_status')
                .then(res => res.json())
                .then(data => {
                    let fav = document.getElementById('favicon');
                    let badge = document.getElementById('nav-badge');
                    if (data.abertos > 0) {
                        fav.href = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='50' fill='%23ff9500'/></svg>";
                        document.title = '(🔔) Novo Chamado! - TI Escolar';
                        if(badge) { 
                            badge.style.display = 'inline-block'; 
                            badge.innerText = data.abertos; 
                        }
                    } else {
                        fav.href = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%230071e3' rx='20'/></svg>";
                        document.title = 'Inventário TI - Sistema Escolar';
                        if(badge) { badge.style.display = 'none'; }
                    }
                })
                .catch(err => console.log('Erro de notificação', err));
        }
        setInterval(checkNotifications, 20000); // Checa a cada 20 segundos
        window.onload = checkNotifications;
    </script>
</head>
<body>
    <div class="navbar">
        <a href="/">💻 Inventário TI Escolar</a>
        <div class="nav-links">
            {% if session.get('logged_in') %}
                <a href="/admin">Painel Admin <span id="nav-badge" class="notification-dot"></span></a>
                <a href="/logout" style="color: #ff3b30;">Sair</a>
            {% else %}
                <a href="/login">Área do Professor</a>
            {% endif %}
        </div>
    </div>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {{ content | safe }}
    </div>
    <div class="footer">
        <div>Desenvolvido por <strong>Fellipe Picetskei</strong></div>
        <div>Contato: fellipe.picetskei@gmail.com</div>
    </div>
</body>
</html>
"""

# =====================================================================
# FUNÇÕES AUXILIARES
# =====================================================================
def precisa_preventiva(data_valor):
    if not data_valor: return True
    try:
        if isinstance(data_valor, date):
            diferenca = date.today() - data_valor
        else:
            data_prev = datetime.strptime(str(data_valor), '%Y-%m-%d').date()
            diferenca = date.today() - data_prev
        return diferenca.days > 180
    except:
        return True

# =====================================================================
# ROTAS DO SISTEMA E API
# =====================================================================

@app.route('/api/chamados_status')
def api_chamados_status():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(id) FROM chamados WHERE status = 'Aberto'")
    qtd_abertos = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({"abertos": qtd_abertos})

@app.route('/')
def index():
    return render_template_string(BASE_LAYOUT, content="""
        <div class="card" style="text-align: center; padding: 50px 20px;">
            <h1>Bem-vindo ao Inventário de TI</h1>
            <p style="color: #86868b; font-size: 18px;">Escaneie o QR Code colado em qualquer computador para ver suas especificações técnicas ou abrir um chamado.</p>
            <br>
            <a href="/login"><button>Acessar como Professor</button></a>
        </div>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('senha') == SENHA_SISTEMA:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        flash('Senha incorreta!', 'error')

    return render_template_string(BASE_LAYOUT, content="""
        <div class="card" style="max-width: 400px; margin: 60px auto;">
            <h2>Área do Professor</h2>
            <form method="POST">
                <div class="form-group"><label>Senha de Acesso</label><input type="password" name="senha" required></div>
                <button type="submit" style="width:100%;">Entrar no Painel</button>
            </form>
        </div>
    """)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'): return redirect(url_for('login'))

    tab = request.args.get('tab', 'inventario')
    conn = get_db_connection()
    c = conn.cursor()

    if request.method == 'POST' and tab == 'cadastrar':
        setor = request.form.get('setor').strip()
        cpu = request.form.get('cpu')
        ram = request.form.get('ram')
        arm = request.form.get('armazenamento')
        ext = request.form.get('extra')
        registro = request.form.get('registro')
        prev = request.form.get('preventiva')
        prev = prev if prev else None

        c.execute("INSERT INTO computadores (setor, cpu, ram, armazenamento, infos_extras, ultima_preventiva, numero_registro) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                  (setor, cpu, ram, arm, ext, prev, registro))
        conn.commit()
        flash('Computador cadastrado com sucesso!', 'success')
        return redirect('/admin?tab=inventario')

    c.execute("SELECT id, setor, cpu, ram, armazenamento, infos_extras, ultima_preventiva, numero_registro FROM computadores ORDER BY setor ASC, id ASC")
    pcs = c.fetchall()
    c.execute("SELECT c.id, p.setor, c.descricao, c.data_chamado, c.status, c.categoria, p.id FROM chamados c JOIN computadores p ON c.pc_id = p.id WHERE c.status IN ('Aberto', 'Em Manutenção') ORDER BY c.status ASC, c.id DESC")
    chamados_ativos = c.fetchall()

    menu = f"""
    <div class="tab-menu">
        <a href="/admin?tab=inventario" class="{'active' if tab=='inventario' else ''}">Inventário Visual</a>
        <a href="/admin?tab=cadastrar" class="{'active' if tab=='cadastrar' else ''}">Cadastrar Novo PC</a>
        <a href="/admin?tab=chamados" class="{'active' if tab=='chamados' else ''}">Chamados Ativos ({len(chamados_ativos)})</a>
        <a href="/admin?tab=diagnostico" class="{'active' if tab=='diagnostico' else ''}">Diagnóstico e Histórico</a>
    </div>
    """

    if tab == 'inventario':
        pcs_por_setor = {}
        for pc in pcs:
            setor = pc[1]
            if setor not in pcs_por_setor: pcs_por_setor[setor] = []
            pcs_por_setor[setor].append(pc)

        conteudo = """
        <h2>Inventário por Localização</h2>
        <input type="text" id="buscaPcs" class="search-bar" placeholder="Buscar por ID, processador, RAM ou observação..." onkeyup="buscarInventario()">
        """

        if not pcs_por_setor:
            conteudo += "<p style='text-align:center; color:#86868b;'>Nenhum computador cadastrado ainda.</p>"
        else:
            for setor, maquinas in pcs_por_setor.items():
                linhas_tabela = ""
                for pc in maquinas:
                    alerta_prev = '<span style="background:#ffcc00; color:#1d1d1f; padding:3px 8px; border-radius:10px; font-size:11px; font-weight:bold; margin-left:8px; display:inline-block;" title="Limpeza atrasada (mais de 6 meses)">⚠️ Limpeza</span>' if precisa_preventiva(pc[6]) else ''
                    # pc[7] = numero_registro
                    reg_text = f" | Reg: {pc[7]}" if pc[7] else ""

                    linhas_tabela += f"""
                    <tr class="linha-pc">
                        <td style="white-space: nowrap;"><strong>#{pc[0]}</strong> {alerta_prev}</td>
                        <td>{pc[2]} <br> <span style="color:#86868b; font-size:12px;">{pc[3]} | {pc[4]}{reg_text} | Última Prev: {pc[6] or 'Nunca'}</span></td>
                        <td style="text-align: right; white-space: nowrap;">
                            <a href="/admin/imprimir/{pc[0]}" target="_blank"><button style="padding:6px 12px; font-size:12px;">QR Code</button></a>
                            <a href="/admin/duplicar/{pc[0]}"><button style="padding:6px 12px; font-size:12px; background:#5e5ce6;">Clonar</button></a>
                            <a href="/admin/editar/{pc[0]}"><button style="padding:6px 12px; font-size:12px; background:#ff9500;">Editar</button></a>
                            <a href="/admin/deletar/{pc[0]}" onclick="return confirm('Apagar o PC #{pc[0]} permanentemente?')"><button class="danger" style="padding:6px 12px; font-size:12px;">Remover</button></a>
                        </td>
                    </tr>
                    """
                conteudo += f"""
                <details>
                    <summary>
                        <span>📍 {setor}</span>
                        <div style="display:flex; align-items:center;">
                            <button onclick="event.stopPropagation(); window.open('/admin/imprimir_setor/{setor}', '_blank');" style="margin-right:15px; padding:6px 12px; font-size:12px; background:#107c41;">🖨️ QRs do Setor</button>
                            <span class="badge" style="background:#0071e3; color:white;">{len(maquinas)} PCs</span>
                        </div>
                    </summary>
                    <div class="details-content"><table><tr><th>ID</th><th>Especificações</th><th style="text-align: right;">Ações</th></tr>{linhas_tabela}</table></div>
                </details>
                """

    elif tab == 'cadastrar':
        hoje = date.today().strftime('%Y-%m-%d')
        conteudo = f"""
        <h2>Cadastrar Novo Computador</h2>
        <form method="POST" action="/admin?tab=cadastrar">
            <div class="grid">
                <div class="form-group"><label>Setor / Sala</label><input type="text" name="setor" required></div>
                <div class="form-group"><label>Processador (CPU)</label><input type="text" name="cpu"></div>
                <div class="form-group"><label>Memória RAM</label><input type="text" name="ram"></div>
                <div class="form-group"><label>Armazenamento</label><input type="text" name="armazenamento"></div>
            </div>
            <div class="grid">
                <div class="form-group"><label>Nº de Registro (Estado/Garantia)</label><input type="text" name="registro" placeholder="Ex: 001234"></div>
                <div class="form-group"><label>Última Manutenção Preventiva</label><input type="date" name="preventiva" value="{hoje}"></div>
            </div>
            <div class="form-group"><label>Notas Técnicas</label><textarea name="extra" rows="2"></textarea></div>
            <button type="submit">Salvar no Banco em Nuvem</button>
        </form>
        """

    elif tab == 'chamados':
        linhas_c = ""
        for ch in chamados_ativos:
            status_class = 'open' if ch[4] == 'Aberto' else 'maintenance'
            botoes = ""
            if ch[4] == 'Aberto':
                botoes += f'<a href="/admin/mudar_status/{ch[0]}/Em Manutenção"><button class="warning" style="padding:6px 10px; font-size:12px;">Em Análise</button></a> '
            botoes += f'<a href="/admin/mudar_status/{ch[0]}/Resolvido"><button class="success" style="padding:6px 10px; font-size:12px;">Resolver</button></a>'

            linhas_c += f"""
            <tr>
                <td><strong>#{ch[0]}</strong></td>
                <td><span class="badge">{ch[1]}</span> (PC #{ch[6]})</td>
                <td><span style="color:#0071e3; font-weight:600; font-size:12px;">[{ch[5]}]</span><br>{ch[2]}</td>
                <td><span class="badge {status_class}">{ch[4]}</span></td>
                <td style="text-align:right;">{botoes}</td>
            </tr>
            """
        conteudo = f"""
        <h2>Gestão de Chamados</h2>
        <table>
            <tr><th>ID</th><th>Setor (Origem)</th><th>Problema Relatado</th><th>Status</th><th style="text-align:right;">Ação</th></tr>
            {linhas_c if linhas_c else '<tr><td colspan="5" style="text-align:center; padding:20px; color:#86868b;">Nenhum chamado pendente.</td></tr>'}
        </table>
        """

    elif tab == 'diagnostico':
        c.execute("SELECT categoria, COUNT(id) FROM chamados GROUP BY categoria ORDER BY COUNT(id) DESC")
        categorias = c.fetchall()

        c.execute("""SELECT p.setor, COUNT(c.id) FROM chamados c JOIN computadores p ON c.pc_id = p.id GROUP BY p.setor ORDER BY COUNT(c.id) DESC""")
        risco_setores = c.fetchall()

        c.execute("""SELECT c.id, p.setor, c.pc_id, c.descricao, c.data_chamado
                     FROM chamados c
                     JOIN computadores p ON c.pc_id = p.id
                     WHERE c.status='Resolvido' ORDER BY c.data_chamado DESC""")
        historico_resolvidos = c.fetchall()

        linhas_cat = "".join([f"<tr><td>{cat[0]}</td><td><span class='badge'>{cat[1]} registros</span></td></tr>" for cat in categorias])
        linhas_setores = "".join([f"<tr><td>📍 {rs[0]}</td><td><span class='badge risk'>{rs[1]} ocorrências</span></td></tr>" for rs in risco_setores])

        linhas_hist = ""
        for hist in historico_resolvidos:
            data_formatada = hist[4].strftime('%d/%m/%Y %H:%M') if isinstance(hist[4], datetime) else hist[4]
            linhas_hist += f"""
            <tr>
                <td><strong>#{hist[0]}</strong></td>
                <td>{hist[1]} (PC #{hist[2]})</td>
                <td>{hist[3]}</td>
                <td style="color:#86868b;">{data_formatada}</td>
                <td><span class="badge resolved">Concluído</span></td>
            </tr>
            """

        conteudo = f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2>Diagnóstico Estatístico</h2>
            <a href="/admin/exportar_csv"><button style="background: #107c41;">📥 Baixar Relatório Excel (.csv)</button></a>
        </div>
        <div class="grid">
            <div>
                <h3>Onde quebra mais? (Por Setor)</h3>
                <table><tr><th>Setor</th><th>Volume</th></tr>{linhas_setores or '<tr><td colspan="2">Sem dados</td></tr>'}</table>
            </div>
            <div>
                <h3>O que quebra mais? (Por Categoria)</h3>
                <table><tr><th>Categoria</th><th>Volume</th></tr>{linhas_cat or '<tr><td colspan="2">Sem dados</td></tr>'}</table>
            </div>
        </div>
        <br><br>
        <hr style="border:0; border-top:1px solid #d2d2d7; margin:20px 0;">
        <h3>Histórico Geral de Manutenções Concluídas</h3>
        <table>
            <tr><th>ID Chamado</th><th>Origem</th><th>Problema Consertado</th><th>Data do Registro</th><th>Status</th></tr>
            {linhas_hist if linhas_hist else '<tr><td colspan="5" style="text-align:center; padding:20px; color:#86868b;">Nenhuma manutenção foi finalizada ainda.</td></tr>'}
        </table>
        """

    c.close()
    conn.close()
    return render_template_string(BASE_LAYOUT, content=menu + '<div class="card">' + conteudo + '</div>')

# =====================================================================
# AÇÕES: EXPORTAR, MUDAR STATUS, EDITAR, CLONAR E IMPRIMIR
# =====================================================================

@app.route('/admin/imprimir_setor/<string:setor>')
def imprimir_setor(setor):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, setor FROM computadores WHERE setor=%s", (setor,))
    pcs = cur.fetchall()
    cur.close()
    conn.close()

    qrs_html = ""
    for pc in pcs:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={request.url_root}pc/{pc[0]}"
        qrs_html += f"""
        <div style="text-align:center; padding:15px; border:1px dashed #d2d2d7; border-radius:12px; width:170px; background:#fff;">
            <h3 style="margin: 0 0 10px 0; font-size:16px;">ID: {pc[0]}<br><span style="font-size:13px; color:#86868b;">{pc[1]}</span></h3>
            <img src="{qr_url}" alt="QR" width="150" height="150">
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>QRs - {setor}</title>
        <style>
            body {{ font-family: sans-serif; background: #f5f5f7; padding: 20px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .grid {{ display: flex; flex-wrap: wrap; gap: 20px; }}
            @media print {{
                body {{ background: #fff; padding: 0; }}
                .no-print {{ display: none !important; }}
                .grid {{ gap: 10px; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>Lote de QR Codes - {setor}</h2>
            <button onclick="window.print()" class="no-print" style="padding:10px 20px; background:#0071e3; color:#fff; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">🖨️ Imprimir Página</button>
        </div>
        <div class="grid">
            {qrs_html}
        </div>
    </body>
    </html>
    """

@app.route('/admin/exportar_csv')
def exportar_csv():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""SELECT c.id, p.setor, p.id, c.categoria, c.descricao, c.status, c.data_chamado
                 FROM chamados c JOIN computadores p ON c.pc_id = p.id ORDER BY c.data_chamado DESC""")
    dados = c.fetchall()
    c.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID Chamado', 'Setor', 'ID PC', 'Categoria', 'Descricao do Problema', 'Status', 'Data e Hora'])
    for linha in dados: writer.writerow(linha)

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-disposition": "attachment; filename=relatorio_ti_escola.csv"})

@app.route('/admin/mudar_status/<int:ch_id>/<status>')
def mudar_status(ch_id, status):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE chamados SET status=%s WHERE id=%s", (status, ch_id))
    
    if status == 'Resolvido':
        cur.execute("SELECT pc_id FROM chamados WHERE id=%s", (ch_id,))
        pc_id = cur.fetchone()[0]
        hoje = date.today().strftime('%Y-%m-%d')
        cur.execute("UPDATE computadores SET ultima_preventiva=%s WHERE id=%s", (hoje, pc_id))
        
    conn.commit()
    cur.close()
    conn.close()
    flash(f'Status atualizado para: {status}', 'success')
    return redirect('/admin?tab=chamados')

@app.route('/admin/duplicar/<int:pc_id>')
def duplicar_pc(pc_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT setor, cpu, ram, armazenamento, infos_extras, numero_registro FROM computadores WHERE id=%s", (pc_id,))
    pc = cur.fetchone()
    if pc:
        hoje = date.today().strftime('%Y-%m-%d')
        cur.execute("INSERT INTO computadores (setor, cpu, ram, armazenamento, infos_extras, numero_registro, ultima_preventiva) VALUES (%s,%s,%s,%s,%s,%s,%s)", (*pc, hoje))
        conn.commit()
        flash('Máquina clonada com sucesso!', 'success')
    cur.close()
    conn.close()
    return redirect('/admin?tab=inventario')

@app.route('/admin/editar/<int:pc_id>', methods=['GET', 'POST'])
def editar_pc(pc_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        setor, cpu, ram, arm, ext, prev = request.form.get('setor'), request.form.get('cpu'), request.form.get('ram'), request.form.get('armazenamento'), request.form.get('extra'), request.form.get('preventiva')
        registro = request.form.get('registro')
        prev = prev if prev else None
        cur.execute("UPDATE computadores SET setor=%s, cpu=%s, ram=%s, armazenamento=%s, infos_extras=%s, ultima_preventiva=%s, numero_registro=%s WHERE id=%s", 
                    (setor, cpu, ram, arm, ext, prev, registro, pc_id))
        conn.commit()
        cur.close()
        conn.close()
        flash('Configurações atualizadas!', 'success')
        return redirect('/admin?tab=inventario')

    cur.execute("SELECT id, setor, cpu, ram, armazenamento, infos_extras, ultima_preventiva, numero_registro FROM computadores WHERE id=%s", (pc_id,))
    pc = cur.fetchone()
    cur.close()
    conn.close()

    conteudo_editar = f"""
    <div class="card" style="max-width: 600px; margin: 20px auto;">
        <h2>Editar PC #{pc[0]}</h2>
        <form method="POST">
            <div class="grid">
                <div class="form-group"><label>Setor</label><input type="text" name="setor" value="{pc[1]}" required></div>
                <div class="form-group"><label>CPU</label><input type="text" name="cpu" value="{pc[2]}"></div>
                <div class="form-group"><label>RAM</label><input type="text" name="ram" value="{pc[3]}"></div>
                <div class="form-group"><label>Armazenamento</label><input type="text" name="armazenamento" value="{pc[4]}"></div>
            </div>
            <div class="grid">
                <div class="form-group"><label>Nº de Registro (Garantia)</label><input type="text" name="registro" value="{pc[7] or ''}"></div>
                <div class="form-group"><label>Data da Última Limpeza</label><input type="date" name="preventiva" value="{pc[6] or ''}"></div>
            </div>
            <div class="form-group"><label>Notas Técnicas</label><textarea name="extra" rows="2">{pc[5]}</textarea></div>
            <div style="display: flex; gap: 10px;">
                <button type="submit" style="flex: 1;">Salvar Alterações</button>
                <a href="/admin?tab=inventario" style="text-decoration: none; flex: 1;"><button type="button" style="background: #86868b; width: 100%;">Cancelar</button></a>
            </div>
        </form>
    </div>
    """
    return render_template_string(BASE_LAYOUT, content=conteudo_editar)

@app.route('/admin/deletar/<int:pc_id>')
def deletar_pc(pc_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM chamados WHERE pc_id=%s", (pc_id,))
    cur.execute("DELETE FROM computadores WHERE id=%s", (pc_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Computador removido!', 'success')
    return redirect('/admin?tab=inventario')

@app.route('/admin/imprimir/<int:pc_id>')
def imprimir_qr(pc_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, setor FROM computadores WHERE id=%s", (pc_id,))
    pc = cur.fetchone()
    cur.close()
    conn.close()
    
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={request.url_root}pc/{pc_id}"
    return f"""
    <div style="font-family:sans-serif; text-align:center; max-width:300px; margin:50px auto; padding:20px; border:2px dashed #d2d2d7; border-radius:15px;">
        <h2>ID: {pc[0]} - {pc[1]}</h2><img src="{qr_url}" alt="QR"><br><br>
        <button onclick="window.print()" style="background:#0071e3; color:white; border:none; padding:10px 20px; border-radius:8px; cursor:pointer;">Imprimir</button>
    </div>
    """

# =====================================================================
# ÁREA PÚBLICA (ALUNO / LEITURA DO QR CODE)
# =====================================================================
@app.route('/pc/<int:pc_id>', methods=['GET', 'POST'])
def view_pc(pc_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, setor, cpu, ram, armazenamento, infos_extras, numero_registro FROM computadores WHERE id=%s", (pc_id,))
    pc = cur.fetchone()
    if not pc: return "PC não encontrado.", 404

    cur.execute("SELECT status FROM chamados WHERE pc_id=%s AND status IN ('Aberto', 'Em Manutenção')", (pc_id,))
    chamado_ativo = cur.fetchone()

    if request.method == 'POST' and not chamado_ativo:
        senha, desc, cat = request.form.get('senha'), request.form.get('descricao'), request.form.get('categoria')
        if senha == SENHA_SISTEMA:
            cur.execute("INSERT INTO chamados (pc_id, descricao, categoria) VALUES (%s, %s, %s)", (pc_id, desc, cat))
            conn.commit()
            flash('Chamado registrado! A TI foi notificada.', 'success')
            chamado_ativo = ('Aberto',)
        else:
            flash('Senha de professor incorreta!', 'error')

    cur.close()
    conn.close()

    if chamado_ativo:
        status_texto = "Aguardando Técnico" if chamado_ativo[0] == "Aberto" else "Técnico já está atuando"
        form_html = f"""
        <div class="alert alert-warning" style="font-size:16px;">
            ⚠️ <strong>Atenção:</strong> Já existe um chamado de manutenção para esta máquina.<br>
            <span style="font-size:14px; display:inline-block; margin-top:8px;">Status atual: <b>{status_texto}</b></span>
        </div>
        """
    else:
        form_html = """
        <form method="POST">
            <div class="form-group">
                <label>Tipo de Problema</label>
                <select name="categoria" required>
                    <option value="" disabled selected>Selecione uma categoria...</option>
                    <option value="Internet / Rede">🌐 Sem Internet / Rede</option>
                    <option value="Sistema / Lento">💻 Sistema Lento / Travando</option>
                    <option value="Peças / Não Liga">⚙️ Não Liga / Problema Físico</option>
                    <option value="Periféricos">🖱️ Teclado / Mouse / Monitor</option>
                    <option value="Outros">Outros</option>
                </select>
            </div>
            <div class="form-group">
                <label>Descreva o que está acontecendo</label>
                <textarea name="descricao" rows="2" required></textarea>
            </div>
            <div class="form-group">
                <label>Senha do Professor</label>
                <input type="password" name="senha" required>
            </div>
            <button type="submit" style="width:100%; background:#ff3b30;">Enviar Chamado</button>
        </form>
        """

    return render_template_string(BASE_LAYOUT, content=f"""
    <div class="card" style="max-width: 500px; margin: 0 auto;">
        <h1 style="text-align:center;">Ficha Técnica</h1>
        <div style="text-align:center; margin-bottom:20px;"><span class="badge">Setor: {pc[1]} (ID: #{pc[0]})</span></div>
        <div style="background:#f5f5f7; padding:15px; border-radius:12px; margin-bottom:20px;">
            <p style="margin:5px 0;"><strong>CPU:</strong> {pc[2]}</p>
            <p style="margin:5px 0;"><strong>RAM:</strong> {pc[3]}</p>
            <p style="margin:5px 0;"><strong>Disco:</strong> {pc[4]}</p>
            <p style="margin:5px 0;"><strong>Nº de Registro (Estado):</strong> {pc[6] or 'Não informado'}</p>
        </div>
        <hr style="border:0; border-top:1px solid #d2d2d7; margin:20px 0;">
        <h2>Relatar Problema</h2>
        {form_html}
    </div>
    """)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
