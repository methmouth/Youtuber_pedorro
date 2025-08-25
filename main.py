import os import re import logging import subprocess import requests import gspread import google.generativeai as genai from bs4 import BeautifulSoup from dotenv import load_dotenv from pytrends.request import TrendReq from duckduckgo_search import DDGS from gtts import gTTS

---------------- CONFIGURACIÓN GLOBAL ----------------

load_dotenv()

Logging configurado

logging.basicConfig( level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler()] )

API Gemini

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") if not GEMINI_API_KEY: raise ValueError("Falta la clave GEMINI_API_KEY en .env") genai.configure(api_key=GEMINI_API_KEY)

Google Sheets

try: gc = gspread.service_account(filename='credentials.json') sh = gc.open(os.getenv("GOOGLE_SHEET_NAME")).sheet1 except Exception as e: logging.error(f"Error al conectar con Google Sheets: {e}") sh = None

---------------- FUNCIONES ----------------

def get_trending_topics(country="mexico"): """Obtiene tendencias desde Google Trends usando pytrends.""" logging.info("Buscando temas en tendencia...") try: pytrends = TrendReq(hl='es-MX', tz=360) pytrends.build_payload(kw_list=["Noticias"], cat=0, timeframe='now 1-d', geo='MX', gprop='') trending = pytrends.trending_searches(pn=country) return trending[0].tolist()[:3] except Exception as e: logging.error(f"Error obteniendo tendencias: {e}") return []

def get_context_for_topic(topic):
    """Obtiene contexto de noticias usando NewsAPI (sin DuckDuckGo)."""
    logging.info(f"Buscando contexto para: {topic}")
    context = ""
    try:
        url = f"https://newsapi.org/v2/everything?q={topic}&language=es&sortBy=publishedAt&pageSize=3&apiKey={os.getenv('NEWSAPI_KEY')}"
        resp = requests.get(url)
        articles = resp.json().get("articles", [])
        context = " ".join([a["description"] for a in articles if a.get("description")])
    except Exception as e:
        logging.error(f"Error en NewsAPI: {e}")
    return context[:2000]

# Fallback básico: NewsAPI si está disponible
if not context and os.getenv("NEWSAPI_KEY"):
    try:
        url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={os.getenv('NEWSAPI_KEY')}"
        resp = requests.get(url)
        articles = resp.json().get("articles", [])
        context = " ".join([a["description"] for a in articles[:3] if a["description"]])
    except Exception as e:
        logging.error(f"Error en NewsAPI: {e}")

return context[:2000]

def generate_script(topic, context, variations=1): """Genera 1 o más guiones con IA.""" model = genai.GenerativeModel('gemini-pro') scripts = [] for i in range(variations): prompt = f""" Eres un guionista de videos virales para TikTok/Instagram/YouTube Shorts. Tema: {topic} Contexto: {context} Instrucciones: - Hazlo divertido y sarcástico. - 2 personajes con personalidades opuestas. - EXACTAMENTE 6 escenas numeradas. - Cada escena inicia con "Escena X:" y describe acción + diálogo breve. - Genera también un título viral y 5 hashtags. """ try: response = model.generate_content(prompt) scripts.append(response.text) except Exception as e: logging.error(f"Error generando guion: {e}") return scripts

def save_script_to_sheet(script_text, topic): if not sh: return [] scenes = re.findall(r"Escena \d+:.+", script_text) for scene in scenes: sh.append_row([topic, scene.strip()]) return scenes

def generate_tts_audio(scene_text, filename): tts = gTTS(text=scene_text, lang="es") tts.save(filename)

def generate_video_clips(scenes, topic_slug): output_dir = f"clips_{topic_slug}" os.makedirs(output_dir, exist_ok=True) clip_paths = []

for i, scene in enumerate(scenes):
    audio_path = os.path.join(output_dir, f"scene_{i+1}.mp3")
    video_path = os.path.join(output_dir, f"scene_{i+1}.mp4")
    generate_tts_audio(scene, audio_path)
    # Crear clip con imagen fija + audio (placeholder)
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', 'color=c=white:s=720x1280:d=5',
        '-i', audio_path,
        '-vf', "drawtext=text='"+scene.replace("'", "")[:40]+"...':fontcolor=black:fontsize=24:x=20:y=H-th-20",
        '-shortest', video_path
    ]
    subprocess.run(cmd, check=True)
    clip_paths.append(video_path)

return clip_paths

def combine_clips(clip_paths, topic_slug): list_file = f"videos_a_unir_{topic_slug}.txt" with open(list_file, 'w') as f: for path in clip_paths: f.write(f"file '{os.path.abspath(path)}'\n")

output_path = f"video_final_{topic_slug}.mp4"
cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', '-y', output_path]
subprocess.run(cmd, check=True)
os.remove(list_file)
return output_path

def post_to_social_media(video_path, title): logging.info(f"(Simulación) Publicando {video_path} con título: {title}")

---------------- MAIN ----------------

if name == "main": logging.info("🚀 Iniciando flujo mejorado...")

topics = get_trending_topics()
if not topics:
    logging.warning("No se encontraron tendencias")
    exit()

for topic in topics:
    slug = re.sub(r'\W+', '_', topic).lower()
    context = get_context_for_topic(topic)
    scripts = generate_script(topic, context, variations=2)

    for idx, script in enumerate(scripts):
        logging.info(f"Procesando variación {idx+1} para {topic}")
        scenes = save_script_to_sheet(script, topic)
        if not scenes:
            continue

        clips = generate_video_clips(scenes, f"{slug}_{idx+1}")
        final = combine_clips(clips, f"{slug}_{idx+1}")
        post_to_social_media(final, f"¡{topic}! 🚀 #viral")

logging.info("✅ Flujo completado.")

