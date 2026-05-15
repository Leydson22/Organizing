import sys
import os
import json
import threading
import webbrowser
import time
import re
from flask import Flask, render_template, send_from_directory, request, redirect, url_for

# Setup PyInstaller paths
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

CONFIG_FILE = 'config.json'

def load_video_dirs():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert old list format to new object format
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str):
                    return [{"path": p, "name": os.path.basename(p), "order": i} for i, p in enumerate(data)]
                return data
        except:
            pass
    return []

def save_video_dirs(dirs):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(dirs, f, indent=4)

VIDEO_DIRS = load_video_dirs()

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.webm')

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s['nome'])]

def scan_videos():
    global VIDEO_DIRS
    VIDEO_DIRS = load_video_dirs()
    # Sort VIDEO_DIRS by order first
    sorted_dirs = sorted(VIDEO_DIRS, key=lambda x: x.get('order', 0))
    
    cursos = {}
    for item in sorted_dirs:
        path = item['path']
        if not os.path.exists(path):
            continue
        
        # Use custom name if available, else basename
        nome_curso = item.get('name') or os.path.basename(path)
        
        if nome_curso not in cursos:
            cursos[nome_curso] = {}
            
        for root, dirs, files in os.walk(path):
            for arquivo in files:
                if arquivo.lower().endswith(VIDEO_EXTENSIONS):
                    rel_path = os.path.relpath(os.path.join(root, arquivo), path)
                    rel_path = rel_path.replace('\\', '/')
                    parts = rel_path.split('/')
                    
                    if len(parts) > 1:
                        categoria = parts[0]
                        nome_exibicao = " - ".join([os.path.splitext(p)[0] for p in parts[1:]])
                    else:
                        categoria = "Raiz"
                        nome_exibicao = os.path.splitext(arquivo)[0]
                        
                    if categoria not in cursos[nome_curso]:
                        cursos[nome_curso][categoria] = []
                        
                    cursos[nome_curso][categoria].append({
                        'nome': nome_exibicao,
                        'filepath': rel_path,
                        'pasta_base': path
                    })
                    
    cursos_final = []
    # Maintain order from VIDEO_DIRS
    for item in sorted_dirs:
        nome_curso = item.get('name') or os.path.basename(item['path'])
        if nome_curso in cursos:
            categorias = cursos[nome_curso]
            cat_sorted = {}
            for cat in sorted(categorias.keys(), key=natural_sort_key_for_cat):
                vlist = sorted(categorias[cat], key=natural_sort_key)
                if vlist:
                    cat_sorted[cat] = vlist
            if cat_sorted:
                cursos_final.append({
                    "name": nome_curso,
                    "path": item['path'],
                    "categorias": cat_sorted
                })
            
    return cursos_final

def natural_sort_key_for_cat(c):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', c)]

@app.route('/')
def index():
    try:
        busca = request.args.get('q', '').lower()
        cursos = scan_videos()

        if busca:
            filtrado = []
            for curso_data in cursos:
                found_cats = {}
                for cat, videos in curso_data['categorias'].items():
                    encontrados = [v for v in videos if busca in v['nome'].lower()]
                    if encontrados:
                        found_cats[cat] = encontrados
                
                if found_cats:
                    filtrado.append({
                        "name": curso_data['name'],
                        "path": curso_data['path'],
                        "categorias": found_cats
                    })
            return render_template('index.html', cursos=filtrado, search_query=busca)

        return render_template('index.html', cursos=cursos, search_query='')
    except Exception as e:
        import traceback
        with open('error.log', 'w') as f:
            f.write(traceback.format_exc())
        return "ERROR", 500

@app.route('/config')
def config_page():
    return render_template('config.html', video_dirs=VIDEO_DIRS)

@app.route('/adicionar_pasta', methods=['POST'])
def adicionar_pasta():
    nova_pasta = request.form.get('nova_pasta', '').strip(' \t\n\r"')
    if nova_pasta and os.path.exists(nova_pasta):
        global VIDEO_DIRS
        paths = [d['path'] for d in VIDEO_DIRS]
        if nova_pasta not in paths:
            VIDEO_DIRS.append({
                "path": nova_pasta,
                "name": os.path.basename(nova_pasta),
                "order": len(VIDEO_DIRS)
            })
            save_video_dirs(VIDEO_DIRS)
    return redirect(url_for('config_page'))

@app.route('/remover_pasta', methods=['POST'])
def remover_pasta():
    pasta_path = request.form.get('pasta', '').strip()
    global VIDEO_DIRS
    VIDEO_DIRS = [d for d in VIDEO_DIRS if d['path'] != pasta_path]
    save_video_dirs(VIDEO_DIRS)
    return redirect(url_for('config_page'))

@app.route('/update_course_metadata', methods=['POST'])
def update_course_metadata():
    try:
        data = request.json
        new_order = data.get('order', []) # List of paths in new order
        new_names = data.get('names', {}) # Map of path -> new name
        
        global VIDEO_DIRS
        # Update names first
        for item in VIDEO_DIRS:
            if item['path'] in new_names:
                item['name'] = new_names[item['path']]
        
        # Update order
        if new_order:
            ordered_dirs = []
            for path in new_order:
                matching = next((d for d in VIDEO_DIRS if d['path'] == path), None)
                if matching:
                    ordered_dirs.append(matching)
            
            # Update order index
            for i, d in enumerate(ordered_dirs):
                d['order'] = i
            
            VIDEO_DIRS = ordered_dirs
            
        save_video_dirs(VIDEO_DIRS)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route('/player/<path:filepath>')
def player(filepath):
    try:
        nome = os.path.basename(filepath)
        categoria = request.args.get('categoria', 'Vídeo')
        
        cursos = scan_videos()
        prev_url = None
        next_url = None
        playlist = []
        
        nome_curso_atual = None
        for curso_data in cursos:
            nome_curso = curso_data['name']
            categorias_dict = curso_data['categorias']
            
            is_in_course = False
            for cat, videos in categorias_dict.items():
                if any(v['filepath'] == filepath for v in videos):
                    is_in_course = True
                    break
            
            if is_in_course:
                nome_curso_atual = nome_curso
                all_videos = []
                for cat, videos in categorias_dict.items():
                    for v in videos:
                        all_videos.append({'cat': cat, 'video': v})
                
                if categoria in categorias_dict:
                    playlist = [{'cat': categoria, 'video': v} for v in categorias_dict[categoria]]
                else:
                    playlist = []
                
                for i, item_v in enumerate(all_videos):
                    if item_v['video']['filepath'] == filepath:
                        if i > 0:
                            prev_v = all_videos[i-1]
                            prev_url = url_for('player', filepath=prev_v['video']['filepath'], categoria=prev_v['cat'])
                        if i < len(all_videos) - 1:
                            next_v = all_videos[i+1]
                            next_url = url_for('player', filepath=next_v['video']['filepath'], categoria=next_v['cat'])
                        break
                break

        return render_template('player.html', filepath=filepath, nome=nome, categoria=categoria, prev_url=prev_url, next_url=next_url, playlist=playlist, nome_curso=nome_curso_atual)
    except Exception as e:
        import traceback
        with open('error_player.log', 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        return f'<pre>ERRO NO PLAYER:\n{traceback.format_exc()}</pre>', 500

@app.route('/browse_folder')
def browse_folder():
    import subprocess
    try:
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, '--pick-folder']
        else:
            cmd = [sys.executable, sys.argv[0], '--pick-folder']
            
        kwargs = {'text': True}
        if os.name == 'nt':  # Windows
            kwargs['creationflags'] = 0x08000000
            
        result = subprocess.check_output(cmd, **kwargs)
        return result.strip()
    except Exception as e:
        import traceback
        with open('error_browse.log', 'w') as f:
            f.write(traceback.format_exc())
        return ""

@app.route('/video/<path:filepath>')
def video(filepath):
    for item in VIDEO_DIRS:
        pasta = item['path']
        caminho_completo = os.path.join(pasta, filepath)
        if os.path.exists(caminho_completo):
            return send_from_directory(os.path.dirname(caminho_completo), os.path.basename(caminho_completo))
    return 'Video não encontrado', 404

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--pick-folder':
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory()
        print(folder)
        sys.exit(0)

    def start_server():
        app.run(host='0.0.0.0', port=5000, debug=False)

    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()

    time.sleep(1)
    webbrowser.open('http://localhost:5000')

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
